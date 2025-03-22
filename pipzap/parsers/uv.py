from pathlib import Path
from typing import List, Optional, Tuple

import tomlkit

from pipzap.core.dependencies import Dependency, ProjectDependencies
from pipzap.exceptions import ParseError
from pipzap.parsers.base import DependencyParser


class UVTomlParser(DependencyParser):
    """Parses UV pyproject.toml dependencies."""

    def parse(self, file_path: Path) -> Tuple[ProjectDependencies, Optional[str]]:
        """Parses a UV pyproject.toml file and returns project dependencies along with the python version.

        Args:
            file_path: A path to the uv pyproject.toml file.

        Returns:
            A tuple containing a ProjectDependencies instance (with direct dependencies and an empty graph)
            and an optional string representing the python version.

        Raises:
            ParseError: Raised when the file is not found or the TOML content is invalid.
        """
        if not file_path.exists():
            raise ParseError(f"File not found: {file_path}")

        try:
            pyproject_data = tomlkit.load(file_path)
        except Exception as e:
            raise ParseError(f"Invalid TOML in {file_path}: {e}")

        deps_data = pyproject_data.get("project", {}).get("dependencies", [])
        python_version = pyproject_data.get("project", {}).get("requires-python", None)

        direct_deps: List[Dependency] = []
        for dep in deps_data:
            dep_obj = Dependency.from_string(dep)
            if dep_obj:
                direct_deps.append(dep_obj)

        return ProjectDependencies(direct=direct_deps, graph={}), python_version
