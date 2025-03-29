class DependencyError(Exception):
    """Base exception for dependency-related errors."""

    ...


class ParsingError(DependencyError):
    """Raised when parsing a dependency file fails."""

    ...


class ResolutionError(DependencyError):
    """Raised when dependency resolution fails."""

    ...
