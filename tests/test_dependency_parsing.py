import pytest

from pipzap.core.source_format import SourceFormat
from pipzap.exceptions import ParsingError, ResolutionError
from pipzap.parsing.converter import ProjectConverter
from pipzap.parsing.parser import DependenciesParser
from pipzap.parsing.workspace import Workspace
from pipzap.utils.requirement_string import parse_requirement_string


def test_malformed_dependency_strings(make_pyproject, dummy_pyproject_dict):
    """Tests parsing a pyproject.toml with malformed dependency strings.

    Expects an exception due to invalid requirement syntax.
    """
    content = dummy_pyproject_dict
    content["project"]["dependencies"] = ["requests==invalid", "@malformed-url", "[extra_without_name"]

    file = make_pyproject(content)
    with Workspace(file) as ws:
        with pytest.raises(ResolutionError, match="Failed to execute resolution"):
            ProjectConverter().convert_to_uv(ws)

    for dep in content["project"]["dependencies"]:
        with pytest.raises(ParsingError, match="Malformed"):
            parse_requirement_string(dep)


def test_empty_missing_dependency_sections(make_pyproject, dummy_pyproject_dict):
    """Tests parsing a pyproject.toml with an empty dependencies list and no optional sections."""
    content = dummy_pyproject_dict
    content["project"]["dependencies"] = []
    file = make_pyproject(content)

    with Workspace(file) as ws:
        (ws.base / "uv.lock").write_text("")
        parsed = DependenciesParser.parse(ws, SourceFormat.UV)
        assert parsed.direct == [], "Expected no direct dependencies"


def test_unsupported_markers(make_pyproject, dummy_pyproject_dict):
    """Tests parsing a dependency with an unsupported marker."""

    content = dummy_pyproject_dict
    content["project"]["dependencies"] = ["package; implementation_name=='pypy'"]

    file = make_pyproject(content)
    with Workspace(file) as ws:
        # Create an empty uv.lock to simulate a resolved state
        (ws.base / "uv.lock").write_text("")
        parsed = DependenciesParser.parse(ws, SourceFormat.UV)
        assert any("pypy" in (dep.marker or "") for dep in parsed.direct), "Marker not preserved"


def test_dependency_strings_split_across_lines(make_pyproject, dummy_pyproject_dict):
    """Tests parsing a dependency split across lines (invalid syntax)."""

    content = dummy_pyproject_dict
    content["project"]["dependencies"] = ["requests\n>=2.28.1"]
    file = make_pyproject(content)

    with Workspace(file) as ws:
        ProjectConverter().convert_to_uv(ws)
        (ws.base / "uv.lock").write_text("")

        with pytest.raises(ParsingError, match="Malformed dependency"):
            DependenciesParser.parse(ws, SourceFormat.UV)
