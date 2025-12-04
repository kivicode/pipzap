from io import StringIO
from typing import Set

from ruamel.yaml import YAML

from pipzap.core.dependencies import DepKeyT
from pipzap.formatting.base import DependenciesFormatter
from pipzap.utils.requirement_string import parse_requirement_string


class CondaFormatter(DependenciesFormatter):
    """Formats pruned dependencies back into a conda environment.yml by modifying the original structure."""

    def format(self) -> str:
        yaml = YAML()
        yaml.preserve_quotes = True

        with self.workspace.backup.open(encoding="utf-8") as f:
            data = yaml.load(f)

        keep_keys = {dep.key for dep in self.dependencies.direct}

        if "dependencies" in data:
            for i, dep in enumerate(data["dependencies"]):
                if isinstance(dep, dict) and "pip" in dep:
                    data["dependencies"][i]["pip"] = self._filter_pip_section(dep["pip"], keep_keys)
                    break

        stream = StringIO()
        yaml.dump(data, stream)
        return stream.getvalue()

    def _filter_pip_section(self, pip_deps: list, keep_keys: Set[DepKeyT]) -> list:
        """Filters pip dependencies to keep only those in keep_keys.

        Args:
            pip_deps: List of pip requirement strings from the original environment.yml.
            keep_keys: Set of (name, groups, extras) tuples to retain.

        Returns:
            Filtered list of pip requirement strings (deduplicated).
        """

        filtered = []
        seen_names = set()

        for req_str in pip_deps:
            # Skip non-string entries (like -r references) or flag-style entries
            if not isinstance(req_str, str) or req_str.startswith("-"):
                filtered.append(req_str)
                continue

            try:
                name = parse_requirement_string(req_str).name.lower()
            except Exception:
                # Keep unparseable entries
                filtered.append(req_str)
                continue

            key: DepKeyT = (name, frozenset(), frozenset())

            if name in seen_names:
                continue

            if key in keep_keys:
                seen_names.add(name)
                filtered.append(req_str)

        return filtered
