from typing import List

from pipzap.core.dependencies import Dependency
from pipzap.formatters.base import DependencyFormatter


class RequirementsFormatter(DependencyFormatter):
    """Formats dependencies in a requirements.txt style."""

    def format(self, deps: List[Dependency]) -> str:
        lines = []
        for dep in deps:
            if dep.source_type == "pypi":
                line = f"{dep.name}{dep.constraint}" if dep.constraint else dep.name

            elif dep.source_type == "git":
                if dep.constraint:
                    line = f"git+{dep.source_url}@{dep.constraint}#egg={dep.name}"
                else:
                    line = f"git+{dep.source_url}#egg={dep.name}"

            elif dep.source_type == "url":
                line = dep.source_url or ""

            elif dep.source_type == "file":
                line = dep.source_url or ""

            else:
                line = str(dep)

            lines.append(line)

        return "\n".join(lines)
