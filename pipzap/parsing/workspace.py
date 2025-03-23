import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Union

from loguru import logger
from typing_extensions import Self

from pipzap.exceptions import ResolutionError
from pipzap.utils.debug import is_debug


class Workspace:
    """A context manager for creating and managing temporary workspaces for dependency processing.

    Handles the creation of temporary directories, file copying, command execution,
    and cleanup for dependency management operations.
    """

    def __init__(self, source_path: Union[(Path, str, None)]):
        """
        Args:
            source_path: The path to the source file to be processed. Can be a path-like object,
                         or None if no source file is needed.
        """
        self.source_path = Path(source_path) if source_path else None
        self.base = None
        self.path = None

    def __enter__(self) -> Self:
        """Enters the context, setting up the temporary workspace.

        Creates a temporary directory (or uses a fixed location in debug mode),
        copies the source file if provided, and sets up the working path.

        Returns:
            The initialized Workspace instance.

        Notes:
            - In normal mode, creates a random temporary directory
            - In debug mode, uses `./pipzap-temp` and ensures it's clean
        """
        if not is_debug():
            self.base = Path(tempfile.mkdtemp())
        else:
            self.base = Path("./pipzap-temp")
            if self.base.exists():
                shutil.rmtree(self.base)
            self.base.mkdir(parents=True)
        logger.debug(f"Entered workspace: {self.base}")
        self.path = self.base
        if self.source_path:
            self.path /= self.source_path.name
            shutil.copyfile(self.source_path, self.path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exits the context, cleaning up the workspace.

        Removes the temporary directory unless in debug mode.
        """
        if self.base:
            if not is_debug():
                shutil.rmtree(self.base)
        logger.debug(f"Exited workspace: {self.base}")

    def run(self, cmd: List[str], marker: str):
        """Executes the specified (shell) command in the workspace directory and captures its output.

        Args:
            cmd: List of command arguments to execute
            marker: A string identifier for the command (used in error messages).

        Raises:
            ResolutionError: If the command fails to execute successfully

        Notes:
            - Command output is logged at debug level
            - stderr is captured and included in any error messages
        """
        try:
            logger.debug(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=(self.base))
            for line in str(result.stderr).splitlines():
                line = line.strip()
                if line:
                    logger.debug(f"       >>> {line.strip()}")

        except subprocess.CalledProcessError as e:
            raise ResolutionError(f"Failed to execute {marker}:\n{e.stderr}") from e
