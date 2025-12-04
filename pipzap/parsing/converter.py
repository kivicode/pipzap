import sys
from typing import List, Optional

from loguru import logger
from ruamel.yaml import YAML

from pipzap.core.source_format import SourceFormat
from pipzap.exceptions import ParsingError, ResolutionError
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
            # Ensure we have at least major.minor.patch for ~= to work correctly
            # ~=3.10 allows 3.11+, but ~=3.10.0 only allows 3.10.x
            parts = py_version.split(".")
            if len(parts) == 2:
                py_version = f"{py_version}.0"
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

        elif deps_format == SourceFormat.CONDA:
            self._convert_from_conda(workspace)

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
            ["uvx", "migrate-to-uv", "--package-manager", "pip", "--skip-lock"],
            "conversion",
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
        pyproject["project"]["requires-python"] = version
        write_toml(pyproject, path)

        return True

    def _convert_from_conda(self, workspace: Workspace) -> None:
        """Implements the conda environment.yml -> pyproject.toml conversion.

        Extracts pip dependencies from the YAML file and delegates to requirements.txt conversion.
        """
        # Use source_path for -r resolution since referenced files are relative to original location
        original_path = workspace.source_path or workspace.path
        pip_deps = self._extract_pip_deps_from_conda(workspace.path, original_path)

        if not pip_deps:
            raise ParsingError(
                "No pip dependencies found in conda environment file. "
                "Ensure your environment.yml has a 'dependencies' section with a 'pip' subsection."
            )

        logger.info(f"Found {len(pip_deps)} pip dependencies in conda environment file")

        if self.py_version is None:
            py_version = self._extract_python_version_from_conda(workspace.path)
            if py_version:
                self.py_version = py_version
                logger.info(f"Using Python version from conda file: {self.py_version}")

        # Write pip deps as requirements.txt and update workspace path
        reqs_path = workspace.base / "requirements.txt"
        reqs_path.write_text("\n".join(pip_deps))
        workspace._path = reqs_path

        self._convert_from_requirements(workspace)

    def _extract_pip_deps_from_conda(self, yaml_path, original_path=None) -> List[str]:
        """Extract pip dependencies from a conda environment YAML file.

        Args:
            yaml_path: Path to the environment.yml file.
            original_path: Original path before workspace copy (for resolving -r references).

        Returns:
            List of pip requirement strings.
        """
        yaml = YAML()
        with open(yaml_path) as f:
            data = yaml.load(f)

        if not data or "dependencies" not in data:
            return []

        # Use original path for -r resolution if available
        resolve_base = (original_path or yaml_path).parent

        pip_deps = []
        for dep in data["dependencies"]:
            if not isinstance(dep, dict) or "pip" not in dep:
                continue

            pip_section = dep["pip"]
            if not isinstance(pip_section, list):
                continue

            for pip_dep in pip_section:
                if not isinstance(pip_dep, str):
                    continue

                # Handle -r requirements.txt references
                if pip_dep.startswith("-r ") or pip_dep.startswith("-r\t"):
                    req_file = pip_dep[3:].strip()
                    req_path = resolve_base / req_file
                    if req_path.is_file():
                        logger.debug(f"Unpacking requirements from: {req_path}")
                        for line in req_path.read_text().splitlines():
                            line = line.strip()
                            if line and not line.startswith("#") and not line.startswith("-"):
                                pip_deps.append(line)
                    else:
                        logger.warning(f"Cannot unpack -r reference, file not found: {req_path}")
                    continue

                # Skip other flags like -e, --index-url, etc.
                if pip_dep.startswith("-"):
                    continue

                pip_deps.append(pip_dep)

        return pip_deps

    def _extract_python_version_from_conda(self, yaml_path) -> Optional[str]:
        """Extract Python version constraint from conda dependencies.

        Args:
            yaml_path: Path to the environment.yml file.

        Returns:
            Python version string if found, None otherwise.
        """
        yaml = YAML()
        with open(yaml_path) as f:
            data = yaml.load(f)

        if not data or "dependencies" not in data:
            return None

        for dep in data["dependencies"]:
            if not isinstance(dep, str) or not dep.startswith("python"):
                continue

            # Parse python version spec like "python=3.10" or "python>=3.8"
            # Also handle conda format "python=3.12.9=h5148396_0" (with build hash)
            dep = dep.strip()
            if "=" not in dep:
                continue

            # Handle python=3.10 or python==3.10 or python>=3.10
            for sep in ["==", ">=", "<=", "=", ">"]:
                if sep not in dep:
                    continue

                version = dep.split(sep, 1)[1].strip()
                # Strip conda build hash (e.g., "3.12.9=h5148396_0" -> "3.12.9")
                # Look for '=' that is not part of '==' or '>=' or '<='
                parts_by_eq = version.split("=")
                if len(parts_by_eq) > 1 and parts_by_eq[0] and parts_by_eq[0][0].isdigit():
                    version = parts_by_eq[0]

                # Normalize to ~= format
                parts = version.split(".")
                if len(parts) == 2:
                    version = f"{version}.0"

                return f"~={version}"

        return None

    def _log_intermediate(self, workspace: Workspace) -> None:
        content = (workspace.base / "pyproject.toml").read_text()
        logger.debug(f"Intermediate UV pyproject:\n{content}")
