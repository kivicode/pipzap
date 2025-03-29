import pytest

from pipzap.parsing.converter import ProjectConverter
from pipzap.parsing.parser import DependenciesParser
from pipzap.parsing.workspace import Workspace


def test_parse_uv(make_pyproject):
    """Tests parsing dependencies from a UV pyproject.toml."""
    content = {
        "project": {
            "name": "test-project",
            "version": "0.1.0",
            "dependencies": ["requests>=2.28.1"],
            "requires-python": "~=3.8",
        },
        "tool": {"uv": {}},
    }
    file = make_pyproject(content)

    with Workspace(file) as ws:
        fmt = ProjectConverter().convert_to_uv(ws)
        parsed = DependenciesParser.parse(ws, fmt)
        assert any(dep.name == "requests" for dep in parsed.direct)


def test_parse_poetry(make_pyproject):
    """Tests parsing dependencies from a Poetry pyproject.toml."""
    content = {
        "tool": {
            "poetry": {
                "name": "test-project",
                "version": "0.1.0",
                "dependencies": {"python": "^3.8", "flask": "2.0.1"},
            }
        }
    }
    file = make_pyproject(content)

    with Workspace(file) as ws:
        fmt = ProjectConverter().convert_to_uv(ws)
        parsed = DependenciesParser.parse(ws, fmt)
        assert any(dep.name == "flask" for dep in parsed.direct)


def test_parse_requirements_txt(dummy_requirements_txt):
    """Tests parsing dependencies from a requirements.txt file."""
    with Workspace(dummy_requirements_txt) as ws:
        fmt = ProjectConverter().convert_to_uv(ws)
        parsed = DependenciesParser.parse(ws, fmt)

        assert any(dep.name == "requests" for dep in parsed.direct)
        assert any(dep.name == "flask" for dep in parsed.direct)


def test_invalid_python_version_specifications(make_pyproject):
    """Tests handling of invalid Python version specifications."""
    content = {
        "project": {
            "name": "test-project",
            "version": "0.1.0",
            "dependencies": ["packageA==1.0.0"],
            "requires-python": "invalid",
        },
        "tool": {"uv": {}},
    }

    with Workspace(make_pyproject(content)) as ws:
        converter = ProjectConverter("invalid")

        with pytest.raises(Exception):
            converter.convert_to_uv(ws)
