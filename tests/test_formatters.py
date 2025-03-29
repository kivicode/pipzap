from pathlib import Path
from typing import Callable, Dict, Set

import pytest
import tomlkit

from pipzap.core.dependencies import Dependency, ProjectDependencies
from pipzap.core.source_format import SourceFormat
from pipzap.formatting.poetry import PoetryFormatter
from pipzap.formatting.requirements import RequirementsTXTFormatter
from pipzap.formatting.uv import UVFormatter
from pipzap.parsing.converter import ProjectConverter
from pipzap.parsing.parser import DependenciesParser
from pipzap.parsing.workspace import Workspace

DEP_NAME = "requests"
DEP_VER = "2.32.3"


@pytest.fixture
def dummy_workspace(tmp_path):
    class DummyWorkspace:
        def __init__(self, base):
            self.base = base
            self.path = base / "dummy.txt"

        def run(self, cmd, marker, log_filter=None):
            return f"# Auto-generated\n{DEP_NAME}=={DEP_VER}\n"

    return DummyWorkspace(tmp_path)


@pytest.fixture
def proj_deps_uv():
    return ProjectDependencies(
        direct=[Dependency(name=DEP_NAME, pinned_version=DEP_VER)],
        graph={},
        source_format=SourceFormat.UV,
        py_version="3.8",
        uv_pyproject_source={"project": {"dependencies": [f"{DEP_NAME}=={DEP_VER}"]}},
        poetry_pyproject_source=None,
    )


@pytest.fixture
def proj_deps_poetry():
    return ProjectDependencies(
        direct=[Dependency(name=DEP_NAME, pinned_version=DEP_VER)],
        graph={},
        source_format=SourceFormat.POETRY,
        py_version="3.8",
        uv_pyproject_source=None,
        poetry_pyproject_source={"tool": {"poetry": {"dependencies": {DEP_NAME: DEP_VER}}}},
    )


@pytest.mark.parametrize(
    "formatter_cls, expected_content",
    [
        (UVFormatter, f"{DEP_NAME}=={DEP_VER}"),
        (PoetryFormatter, f'{DEP_NAME} = "{DEP_VER}"'),
        (RequirementsTXTFormatter, f"{DEP_NAME}=={DEP_VER}"),
    ],
)
def test_formatters_output(formatter_cls, expected_content, dummy_workspace, proj_deps_uv, proj_deps_poetry):
    """Tests that each formatter produces the expected output."""
    proj_deps = proj_deps_poetry if formatter_cls == PoetryFormatter else proj_deps_uv
    formatter = formatter_cls(dummy_workspace, proj_deps)
    output = formatter.format()

    if formatter_cls == RequirementsTXTFormatter:
        assert expected_content in output
        return

    parsed = tomlkit.parse(output)
    if formatter_cls == UVFormatter:
        assert f"{DEP_NAME}=={DEP_VER}" in parsed["project"]["dependencies"]

    elif formatter_cls == PoetryFormatter:
        assert parsed["tool"]["poetry"]["dependencies"][DEP_NAME] == DEP_VER

    else:
        assert False, f"Test not implemented for {formatter_cls}"


@pytest.fixture
def dummy_poetry_file(make_pyproject: Callable) -> Path:
    content: Dict = {
        "tool": {"poetry": {"dependencies": {"requests": ">=2.28.1", "flask": "2.0.1"}}},
        "project": {"requires-python": "~=3.8"},
    }
    return make_pyproject(content)


@pytest.mark.parametrize(
    "source_fixture,target_format,expected_deps",
    [
        # requirements.txt source
        ("dummy_requirements_txt", "requirements", {"requests", "flask"}),
        ("dummy_requirements_txt", "poetry", {"requests", "flask"}),
        ("dummy_requirements_txt", "uv", {"requests", "flask"}),
        # poetry source
        ("dummy_poetry_file", "requirements", {"requests", "flask"}),
        ("dummy_poetry_file", "poetry", {"requests", "flask"}),
        ("dummy_poetry_file", "uv", {"requests", "flask"}),
        # uv source
        ("dummy_pyproject", "requirements", {"requests"}),
        ("dummy_pyproject", "poetry", {"requests"}),
        ("dummy_pyproject", "uv", {"requests"}),
    ],
)
def test_conversion_pairs(request, source_fixture: str, target_format: str, expected_deps: Set[str]) -> None:
    source_file = request.getfixturevalue(source_fixture)

    formatters_map = {
        "requirements": RequirementsTXTFormatter,
        "poetry": PoetryFormatter,
        "uv": UVFormatter,
    }

    with Workspace(source_file) as ws:
        converter = ProjectConverter("3.8")
        src_format = converter.convert_to_uv(ws)
        parsed = DependenciesParser.parse(ws, src_format)

        formatter_cls = formatters_map.get(target_format)
        if not formatter_cls:
            assert False, f"Test not implemented for {target_format}"

        output = formatter_cls(ws, parsed).format()  # type: ignore [abstract]

    for dep in expected_deps:
        assert dep in output, f"Missing dependency {dep} in conversion {source_fixture} -> {target_format}"
