import pytest
import tomlkit

from pipzap.core.dependencies import Dependency, ProjectDependencies
from pipzap.core.source_format import SourceFormat
from pipzap.formatting.poetry import PoetryFormatter
from pipzap.formatting.requirements import RequirementsTXTFormatter
from pipzap.formatting.uv import UVFormatter

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
