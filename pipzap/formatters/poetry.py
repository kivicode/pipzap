from typing import Dict, List, Union

import tomlkit

from pipzap.core.dependencies import Dependency
from pipzap.formatters.base import DependencyFormatter


class PoetryFormatter(DependencyFormatter):
    """Formats dependencies in a Poetry pyproject.toml style."""

    def format(self, deps: List[Dependency]) -> str:
        poetry_deps: Dict[str, Union[str, Dict]] = {}
        for dep in deps:
            version: Union[str, Dict]

            if dep.source_type == "pypi":
                version = dep.constraint if dep.constraint else "*"

            elif dep.source_type == "git":
                entry = {"git": dep.source_url}
                if dep.constraint:
                    entry["rev"] = dep.constraint
                version = entry

            elif dep.source_type == "url":
                version = {"url": dep.source_url}

            elif dep.source_type == "file":
                version = {"path": dep.source_url}

            else:
                version = str(dep)

            if isinstance(version, str):
                version = version.replace("==", "")
            poetry_deps[dep.name] = version

        toml_data = {"tool": {"poetry": {"dependencies": poetry_deps}}}
        return tomlkit.dumps(toml_data)
