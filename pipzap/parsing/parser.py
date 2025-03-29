from typing import Any, Dict, List, Optional, Set

import tomlkit
import tomlkit.items
from loguru import logger

from pipzap.core.dependencies import Dependency, DepKeyT, ProjectDependencies
from pipzap.core.source_format import SourceFormat
from pipzap.exceptions import ParsingError
from pipzap.parsing.workspace import Workspace
from pipzap.utils.io import read_toml
from pipzap.utils.requirement_string import parse_requirement_string


class DependenciesParser:
    """Parser for uv project dependencies from `pyproject.toml` and `uv.lock`."""

    @classmethod
    def parse(cls, workspace: Workspace, source_format: SourceFormat) -> ProjectDependencies:
        """Parse project dependencies from `pyproject.toml` and `uv.lock` into an internal runtime representation.

        Args:
            workspace: The workspace containing the project files.
            source_format: The format of the original dependencies definition.

        Returns:
            A ProjectDependencies instance with all dependencies and the extract information,
            such as groups, extras, etc.
        """
        original_project: Optional[dict] = None
        if workspace.backup and workspace.backup.suffix == ".toml":
            original_project = read_toml(workspace.backup)

        project = read_toml(workspace.base / "pyproject.toml")
        lock = read_toml(workspace.base / "uv.lock")
        lock.setdefault("package", [])

        indexes = cls._parse_indexes(project)
        direct = cls._build_direct_dependencies(project, indexes)
        graph = cls._build_dependency_graph(lock, direct)
        cls._set_pinned_version(lock, direct)

        py_version = project["project"]["requires-python"]
        parsed = ProjectDependencies(direct, graph, source_format, py_version, original_project, project)
        logger.debug(f"Parsed dependencies:\n{str(parsed)}")
        return parsed

    @staticmethod
    def _parse_indexes(project: Dict[(str, Any)]) -> Dict[(str, str)]:
        """Parses index definitions from `[tool.uv.index]`.

        Args:
            project: Parsed pyproject.toml dictionary.

        Returns:
            Dictionary mapping index names to their URLs.
        """
        index_list = project.get("tool", {}).get("uv", {}).get("index", [])
        return {index["name"]: index["url"] for index in index_list}

    @classmethod
    def _build_direct_dependencies(cls, project: Dict[str, Any], indexes: Dict[str, str]) -> List[Dependency]:
        """Builds a list of direct dependencies from `pyproject.toml`.

        Args:
            project: Parsed `pyproject.toml` dictionary.
            indexes: Dictionary of index names to URLs.

        Returns:
            List of Dependency instances for all direct dependencies.
        """
        direct = []
        uv_tool = project.get("tool", {}).get("uv", {})
        sources = uv_tool.get("sources", {})

        if not isinstance(sources, (dict, tomlkit.items.Table, tomlkit.items.InlineTable)):
            if len(sources) != 0:
                raise ParsingError(
                    "[tool.uv.sources] is expected to be a dict-like struct or an empty list, "
                    f"got {type(sources)=}, {len(sources)=}"
                )

            uv_tool["sources"] = sources = {}

        # [project.dependencies]
        for req in project.get("project", {}).get("dependencies", []):
            direct.append(cls._parse_requirement(req, set(), set(), sources, indexes))

        # [project.optional-dependencies]
        for extra, deps in project.get("project", {}).get("optional-dependencies", {}).items():
            for req in deps:
                direct.append(cls._parse_requirement(req, set(), {extra}, sources, indexes))

        # [dependency-groups]
        for group, deps in project.get("dependency-groups", {}).items():
            for dep in deps:
                if not isinstance(dep, str):
                    logger.warning(f"Found a non-flat dependency-group: {dep}. This is not implemented yet.")
                    continue

                direct.append(cls._parse_requirement(dep, {group}, set(), sources, indexes))

        return direct

    @staticmethod
    def _parse_requirement(
        req_str: str,
        groups: Set[str],
        extras: Set[str],
        sources: Dict[str, Any],
        indexes: Dict[str, str],
    ) -> Dependency:
        """Parse a single requirement string into a Dependency object."""
        req = parse_requirement_string(req_str)
        name = req.name
        source = sources.get(name, {})

        return Dependency(
            name=name,
            groups=frozenset(groups),
            extras=frozenset(extras),
            marker=str(req.marker) if req.marker else None,
            index=indexes.get(source.get("index")) if "index" in source else None,
            required_extras=frozenset(req.extras or []),
        )

    @staticmethod
    def _build_dependency_graph(lock: Dict[str, Any], deps: List[Dependency]) -> Dict[DepKeyT, List[DepKeyT]]:
        """Parse the resolved dependency graph from uv.lock."""
        graph = {}
        direct_map = {dep.key: dep for dep in deps}

        for package in lock.get("package", []):
            name = package["name"].lower()

            for d_name, groups, extras in direct_map:
                if d_name != name:
                    continue

                key = (name, groups, extras)
                package_deps: List[DepKeyT] = [
                    (dep_name["name"].lower(), frozenset(), frozenset())
                    for dep_name in package.get("dependencies", [])
                ]

                for i, (dep_name, _, _) in enumerate(package_deps):
                    if (dep_name, frozenset(), frozenset()) not in direct_map:
                        continue

                    direct_dep = direct_map[(dep_name, frozenset(), frozenset())]
                    package_deps[i] = (dep_name, frozenset(direct_dep.groups), frozenset(direct_dep.extras))

                graph[key] = package_deps

        for package in lock.get("package", []):
            name = package["name"].lower()
            key = (name, frozenset(), frozenset())
            if key in graph:
                continue

            graph[key] = [
                (dep["name"].lower(), frozenset(), frozenset())  #
                for dep in package.get("dependencies", [])
            ]

        return graph

    @staticmethod
    def _set_pinned_version(lock: Dict[str, Any], deps: List[Dependency]) -> None:
        """Fills the pinned versions of the dependencies from `uv.lock`."""
        versions = {package["name"]: package.get("version") for package in lock["package"]}
        for dep in deps:
            dep.pinned_version = version = versions.get(dep.name)

            if not version:
                logger.warning(f"Unable to determine a pinned version of {dep.name}")
