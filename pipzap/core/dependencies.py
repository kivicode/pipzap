from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from loguru import logger
from typing_extensions import Literal, Self


@dataclass(frozen=True)
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

    def to_uv_format(self) -> Union[str, Dict[str, Optional[str]]]:
        """Serializes the dependency for UV's pyproject.toml.

        Returns:
            The serialized dependency in a string or dictionary format.
        """
        if self.source_type == "pypi":
            return f"{self.name}{self.constraint}" if self.constraint else self.name

        if self.source_type == "git":
            base = {"git": self.source_url}
            if self.constraint:
                base["rev"] = self.constraint
            return base

        if self.source_type == "url":
            return {"url": self.source_url}

        if self.source_type == "file":
            return {"path": self.source_url}

        raise ValueError(f"Unsupported source_type: {self.source_type}")

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

        if dep_str.startswith("git+"):
            return cls._from_git(dep_str, custom_index)
        if dep_str.startswith(("http://", "https://")) and not dep_str.startswith("git+"):
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
            return cls(name=name, constraint=value, source_type="pypi", custom_index=custom_index)
        if not isinstance(value, dict):
            logger.warning(f"Invalid dependency value for {name}: {value}")
            return None

        constraint = value.get("version", "")
        if "git" in value:
            return cls(
                name=name,
                constraint=value.get("rev", ""),
                source_type="git",
                source_url=value["git"],
                custom_index=custom_index,
            )
        if "url" in value:
            return cls(
                name=name,
                constraint=constraint,
                source_type="url",
                source_url=value["url"],
                custom_index=custom_index,
            )
        if "path" in value:
            return cls(
                name=name,
                constraint=constraint,
                source_type="file",
                source_url=value["path"],
                custom_index=custom_index,
            )
        return cls(name=name, constraint=constraint, source_type="pypi", custom_index=custom_index)

    @classmethod
    def _from_git(cls, dep_str: str, custom_index: Optional[str]) -> Self:
        """Parses a git-based dependency.

        Args:
            dep_str: A string representing a git-based dependency.
            custom_index: An optional custom package index URL.

        Returns:
            A Dependency instance.
        """
        url = dep_str.replace("git+", "")
        rev = url.split("@")[-1] if "@" in url else ""
        url = url.split("@")[0] if "@" in url else url
        egg_index = dep_str.find("#egg=")
        name = dep_str[egg_index + 5 :].strip() if egg_index != -1 else "unknown"
        return cls(name, rev, source_type="git", source_url=url, custom_index=custom_index)

    @classmethod
    def _from_url(cls, dep_str: str, custom_index: Optional[str]) -> Self:
        """Parses a URL-based dependency.

        Args:
            dep_str: A string representing a URL-based dependency.
            custom_index: An optional custom package index URL.

        Returns:
            A Dependency instance.
        """
        return cls("unknown", "", source_type="url", source_url=dep_str, custom_index=custom_index)

    @classmethod
    def _from_file(cls, dep_str: str, custom_index: Optional[str]) -> Self:
        """Parses a file-based dependency.

        Args:
            dep_str: A string representing a file-based dependency.
            custom_index: An optional custom package index URL.

        Returns:
            A Dependency instance.
        """
        return cls("unknown", "", source_type="file", source_url=dep_str, custom_index=custom_index)

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
                source_type="pypi",
                custom_index=custom_index,
            )

        return cls(dep_str.strip(), "", source_type="pypi", custom_index=custom_index)

    @staticmethod
    def _is_file_path(dep_str: str) -> bool:
        """Checks if the string represents a file path.

        Args:
            dep_str: A string to be evaluated.

        Returns:
            True if the string represents a file path, otherwise False.
        """
        return dep_str.startswith(("./", "../", "/", "~")) or dep_str.endswith((".tar.gz", ".whl"))

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
