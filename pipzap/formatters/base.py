from abc import ABC, abstractmethod
from typing import List

from pipzap.core.dependencies import Dependency


class DependencyFormatter(ABC):
    """Base class for formatting a list of dependencies.

    Provides an interface for converting dependency lists into various formats.
    """

    @abstractmethod
    def format(self, deps: List[Dependency]) -> str:
        """Returns a formatted string representation of dependencies."""
        pass
