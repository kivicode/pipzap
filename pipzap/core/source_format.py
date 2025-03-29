from enum import Enum
from pathlib import Path

from pipzap.exceptions import ParsingError
from pipzap.utils.io import read_toml


class SourceFormat(Enum):
    """Enumeration of known build systems."""

    REQS = "reqs"
    POETRY = "poetry"
    UV = "uv"

    @classmethod
    def detect_format(cls, file_path: Path) -> "SourceFormat":
        """Attempts to guess the build system given a source file path."""

        if "requirements" in file_path.name and ".txt" in file_path.suffixes:
            return cls.REQS

        if file_path.name != "pyproject.toml":
            raise ParsingError(f"Cannot determine format of {file_path}")

        data = read_toml(file_path)

        if "tool" in data and "poetry" in data["tool"]:
            return cls.POETRY

        if "project" in data:
            return cls.UV

        raise ParsingError(f"Cannot determine format of {file_path}")
