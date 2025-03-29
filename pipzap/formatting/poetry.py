from typing import Dict, Optional

import tomlkit

from pipzap.core.source_format import SourceFormat
from pipzap.formatting._uv_to_poetry import UVToPoetryConverter
from pipzap.formatting.base import DependenciesFormatter


class PoetryFormatter(DependenciesFormatter):
    """Formats pruned dependencies into a Poetry-style pyproject.toml."""

    def format(self) -> str:
        """Generates or updates the pyproject.toml to use the poetry format.

        Returns:
            A string representation of the pyproject.toml file.
        """

        if self.dependencies.source_format != SourceFormat.POETRY:
            assert self.dependencies.uv_pyproject_source, (
                "[internal assertion] No parsed uv pyproject provided."
            )
            pyproject = UVToPoetryConverter(self.dependencies.uv_pyproject_source).convert()
        else:
            assert self.dependencies.poetry_pyproject_source, (
                "[internal assertion] Source project must be provided for poetry-to-poetry export."
            )
            pyproject = self.dependencies.poetry_pyproject_source

        pyproject = self._filter_pyproject(pyproject)
        return tomlkit.dumps(pyproject)

    def _filter_pyproject(self, pyproject: dict) -> dict:
        kept_names = {dep.name.lower() for dep in self.dependencies.direct}

        self._remove_irrelevant_sections(pyproject)
        poetry = pyproject.get("tool", {}).get("poetry", {})

        self._filter_dependencies(poetry)
        self._filter_groups(poetry)
        self._filter_extras(poetry, kept_names)
        self._filter_sources(poetry)

        return pyproject

    def _remove_irrelevant_sections(self, pyproject: dict) -> None:
        """Remove sections not needed for Poetry from pyproject.toml.

        Args:
            pyproject: The pyproject.toml dictionary to modify.
        """
        project = pyproject.get("project", {})
        project.pop("dependencies", None)
        project.pop("optional-dependencies", None)

        pyproject.pop("dependency-groups", None)
        pyproject.get("tool", {}).pop("uv", None)

    def _filter_dependencies(self, poetry: dict) -> None:
        """Filters main dependencies in the poetry section."""
        poetry["dependencies"] = self._filter_section(poetry.get("dependencies", {}), None)

    def _filter_groups(self, poetry: dict) -> None:
        """Filters group dependencies, removing groups with no dependencies left."""

        groups = poetry.get("group", {})
        filtered_groups = {
            name: {"dependencies": self._filter_section(group.get("dependencies", {}), name)}
            for name, group in groups.items()
            if self._filter_section(group.get("dependencies", {}), name)
        }

        if not filtered_groups:
            return poetry.pop("group", None)

        poetry["group"] = filtered_groups

    def _filter_extras(self, poetry: dict, kept_names: set) -> None:
        """Filters extras, removing those with no dependencies left.

        Args:
            poetry: The 'tool.poetry' section dictionary to modify.
            kept_names: Set of dependency names to retain.
        """
        extras = poetry.get("extras", {})
        filtered_extras = {
            extra: tomlkit.array([dep for dep in deps if dep.lower() in kept_names]).multiline(True)
            for extra, deps in extras.items()
            if [dep for dep in deps if dep.lower() in kept_names]
        }
        if not filtered_extras:
            return poetry.pop("extras", None)

        poetry["extras"] = filtered_extras

    def _filter_sources(self, poetry: dict) -> None:
        """Filters sources to keep only those referenced by dependencies."""
        all_specs = list(poetry.get("dependencies", {}).values())
        for group in poetry.get("group", {}).values():
            all_specs.extend(group.get("dependencies", {}).values())

        used_sources = {spec["source"] for spec in all_specs if isinstance(spec, dict) and "source" in spec}
        sources = poetry.get("source", [])

        filtered_sources = [source for source in sources if source["name"] in used_sources]
        if not filtered_sources:
            return poetry.pop("source", None)

        poetry["source"] = filtered_sources

    def _filter_section(self, section: Dict, group: Optional[str]) -> Dict:
        """Filters a dependency section based on group context.

        Args:
            section: The dependency section to filter.
            group: The group name to filter by, or None for main dependencies.

        Returns:
            A filtered dictionary of dependencies.
        """
        return {name: spec for name, spec in section.items() if self._should_keep(name, group)}

    def _should_keep(self, name: str, group: Optional[str]) -> bool:
        """Checks if a dependency should be kept.

        Args:
            name: The name of the dependency.
            group: The group to check against, or None for main dependencies.

        Returns:
            True if the dependency should be retained, False otherwise.
        """
        if name == "python":
            return True

        return any(
            dep.name.lower() == name.lower() and (group in dep.groups if group else not dep.groups)
            for dep in self.dependencies.direct
        )
