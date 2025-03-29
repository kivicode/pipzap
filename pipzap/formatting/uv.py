from copy import deepcopy
from typing import List, Optional, Set

import tomlkit

from pipzap.core.dependencies import DepKeyT
from pipzap.formatting.base import DependenciesFormatter
from pipzap.utils.requirement_string import parse_requirement_string


class UVFormatter(DependenciesFormatter):
    """Formats pruned dependencies back into a uv-style pyproject.toml by modifying the original structure."""

    def format(self) -> str:
        """Converts pruned dependencies back into a uv-style pyproject.toml string.

        Modifies the original pyproject.toml to retain only the pruned direct dependencies.

        Returns:
            A string representation of the updated pyproject.toml.
        """
        pyproject = self.dependencies.uv_pyproject_source
        assert pyproject, "[internal assertion] Source project must be provided"

        pyproject = deepcopy(pyproject)
        project = pyproject.get("project", {})

        keep_keys = {dep.key for dep in self.dependencies.direct}

        # [project.dependencies]
        project_deps = project.get("dependencies")
        if project_deps:
            project["dependencies"] = self._filter_section(project_deps, keep_keys)

        # [project.optional-dependencies]
        optional_deps = project.get("optional-dependencies", [])
        for extra in optional_deps:
            optional_deps[extra] = self._filter_section(optional_deps[extra], keep_keys, extra=extra)

        # [dependency-groups]
        groups_deps = pyproject.get("dependency-groups", [])
        for group in groups_deps:
            groups_deps[group] = self._filter_section(groups_deps[group], keep_keys, group)

        pyproject.get("tool", {}).pop("poetry", None)
        return tomlkit.dumps(pyproject)

    def _filter_section(
        self,
        section: List[str],
        keep_keys: Set[DepKeyT],
        group: Optional[str] = None,
        extra: Optional[str] = None,
    ) -> List[str]:
        """Filters a section of dependencies to keep only those in keep_keys.

        Args:
            section: List of requirement strings from the original pyproject.toml.
            keep_keys: Set of (name, groups, extras) tuples to retain.
            group: The group context, if applicable.
            extra: The extra context, if applicable.

        Returns:
            Filtered list of requirement strings.
        """
        filtered = []
        group_set = frozenset([group]) if group else frozenset()
        extra_set = frozenset([extra]) if extra else frozenset()

        for req_str in section:
            if isinstance(req_str, dict) and "include-group" in req_str:
                filtered.append(req_str)
                continue

            name = parse_requirement_string(req_str).name.lower()
            key = (name, group_set, extra_set)

            if key in keep_keys:
                filtered.append(req_str)

        return tomlkit.array(filtered).multiline(True)
