from enum import Enum
from pathlib import Path

import tomli
from typing_extensions import Self

from pipzap.exceptions import ParseError


class SourceType(Enum):
    """Enumeration of known build systems."""

    REQUIREMENTS = "requirements"
    POETRY = "poetry"
    UV = "uv"

    @classmethod
    def detect_format(cls, file_path: Path) -> Self:
        """Attempts to guess the build system given a source file path."""

        if file_path.name.endswith("requirements.txt"):
            return cls.REQUIREMENTS

        if file_path.name != "pyproject.toml":
            raise ParseError(f"Cannot determine format of {file_path}")

        with file_path.open("rb") as f:
            data = tomli.load(f)

        if "tool" in data and "poetry" in data["tool"]:
            return cls.POETRY

        if "project" in data:
            return cls.UV

        raise ParseError(f"Cannot determine format of {file_path}")
