from abc import ABC, abstractmethod

from pipzap.core.dependencies import ProjectDependencies
from pipzap.parsing.workspace import Workspace


class DependenciesFormatter(ABC):
    """Base class for dependency formatters.

    Turns parsed project dependencies into one of the standard packaging formats.
    """

    def __init__(self, workspace: Workspace, dependencies: ProjectDependencies):
        """
        Args:
            workspace: Current conversion workspace.
            dependencies: Parsed project dependencies to format.
        """
        self.workspace = workspace
        self.dependencies = dependencies

    @abstractmethod
    def format(self) -> str:
        """Executes the formatting of the dependencies tree provided in constructor.

        Returns:
            String representation of a formatted file.
        """
        ...
