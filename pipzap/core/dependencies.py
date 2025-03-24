from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from pipzap.utils.pretty_string import format_project_dependencies

DepKeyT = Tuple[str, FrozenSet[str], FrozenSet[str]]


@dataclass
class Dependency:
    """Represents a dependency with potentially multiple contexts and its own extras."""

    name: str
    """Package name (e.g., "torch")."""

    groups: Set[str] = frozenset()
    """Group names the dependency belongs to."""

    extras: Set[str] = frozenset()
    """Names of extras the dependency belongs to."""

    marker: Optional[str] = None
    """Marker of the dependency (e.g., "python_version >= '3.8'")."""

    index: Optional[str] = None
    """Name of the custom index to use for the dependency."""

    required_extras: Set[str] = frozenset()
    """Extras required by this dependency."""

    @property
    def key(self) -> DepKeyT:
        return (self.name.lower(), frozenset(self.groups), frozenset(self.extras))


@dataclass
class ProjectDependencies:
    """Represents the project's dependencies with context."""

    direct: List[Dependency]
    graph: Dict[DepKeyT, List[DepKeyT]]
    py_version: Optional[str] = None
    uv_pyproject_source: Optional[dict] = None

    def __str__(self) -> str:
        return format_project_dependencies(self)
