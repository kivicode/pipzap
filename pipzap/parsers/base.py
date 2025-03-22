from abc import ABC, abstractmethod
from pathlib import Path

from pipzap.core.dependencies import ProjectDependencies


class DependencyParser(ABC):
    """Base class for dependency parsers."""

    @abstractmethod
    def parse(self, file_path: Path) -> ProjectDependencies:
        """Parses a dependency file, returning a ProjectDependencies instance.

        Args:
            file_path: Path to the dependency file.

        Returns:
            ProjectDependencies containing parsed dependency information.
        """
        ...
