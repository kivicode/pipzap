from argparse import Namespace
from pathlib import Path
from typing import Optional

import pytest

from pipzap.utils.io import write_toml


@pytest.fixture
def dummy_pyproject_dict() -> dict:
    """Generates a dummy uv-based pyproject.toml content."""
    return {
        "project": {
            "name": "test-project",
            "version": "0.1.0",
            "dependencies": ["requests>=2.28.1", "flask==2.0.1"],
            "requires-python": "~=3.8",
        },
        "tool": {"uv": {}},
    }


@pytest.fixture
def dummy_pyproject(tmp_path, dummy_pyproject_dict) -> Path:
    """Creates a dummy uv-bases pyproject.toml with all strictly required fields."""

    file = tmp_path / "pyproject.toml"
    write_toml(dummy_pyproject_dict, file)
    return file


@pytest.fixture
def make_pyproject(tmp_path: Path):
    """Factory fixture to create custom pyproject.toml files."""

    def _make_pyproject(content: dict) -> Path:
        file = tmp_path / "pyproject.toml"
        write_toml(content, file)
        return file

    return _make_pyproject


@pytest.fixture
def dummy_requirements_txt(tmp_path: Path) -> Path:
    """Provides a dummy requirements.txt file."""
    file = tmp_path / "requirements.txt"
    file.write_text("requests>=2.28.1\nflask==2.0.1")
    return file


@pytest.fixture
def cli_args():
    """Factory fixture for creating CLI argument objects."""

    def _cli_args(file: Path, output: Optional[Path] = None, **kwargs):
        defaults = {
            "file": file,
            "verbose": False,
            "output": output,
            "override": kwargs.get("override", False),
            "no_isolation": kwargs.get("no_isolation", True),
            "format": None,
            "python_version": "3.8",
            "version": kwargs.get("version", False),
        }
        return Namespace(**defaults)

    return _cli_args
