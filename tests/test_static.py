from io import StringIO
from pathlib import Path
from typing import Set

import pytest
from ruamel.yaml import YAML

from pipzap.core.pruner import DependencyPruner
from pipzap.core.source_format import SourceFormat
from pipzap.formatting.conda import CondaFormatter
from pipzap.formatting.uv import UVFormatter
from pipzap.parsing.converter import ProjectConverter
from pipzap.parsing.parser import DependenciesParser
from pipzap.parsing.workspace import Workspace
from pipzap.utils.io import read_toml

DATA_DIR = Path("tests/data")
REQUIREMENTS_DIR = DATA_DIR / "requirements"
POETRY_DIR = DATA_DIR / "poetry"
CONDA_DIR = DATA_DIR / "conda"

REQUIREMENTS_ENTRIES = set(REQUIREMENTS_DIR.rglob("*.txt")) - set(REQUIREMENTS_DIR.rglob("failing/**/*.txt"))
POETRY_ENTRIES = set(POETRY_DIR.rglob("*.toml"))
CONDA_ENTRIES = set(CONDA_DIR.rglob("*.yml")) | set(CONDA_DIR.rglob("*.yaml"))


STATIC_TEST_CASES_SET = REQUIREMENTS_ENTRIES  # | POETRY_ENTRIES
STATIC_TEST_CASES = sorted(STATIC_TEST_CASES_SET)
STATIC_TEST_IDS = [str(file) for file in STATIC_TEST_CASES]

CONDA_TEST_CASES = sorted(CONDA_ENTRIES)
CONDA_TEST_IDS = [str(file) for file in CONDA_TEST_CASES]


def get_package_names(lock_data: dict) -> Set[str]:
    return {p["name"] for p in lock_data["package"]}


@pytest.mark.parametrize("input_file", STATIC_TEST_CASES, ids=STATIC_TEST_IDS)
def test_dependency_pruning(input_file):
    with Workspace(input_file) as workspace:
        # TODO: Specify per-test python versions?
        source_format = ProjectConverter("3.10").convert_to_uv(workspace)
        parsed = DependenciesParser.parse(workspace, source_format)
        pruned = DependencyPruner.prune(parsed)
        full_lock = read_toml(workspace.base / "uv.lock")

        output_path = workspace.base / "pruned" / "pyproject.toml"
        output_path.parent.mkdir(exist_ok=True)
        output_path.write_text(UVFormatter(workspace, pruned).format())

        with Workspace(output_path) as inner_workspace:
            inner_workspace.run(["uv", "lock"], ".")
            pruned_lock = read_toml(inner_workspace.base / "uv.lock")

        full_packages = get_package_names(full_lock)
        pruned_packages = get_package_names(pruned_lock)

        missing = full_packages - pruned_packages
        assert len(missing) == 0, f"Dependency mismatch for {input_file.name}. Missing: {missing} "


@pytest.mark.parametrize("input_file", CONDA_TEST_CASES, ids=CONDA_TEST_IDS)
def test_conda_dependency_pruning(input_file):
    """Test conda environment.yml files are processed correctly end-to-end."""

    with Workspace(input_file) as workspace:
        # Don't pass python version - let it extract from the conda file
        source_format = ProjectConverter().convert_to_uv(workspace)
        assert source_format == SourceFormat.CONDA

        parsed = DependenciesParser.parse(workspace, source_format)
        pruned = DependencyPruner.prune(parsed, preserve_all=True, workspace=workspace)
        full_lock = read_toml(workspace.base / "uv.lock")

        output_content = CondaFormatter(workspace, pruned).format()
        print(output_content)

        yaml = YAML()
        output_data = yaml.load(StringIO(output_content))

        pip_deps = []
        for dep in output_data.get("dependencies", []):
            if isinstance(dep, dict) and "pip" in dep:
                pip_deps = dep["pip"]
                break

        assert len(pip_deps) > 0, "No pip dependencies in output"
        assert "name" in output_data, "Conda environment name missing"
        assert "dependencies" in output_data, "Conda dependencies section missing"

        pruned_conda_path = workspace.base / "pruned" / "environment.yml"
        pruned_conda_path.parent.mkdir(exist_ok=True)
        pruned_conda_path.write_text(output_content)

        with Workspace(pruned_conda_path) as inner_workspace:
            inner_format = ProjectConverter().convert_to_uv(inner_workspace)
            assert inner_format == SourceFormat.CONDA
            pruned_lock = read_toml(inner_workspace.base / "uv.lock")

        full_packages = get_package_names(full_lock) - {"generated-project"}
        pruned_packages = get_package_names(pruned_lock) - {"generated-project"}

        missing = full_packages - pruned_packages
        assert len(missing) == 0, f"Dependency mismatch for {input_file.name}. Missing: {missing}"
