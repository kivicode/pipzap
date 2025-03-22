import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import toml
from loguru import logger

from pipzap.core.dependencies import Dependency, ProjectDependencies
from pipzap.exceptions import ResolutionError


class DependenciesResolver:
    """Provides dependency resolution by creating and locking a temporary project using UV."""

    def resolve(self, project_deps: ProjectDependencies, python_version: str) -> ProjectDependencies:
        """Resolves dependencies and updates the dependency graph.

        Args:
            project_deps: The project dependencies prior to resolution.
            python_version: The python version constraint for the temporary project.

        Returns:
            A ProjectDependencies instance with an updated dependency graph.

        Raises:
            ResolutionError: An error indicating that uv.lock was not generated.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path("./temp")
            temp_path.mkdir(exist_ok=True)
            # temp_path = Path(temp_dir)

            self._write_pyproject_toml(project_deps.direct, temp_path, python_version)
            self._execute_uv_lock(temp_path)

            lock_file = temp_path / "uv.lock"
            if not lock_file.exists():
                raise ResolutionError("Failed to generate uv.lock")

            graph = self._parse_lock_file(lock_file)
            return ProjectDependencies(direct=project_deps.direct, graph=graph)

    def _write_pyproject_toml(
        self, direct_deps: List[Dependency], output_dir: Path, python_version: str
    ) -> None:
        """Generates a dummy pyproject.toml file for dependency resolution.

        Args:
            direct_deps: A list of direct Dependency instances.
            output_dir: The directory in which the pyproject.toml file is written.
            python_version: The python version constraint for the project.
        """
        dependencies = [dep.to_uv_format() for dep in direct_deps]
        custom_indices = {dep.custom_index for dep in direct_deps if dep.custom_index}
        sources = [{"url": index, "type": "index"} for index in custom_indices] if custom_indices else []

        pyproject: Dict[str, Dict[str, Any]] = {
            "project": {
                "name": "dummy-project",
                "version": "0.1.0",
                "description": "Temporary project for dependency resolution",
                "requires-python": python_version,
                "dependencies": dependencies,
            }
        }

        if sources:
            pyproject["tool"] = {"uv": {"sources": sources}}

        with (output_dir / "pyproject.toml").open("w") as f:
            toml.dump(pyproject, f)

    def _execute_uv_lock(self, directory: Path) -> None:
        """Executes the uv lock command in the specified directory.

        Args:
            directory: The directory where uv lock is executed.

        Raises:
            ResolutionError: An error indicating failure during the uv lock execution.
        """
        cmd = ["uv", "lock", "--directory", str(directory)]

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            if result.stderr:
                logger.debug(f"uv lock log:\n{result.stderr}")
        except subprocess.CalledProcessError as e:
            raise ResolutionError(f"Failed to execute uv lock:\n{e.stderr}")

    @staticmethod
    def _parse_lock_file(lock_file: Path) -> Dict[str, List[str]]:
        """Parses the uv.lock file to build a dependency graph.

        Args:
            lock_file: The path to the uv.lock file.

        Returns:
            A dictionary mapping package names to lists of dependency names.

        Raises:
            ResolutionError: An error indicating that the uv.lock file is invalid.
        """
        try:
            lock_data = toml.load(lock_file)
            graph: Dict[str, List[str]] = {}

            for package in lock_data.get("package", []):
                name = package["name"].lower()
                deps = [dep["name"].lower() for dep in package.get("dependencies", [])]
                graph[name] = deps

            return graph

        except Exception as e:
            raise ResolutionError(f"Invalid uv.lock file: {e}")
