from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

from loguru import logger
from typing_extensions import Literal, Self

from pipzap.exceptions import ParseError


@dataclass
class Dependency:
    """Represents a single dependency with a unified constraint field.

    Attributes:
        name: Package name.
        constraint: Full version constraint (e.g., '==2.28.1', '>=1.26.9', or empty for no constraint).
        source_type: Source type of the dependency.
        source_url: URL or path for non-PyPI sources.
        custom_index: Custom package index URL.
    """

    name: str
    constraint: str = ""
    source_type: Literal["pypi", "git", "url", "file"] = "pypi"
    source_url: Optional[str] = None
    custom_index: Optional[str] = None
    qual_name: Optional[str] = None

    def __post_init__(self):
        self.qual_name = self.qual_name or self.name

    def to_uv_format(self) -> Union[str, Dict[str, Optional[str]]]:
        """Serializes the dependency for UV's pyproject.toml.

        Returns:
            The serialized dependency in a string or dictionary format.
        """
        if self.source_type == "pypi":
            return f"{self.name}{self.constraint}" if self.constraint else self.name

        return self.qual_name

    @classmethod
    def from_string(cls, dep_str: str, custom_index: Optional[str] = None) -> Optional[Self]:
        """Returns a Dependency instance constructed from a string.

        Args:
            dep_str: A string representing the dependency (e.g., 'requests==2.28.1').
            custom_index: An optional custom package index URL.

        Returns:
            A Dependency instance or None if the input string is empty.
        """
        if not dep_str:
            logger.warning("Empty dependency string provided")
            return None

        if "git+" in dep_str:
            return cls._from_git(dep_str, custom_index)
        if "http://" in dep_str or "http://" in dep_str:
            return cls._from_url(dep_str, custom_index)
        if cls._is_file_path(dep_str):
            return cls._from_file(dep_str, custom_index)
        return cls._from_pypi(dep_str, custom_index)

    @classmethod
    def from_dict(
        cls, name: str, value: Union[str, Dict[str, str]], custom_index: Optional[str] = None
    ) -> Optional[Self]:
        """Returns a Dependency instance constructed from a dictionary or string (e.g., Poetry format).

        Args:
            name: The name of the dependency.
            value: A string or dictionary representing the dependency details.
            custom_index: An optional custom package index URL.

        Returns:
            A Dependency instance or None if the value is invalid.
        """
        if isinstance(value, str):
            return cls(name, value, "pypi", custom_index=custom_index)
        if not isinstance(value, dict):
            logger.warning(f"Invalid dependency value for {name}: {value}")
            return None

        constraint = value.get("version", "")
        if "git" in value:
            return cls(
                name,
                value.get("rev", ""),
                "git",
                source_url=value["git"],
                custom_index=custom_index,
            )
        if "url" in value:
            return cls(
                name,
                constraint,
                "url",
                source_url=value["url"],
                custom_index=custom_index,
            )
        if "path" in value:
            return cls(
                name,
                constraint,
                "file",
                source_url=value["path"],
                custom_index=custom_index,
            )
        return cls(name, constraint, "pypi", custom_index=custom_index)

    @classmethod
    def _from_git(cls, dep_str: str, custom_index: Optional[str]) -> Self:
        """Parses a git-based dependency.

        Args:
            dep_str: A string representing a git-based dependency.
            custom_index: An optional custom package index URL.

        Returns:
            A Dependency instance.
        """
        name, url = cls._split_uri_name(dep_str)
        rev = url.split("@")[-1] if "@" in url else ""
        url = url.split("@")[0] if "@" in url else url
        egg_index = url.find("#egg=")
        name = url[egg_index + 5 :].strip() if egg_index != -1 else name
        return cls(name, rev, "git", source_url=dep_str, custom_index=custom_index, qual_name=dep_str)

    @classmethod
    def _from_url(cls, dep_str: str, custom_index: Optional[str]) -> Self:
        """Parses a URL-based dependency.

        Args:
            dep_str: A string representing a URL-based dependency.
            custom_index: An optional custom package index URL.

        Returns:
            A Dependency instance.
        """
        name, source = cls._split_uri_name(dep_str)
        return cls(name, "", "url", source_url=source, custom_index=custom_index, qual_name=dep_str)

    @classmethod
    def _from_file(cls, dep_str: str, custom_index: Optional[str]) -> Self:
        """Parses a file-based dependency.

        Args:
            dep_str: A string representing a file-based dependency.
            custom_index: An optional custom package index URL.

        Returns:
            A Dependency instance.
        """
        name, source = cls._split_uri_name(dep_str)
        return cls(name, "", "file", source, custom_index=custom_index, qual_name=dep_str)

    @classmethod
    def _from_pypi(cls, dep_str: str, custom_index: Optional[str]) -> Self:
        """Parses a PyPI dependency.

        Args:
            dep_str: A string representing a PyPI dependency.
            custom_index: An optional custom package index URL.

        Returns:
            A Dependency instance.
        """
        for op in ["==", ">=", "<=", ">", "<", "~=", "!="]:
            if op not in dep_str:
                continue

            name, constraint = dep_str.split(op, 1)
            return cls(
                name.strip(),
                f"{op}{constraint.strip()}",
                "pypi",
                custom_index=custom_index,
            )

        return cls(dep_str.strip(), "", "pypi", custom_index=custom_index)

    @staticmethod
    def _is_file_path(dep_str: str) -> bool:
        """Checks if the string represents a file path.

        Args:
            dep_str: A string to be evaluated.

        Returns:
            True if the string represents a file path, otherwise False.
        """
        dep_str = dep_str.split("@", 1)[-1].strip()
        return dep_str.startswith(("./", "../", "/", "~")) or dep_str.endswith((".tar.gz", ".whl"))

    @staticmethod
    def _split_uri_name(dep_str: str) -> Tuple[str, str]:
        if "@" not in dep_str:
            raise ParseError("Non-PyPI requirements must be prefixed with 'lib_name @ <uri>'")

        name, dep_str = dep_str.replace(" ", "").split("@", 1)
        return name, dep_str

    def __str__(self) -> str:
        if self.source_type == "pypi":
            return f"{self.name}{self.constraint}"

        return f"{self.name} ({self.source_type}: {self.source_url or ''}{self.constraint})"


@dataclass(frozen=True)
class ProjectDependencies:
    """Intermediate representation of project dependencies."""

    direct: List[Dependency]
    """A list of direct dependencies."""

    graph: Dict[str, List[str]]
    """A mapping of dependency names to lists of transitive dependencies."""
