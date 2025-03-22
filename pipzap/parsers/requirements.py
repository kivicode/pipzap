from pathlib import Path
from typing import List, Optional, Tuple

from pipzap.core.dependencies import Dependency, ProjectDependencies
from pipzap.exceptions import ParseError
from pipzap.parsers.base import DependencyParser


class RequirementsTxtParser(DependencyParser):
    """Parses requirements.txt files."""

    def parse(self, file_path: Path) -> Tuple[ProjectDependencies, Optional[str]]:
        """Parses a requirements.txt file and returns project dependencies.

        Args:
            file_path: A Path to the requirements.txt file.

        Returns:
            A tuple containing a ProjectDependencies instance with direct dependencies
            and an empty dependency graph, and None indicating no python version was extracted.

        Raises:
            ParseError: An error indicating that the file was not found.
        """
        if not file_path.exists():
            raise ParseError(f"File not found: {file_path}")

        direct_deps: List[Dependency] = []
        custom_index: Optional[str] = None

        with file_path.open("r") as file:
            lines = file.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("--extra-index-url"):
                custom_index = self._extract_custom_index(line)
                continue

            dep = Dependency.from_string(line, custom_index)
            if dep:
                direct_deps.append(dep)

        return ProjectDependencies(direct=direct_deps, graph={}), None

    @staticmethod
    def _extract_custom_index(line: str) -> Optional[str]:
        """Extracts the custom package index URL from a given line.

        Args:
            line: A string line from the requirements.txt file.

        Returns:
            The custom index URL if present, otherwise None.
        """
        parts = line.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else None
