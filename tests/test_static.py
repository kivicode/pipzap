from pathlib import Path
from typing import Set

import pytest

from pipzap.core.pruner import DependencyPruner
from pipzap.formatting.uv import UVFormatter
from pipzap.parsing.converter import ProjectConverter
from pipzap.parsing.parser import DependenciesParser
from pipzap.parsing.workspace import Workspace
from pipzap.utils.io import read_toml

DATA_DIR = Path("tests/data")
REQUIREMENTS_DIR = DATA_DIR / "requirements"
POETRY_DIR = DATA_DIR / "poetry"

REQUIREMENTS_ENTRIES = set(REQUIREMENTS_DIR.rglob("*.txt")) - set(REQUIREMENTS_DIR.rglob("failing/**/*.txt"))
POETRY_ENTRIES = set(POETRY_DIR.rglob("*.toml"))


STATIC_TEST_CASES_SET = REQUIREMENTS_ENTRIES  # | POETRY_ENTRIES
STATIC_TEST_CASES = sorted(STATIC_TEST_CASES_SET)
STATIC_TEST_IDS = [str(file) for file in STATIC_TEST_CASES]


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
