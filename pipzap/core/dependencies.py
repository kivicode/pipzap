from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from pipzap.core.source_format import SourceFormat
from pipzap.utils.pretty_string import format_project_dependencies

DepKeyT = Tuple[str, FrozenSet[str], FrozenSet[str]]


@dataclass
class Dependency:
    """Represents a dependency with potentially multiple contexts and its own extras."""

    name: str
    """Package name (e.g., "torch")."""

    groups: FrozenSet[str] = field(default_factory=frozenset)
    """Group names the dependency belongs to."""

    extras: FrozenSet[str] = field(default_factory=frozenset)
    """Names of extras the dependency belongs to."""

    marker: Optional[str] = None
    """Marker of the dependency from pyproject.toml (e.g., "python_version >= '3.8'")."""

    index: Optional[str] = None
    """Name of the custom index to use for the dependency."""

    required_extras: FrozenSet[str] = field(default_factory=frozenset)
    """Extras required by this dependency."""

    pinned_version: Optional[str] = None
    """Exact pinned version from uv.lock."""

    indirect_markers: FrozenSet[str] = field(default_factory=frozenset)
    """Markers from uv.lock where this dependency is required by others."""

    @property
    def key(self) -> DepKeyT:
        return (self.name.lower(), frozenset(self.groups), frozenset(self.extras))


@dataclass
class ProjectDependencies:
    """Represents the project's dependencies with context."""

    direct: List[Dependency]
    """Dependencies directly mentioned in the source requirements.txt or pyproject.toml."""

    graph: Dict[DepKeyT, List[DepKeyT]]
    """Graph of dependency relations."""

    source_format: SourceFormat
    """The format of the original dependencies definition."""

    py_version: Optional[str] = None
    """Python version or constraint, if available."""

    poetry_pyproject_source: Optional[dict] = None
    """The original poetry pyproject.toml parsed, if applicable."""

    uv_pyproject_source: Optional[dict] = None
    """Normalized always-uv pyproject.toml version."""

    def __str__(self) -> str:
        return format_project_dependencies(self)
