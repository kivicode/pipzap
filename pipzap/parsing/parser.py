from typing import Any, Dict, List, Optional, Set

from loguru import logger
from pkg_resources import Requirement

from pipzap.core.dependencies import Dependency, ProjectDependencies
from pipzap.parsing.workspace import Workspace
from pipzap.utils.io import read_toml


class DependenciesParser:
    """Parser for uv project dependencies from `pyproject.toml` and `uv.lock`."""

    @classmethod
    def parse(cls, workspace: Workspace) -> ProjectDependencies:
        """Parse project dependencies from `pyproject.toml` and `uv.lock` into an internal runtime representation.

        Args:
            workspace: The workspace containing the project files.

        Returns:
            A ProjectDependencies instance with all dependencies and the extract information,
            such as groups, extras, etc.
        """
        project = read_toml(workspace.base / "pyproject.toml")
        lock = read_toml(workspace.base / "uv.lock")

        indexes = cls._parse_indexes(project)
        direct = cls._build_direct_dependencies(project, indexes)
        direct = cls._add_pinned_versions(direct, lock)
        graph = cls._build_dependency_graph(lock)

        py_version = project["project"]["requires-python"]
        parsed = ProjectDependencies(direct=direct, graph=graph, py_version=py_version)
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
    def _build_direct_dependencies(
        cls, project: Dict[(str, Any)], indexes: Dict[(str, str)]
    ) -> List[Dependency]:
        """Builds a list of direct dependencies from `pyproject.toml`.

        Args:
            project: Parsed `pyproject.toml` dictionary.
            indexes: Dictionary of index names to URLs.

        Returns:
            List of Dependency instances for all direct dependencies.
        """
        direct = []
        sources = project.get("tool", {}).get("uv", {}).get("sources", {})

        # [project.dependencies]
        main_deps = project["project"].get("dependencies", [])
        for req in main_deps:
            direct.append(cls._parse_dependency(req, sources, indexes, group=None, extra=None))

        # [project.optional-dependencies]
        optional_deps = project["project"].get("optional-dependencies", {})
        for extra, deps in optional_deps.items():
            for req in deps:
                direct.append(cls._parse_dependency(req, sources, indexes, group=None, extra=extra))

        # [dependency-groups]
        dependency_groups = project.get("dependency-groups", {})
        for group_name in dependency_groups:
            resolved_deps = cls._resolve_group_dependencies(group_name, dependency_groups)

            for req in resolved_deps:
                direct.append(cls._parse_dependency(req, sources, indexes, group=group_name, extra=None))

        return direct

    @staticmethod
    def _parse_dependency(
        raw_requirement: str,
        sources: Dict[(str, Any)],
        indexes: Dict[(str, str)],
        group: Optional[str] = None,
        extra: Optional[str] = None,
    ) -> Dependency:
        """Parses a single dependency string with index information.

        Args:
            raw_requirement: The raw dependency string (e.g., "torch" or "torch~=2.1.0").
            sources: Dictionary from `[tool.uv.sources]`.
            indexes: Dictionary of index names to URLs.
            group: The group name, if applicable.
            extra: The extra name, if applicable.

        Returns:
            A Dependency instance.
        """
        req_name = Requirement(raw_requirement).name
        source_info = sources.get(req_name)

        if not source_info:
            return Dependency.from_string(raw_requirement, group, extra)

        if "index" not in source_info:
            return Dependency.from_string(raw_requirement, group, extra, source_info)

        index_url = indexes.get(source_info["index"])
        return Dependency.from_string(raw_requirement, group, extra, index_url, source_info)

    @classmethod
    def _resolve_group_dependencies(
        cls,
        group_name: str,
        dependency_groups: Dict[(str, Any)],
        visited: Optional[Set[str]] = None,
    ) -> List[str]:
        """Recursively resolves dependencies for a group.

        Args:
            group_name: The name of the group to resolve.
            dependency_groups: Dictionary of all dependency groups.
            visited: Set of visited group names to detect circular references.

        Returns:
            List of requirement strings for the group.

        Raises:
            ValueError: If a circular dependency is detected.
        """
        if visited is None:
            visited = set()

        if group_name in visited:
            raise ValueError(f"Circular dependency in group {group_name}")

        visited.add(group_name)

        dependencies = []
        group = dependency_groups.get(group_name, [])
        for item in group:
            if isinstance(item, str):
                dependencies.append(item)
                continue

            if not isinstance(item, dict) and "include-group" not in item:
                continue

            included_group = item["include-group"]
            dependencies.extend(cls._resolve_group_dependencies(included_group, dependency_groups, visited))

        visited.remove(group_name)
        return dependencies

    @staticmethod
    def _add_pinned_versions(dependencies: List[Dependency], lock: Dict[(str, Any)]) -> List[Dependency]:
        """Adds explicit pinned versions to each dependency.

        Args:
            dependencies: Current list of all parsed dependencies.
            lock: Parsed `uv.lock` dictionary.

        Returns:
            List of input dependencies with the pinned versions filled in.
        """
        locked_versions = {dep["name"]: dep["version"] for dep in lock["package"]}

        for dep in dependencies:
            dep.pinned_version = locked_versions.get(dep.name)

            if dep.pinned_version is None:
                logger.warning(f"Unable to determine version of {dep.name}")

        return dependencies

    @staticmethod
    def _build_dependency_graph(lock: Dict[(str, Any)]) -> Dict[(str, List[str])]:
        """Build the transitive dependency graph from uv.lock.

        Args:
            lock: Parsed `uv.lock` dictionary.

        Returns:
            Dictionary mapping package names to their dependencies.
        """
        return {
            package["name"]: [dep["name"] for dep in package.get("dependencies", [])]
            for package in lock["package"]
        }
