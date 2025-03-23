from abc import ABC, abstractmethod
from pipzap.core.dependencies import ProjectDependencies


class DependenciesFormatter(ABC):
    """Base class for dependency formatters.

    Turns parsed project dependencies into one of the standard packaging formats.
    """

    def __init__(self, dependencies: ProjectDependencies):
        """
        Args:
            dependencies: Parsed project dependencies to format.
        """
        self.python_version = dependencies.py_version
        self.deps = dependencies.direct

    @abstractmethod
    def format(self) -> str:
        """Executes the formatting of the dependencies tree provided in constructor.

        Returns:
            String representation of a formatted file.
        """
        ...
