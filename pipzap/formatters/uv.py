from typing import Dict, List, Optional, Union

import tomlkit

from pipzap.core.dependencies import Dependency
from pipzap.formatters.base import DependencyFormatter


class UVFormatter(DependencyFormatter):
    """Formats dependencies in a UV pyproject.toml style."""

    def format(self, deps: List[Dependency]) -> str:
        uv_deps = []
        for dep in deps:
            entry: Union[str, Dict[str, Optional[str]]]

            if dep.source_type == "pypi":
                entry = f"{dep.name}{dep.constraint}" if dep.constraint else dep.name

            elif dep.source_type == "git":
                entry = {"git": dep.source_url}
                if dep.constraint:
                    entry["rev"] = dep.constraint

            elif dep.source_type == "url":
                entry = {"url": dep.source_url}

            elif dep.source_type == "file":
                entry = {"path": dep.source_url}

            else:
                entry = str(dep)

            uv_deps.append(entry)
        toml_data = {"project": {"dependencies": uv_deps}}
        return tomlkit.dumps(toml_data)
