from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

from pipzap.core.dependencies import ProjectDependencies


class DependencyParser(ABC):
    """Base class for dependency parsers."""

    @abstractmethod
    def parse(self, file_path: Path) -> Tuple[ProjectDependencies, Optional[str]]:
        """Parses a dependency file, returning a ProjectDependencies instance.

        Args:
            file_path: Path to the dependency file.

        Returns:
            A tuple containing a ProjectDependencies instance with direct dependencies and an empty graph,
            and an optional string representing the python version requirement.
        """
        ...
