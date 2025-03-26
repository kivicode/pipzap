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

REQUIREMENTS_ENTRIES = set(REQUIREMENTS_DIR.rglob("*.txt")) - set(REQUIREMENTS_DIR.rglob("failing/**/*.txt"))


def get_package_names(lock_data: dict) -> Set[str]:
    return {p["name"] for p in lock_data["package"]} - {ProjectConverter.DUMMY_PROJECT_NAME}


@pytest.mark.parametrize("input_file", REQUIREMENTS_ENTRIES)
def test_dependency_pruning(input_file):
    with Workspace(input_file) as workspace:
        # FIXME: Specify per-test python versions?
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

        assert pruned_packages == full_packages, (
            f"Dependency mismatch for {input_file.name}: "
            f"Missing: {full_packages - pruned_packages} "
            f"Extra: {pruned_packages - full_packages}"
        )
