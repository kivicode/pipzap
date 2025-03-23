from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from packaging.requirements import Requirement
from typing_extensions import Self

from pipzap.utils.pretty_string import format_project_dependencies


@dataclass
class Dependency:
    """Represents a single dependency with detailed attributes."""

    name: str
    """Package name (e.g., "torch")."""

    version_constraint: Optional[str] = None
    """ Version specifier (e.g., ">=4.12.2"), if applicable."""

    url: Optional[str] = None
    """Direct URL if the dependency is sourced from a specific location."""

    group: Optional[str] = None
    """Name of the dependency group it belongs to, if any."""

    extra: Optional[str] = None
    """Name of the extra it belongs to, if any."""
    # TODO: Should it be a set?

    index: Optional[str] = None  # For custom indexes
    """Source index name (e.g., "pytorch-cu124"), if specified."""

    source: Optional[Dict[str, str]] = None
    """Source URL for Git, VCS, or other sources."""

    pinned_version: Optional[str] = None
    """Explicit pinned version, if provided."""

    @classmethod
    def from_string(
        cls,
        raw_requirement: str,
        group: Optional[str] = None,
        extra: Optional[str] = None,
        index: Optional[str] = None,
        source: Optional[Dict[str, str]] = None,
    ) -> Self:
        """Create a Dependency instance from a requirement string.

        Args:
            raw_requirement: The raw dependency string (e.g., "torch>=2.0.0").
            group: The group name, if applicable.
            extra: The extra name, if applicable.
            index: The index name, if specified.
            source: The source URL, if applicable.

        Returns:
            A Dependency instance with parsed attributes.
        """
        req = Requirement(raw_requirement)
        if req.url:
            return cls(name=req.name, url=req.url, group=group, extra=extra, source=source)

        return cls(
            name=req.name,
            version_constraint=str(req.specifier),
            group=group,
            extra=extra,
            index=index,
            source=source,
        )

    @property
    def context(self) -> Tuple[Optional[str], Optional[str]]:
        """A unique context identifier in a form of a group+extra tuple."""
        return (self.group, self.extra)


@dataclass
class ProjectDependencies:
    """Intermediate representation of project dependencies."""

    direct: List[Dependency]
    """A list of direct dependencies."""

    graph: Dict[str, List[str]]
    """A mapping of dependency names to lists of transitive dependencies."""

    py_version: Optional[str] = None
    """Version (or constraint) of the Python used to generate the dependencies."""

    def __str__(self):
        return format_project_dependencies(self)
