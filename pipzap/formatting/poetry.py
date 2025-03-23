from copy import deepcopy
from typing import Any, Dict, List, Union

import tomlkit

from pipzap.core.dependencies import Dependency
from pipzap.formatting.base import DependenciesFormatter
from pipzap.parsing.converter import ProjectConverter
from pipzap.utils.pretty_string import remove_prefix


class PoetryFormatter(DependenciesFormatter):
    """Builds a Poetry pyproject.toml structure from parsed dependencies."""

    TEMPLATE: Dict[str, Any] = {
        "tool": {
            "poetry": {
                "name": ProjectConverter.DUMMY_PROJECT_NAME,
                "version": "0.0.0",
                "description": "",
                "authors": ["Generated <generated@example.com>"],
            }
        }
    }

    def format(self) -> str:
        self.pyproject = deepcopy(self.TEMPLATE)

        main_deps = [d for d in self.deps if not d.group if not d.extra]
        extra_deps = [d for d in self.deps if d.extra]
        group_deps = [d for d in self.deps if d.group]

        self._add_base_dependencies(main_deps, extra_deps)
        self._add_group_dependencies(group_deps)
        self._add_extras(extra_deps)
        self._add_sources()

        return tomlkit.dumps(self.pyproject)

    def _add_base_dependencies(self, main_deps: List[Dependency], extra_deps: List[Dependency]) -> None:
        """Adds main and extra dependencies to [tool.poetry.dependencies].

        Args:
            main_deps: List of parsed dependencies that are static for the project.
            extra_deps: List of parsed optional dependencies (extras).
        """
        deps = {"python": remove_prefix(self.python_version, "=", 2)}

        for dep in main_deps:
            deps[dep.name] = self._format_dependency_spec(dep)

        for dep in extra_deps:
            spec = self._format_dependency_spec(dep)

            if isinstance(spec, dict):
                spec["optional"] = True
            else:
                spec = {"version": spec, "optional": True}

            deps[dep.name] = spec

        self.pyproject["tool"]["poetry"]["dependencies"] = deps

    def _add_group_dependencies(self, group_deps: List[Dependency]) -> None:
        """Adds group dependencies to [tool.poetry.group.*.dependencies].

        Args:
            group_deps: List of non-main and non-extra dependencies.
        """
        if not group_deps:
            return

        groups: Dict[str, Any] = {}
        for dep in group_deps:
            if dep.group is None:
                raise RuntimeError(
                    f"Internal error: dependency {dep.name} doesn't specify a group. "
                    "This is likely a bug, please report it."
                )

            group = groups.setdefault(dep.group, {"dependencies": {}})
            group["dependencies"][dep.name] = self._format_dependency_spec(dep)

        self.pyproject["tool"]["poetry"]["group"] = groups

    def _add_extras(self, extra_deps: List[Dependency]) -> None:
        """Adds extras to [tool.poetry.extras].

        Constructs the [extras] reference list.

        Args:
            extra_deps: List of parsed optional dependencies (extras).
        """
        if not extra_deps:
            return

        extras: Dict[str, List[str]] = {}
        for dep in extra_deps:
            if dep.extra is None:
                raise RuntimeError(
                    f"Internal error: dependency {dep.name} doesn't belong to any extra. "
                    "This is likely a bug, please report it."
                )

            extras.setdefault(dep.extra, []).append(dep.name)

        self.pyproject["tool"]["poetry"]["extras"] = extras

    def _add_sources(self) -> None:
        """Adds custom indexes to [[tool.poetry.source]]."""
        seen_indexes = set()
        sources = []

        for dep in self.deps:
            if not dep.index:
                continue

            index_key = str(dep.index)
            if isinstance(dep.index, dict):
                if "url" not in dep.index:
                    continue

                index_key = dep.index["url"]

            if index_key in seen_indexes:
                continue

            seen_indexes.add(index_key)
            source_name = index_key.split("://", 1)[-1]
            sources.append({"name": source_name, "url": index_key})

        self.pyproject["tool"]["poetry"]["source"] = sources

    @staticmethod
    def _format_dependency_spec(dep: Dependency) -> Union[(Dict[(str, Any)], str)]:
        """Format a dependency specification as a Poetry entry.

        Args:
            dep: The Dependency object to format.

        Returns:
            A dictionary for complex specs (e.g., Git, URL) or a string for bare version constraints.
        """

        if dep.source and "git" in dep.source:
            spec = {"git": dep.source["git"]}
            if "rev" in dep.source:
                spec["rev"] = dep.source["rev"]
            return spec

        if dep.url:
            return {"url": dep.url}

        if dep.version_constraint:
            return remove_prefix(dep.version_constraint, "=", 2)

        return "*"
