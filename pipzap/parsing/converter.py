import sys
from typing import Optional

from loguru import logger

from pipzap.core.source_format import SourceFormat
from pipzap.exceptions import ResolutionError
from pipzap.parsing.workspace import Workspace
from pipzap.utils.io import read_toml, write_toml


class ProjectConverter:
    """Converts an existing dependencies specification file into a common `uv` format one."""

    DUMMY_PROJECT_NAME = "generated-project"

    def __init__(self, py_version: Optional[str] = None):
        """
        Args:
            py_version: Version constraint of Python to use. Takes from the current env if None. Default: None.
                        Adds a `~=` specifier if nothing else is provided.
        """
        if py_version and py_version[0].isdigit():
            py_version = f"~={py_version}"

        self.py_version = py_version

    def convert_to_uv(self, workspace: Workspace) -> SourceFormat:
        """Performs the source-agnostic conversion of a dependencies file into the `uv` format.

        May operate in-place for certain source formats, but only within the workspace.

        Guaranteed to build the `uv.lock` file long with a `pyproject.toml`.

        Args:
            workspace: Workspace containing the original dependencies file.

        Returns:
            The source file format identified.
        """
        deps_format = SourceFormat.detect_format(workspace.path)
        logger.debug(f"Identified source format as '{deps_format.value}'")

        if deps_format == SourceFormat.REQS:
            self._convert_from_requirements(workspace)

        elif deps_format == SourceFormat.POETRY:
            self._convert_from_poetry(workspace)

        elif deps_format == SourceFormat.UV:
            self._convert_from_uv(workspace)

        else:
            raise NotImplementedError(f"Unknown source type: {deps_format}")

        self._log_intermediate(workspace)
        return deps_format

    def _convert_from_requirements(self, workspace: Workspace) -> None:
        """Implements the requirements.txt -> pyproject.toml conversion.

        Relies on the `uvx migrate-to-uv` tool.
        """
        workspace.path.rename(workspace.base / "requirements.txt")

        if self.py_version is None:
            v = sys.version_info
            self.py_version = f"~={v.major}.{v.minor}.{v.micro}"
            logger.warning(
                f"No --python-version provided. "  #
                f"Defaulting to the current environment: {self.py_version}"
            )

        workspace.run(
            ["uvx", "migrate-to-uv", "--package-manager", "pip"],
            "conversion",
            log_filter=lambda line: "No `requires-python` value found in the workspace." not in line,
        )

        path = workspace.base / "pyproject.toml"
        pyproject = read_toml(path)
        pyproject["project"]["name"] = self.DUMMY_PROJECT_NAME
        write_toml(pyproject, path)

        if not self._try_inject_python_version(workspace):
            raise ResolutionError("An explicit python version must be provided for requirements.txt projects")

        workspace.run(["uv", "lock"], "resolution")

    def _convert_from_poetry(self, workspace: Workspace):
        """Implements the pyproject.toml (poetry) -> pyproject.toml (uv) conversion.

        Relies on the `uvx migrate-to-uv` tool.
        """
        workspace.run(
            ["uvx", "migrate-to-uv", "--keep-current-data", "--skip-lock", "--package-manager", "poetry"],
            "conversion",
        )

        self._try_inject_python_version(workspace)
        workspace.run(["uv", "lock"], "resolution")

        pyproject_path = workspace.base / "pyproject.toml"
        pyproject = read_toml(pyproject_path)
        pyproject["tool"] = {key: val for key, val in pyproject["tool"].items() if key != "poetry"}
        write_toml(pyproject, pyproject_path)

    def _convert_from_uv(self, workspace: Workspace):
        """Pass-though uv-to-uv conversion. Makes sure to perform locking if not done yet."""
        if (workspace.base / "uv.lock").is_file():
            return

        self._try_inject_python_version(workspace)
        workspace.run(["uv", "lock"], "resolution")

    def _try_inject_python_version(self, workspace: Workspace) -> bool:
        """Attempts to inject a `project.requires-python` field into the `pyproject.toml`.

        If not `self.py_version` is specified - attempts to find a version in the existing pyproject.

        Returns:
            Whether it has managed to inject the python version field.
        """
        fallback: Optional[str] = None
        potential_pyproject_path = workspace.base / "pyproject.toml"

        if potential_pyproject_path.is_file():
            pyproject = read_toml(potential_pyproject_path)
            uv_version = pyproject.get("project", {}).get("requires-python")
            poetry_version = pyproject.get("tool", {}).get("poetry", {}).get("dependencies", {}).get("python")
            fallback = uv_version or poetry_version

        version = self.py_version or fallback

        if version is None:
            return False

        path = workspace.base / "pyproject.toml"
        pyproject = read_toml(path)
        pyproject["project"]["requires-python"] = self.py_version or fallback
        write_toml(pyproject, path)

        return True

    def _log_intermediate(self, workspace: Workspace) -> None:
        content = (workspace.base / "pyproject.toml").read_text()
        logger.debug(f"Intermediate UV pyproject:\n{content}")
