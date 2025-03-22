from pathlib import Path
from typing import List, Optional, Tuple

import toml
from loguru import logger

from pipzap.core.dependencies import Dependency, ProjectDependencies
from pipzap.exceptions import ParseError
from pipzap.parsers.base import DependencyParser


class PoetryTomlParser(DependencyParser):
    """Parses Poetry pyproject.toml files, supporting both old and new formats.

    Extracts dependencies from the 'project.dependencies' section or, if absent,
    from the 'tool.poetry.dependencies' section.
    """

    def parse(self, file_path: Path) -> Tuple[ProjectDependencies, Optional[str]]:
        """Parses a Poetry pyproject.toml file and returns the project dependencies and python version.

        Args:
            file_path: A Path representing the location of the pyproject.toml file.

        Returns:
            A tuple containing a ProjectDependencies instance with direct dependencies and an empty graph,
            and an optional string representing the python version requirement.

        Raises:
            ParseError: An error indicating that the file was not found or that the TOML content is invalid.
        """
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            raise ParseError(f"File not found: {file_path}")

        try:
            pyproject_data = toml.load(file_path)
        except Exception as e:
            raise ParseError(f"Invalid TOML in {file_path}: {e}")

        deps_data = pyproject_data.get("project", {}).get("dependencies", None)
        python_version = pyproject_data.get("project", {}).get("requires-python", None)
        source = "project.dependencies"

        if deps_data is None:
            deps_data = pyproject_data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            python_version = python_version or pyproject_data.get("tool", {}).get("poetry", {}).get(
                "dependencies", {}
            ).get("python", None)
            source = "tool.poetry.dependencies"

        direct_deps: List[Dependency] = []
        for name, value in deps_data.items():
            if name.lower() == "python":
                continue

            dep = Dependency.from_dict(name, value if isinstance(value, dict) else value)
            if dep:
                direct_deps.append(dep)

        logger.debug(f"Parsed dependencies from {source} in {file_path}")
        return ProjectDependencies(direct=direct_deps, graph={}), python_version
