from enum import Enum
from pathlib import Path

from pipzap.exceptions import ParseError
from pipzap.utils.io import read_toml


class SourceType(Enum):
    """Enumeration of known build systems."""

    REQUIREMENTS = "requirements"
    POETRY = "poetry"
    UV = "uv"

    @classmethod
    def detect_format(cls, file_path: Path) -> "SourceType":
        """Attempts to guess the build system given a source file path."""

        if "requirements" in file_path.name and ".txt" in file_path.suffixes:
            return cls.REQUIREMENTS

        if file_path.name != "pyproject.toml":
            raise ParseError(f"Cannot determine format of {file_path}")

        data = read_toml(file_path)

        if "tool" in data and "poetry" in data["tool"]:
            return cls.POETRY

        if "project" in data:
            return cls.UV

        raise ParseError(f"Cannot determine format of {file_path}")
