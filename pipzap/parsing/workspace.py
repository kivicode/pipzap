import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, List, Optional, Union

from loguru import logger
from typing_extensions import Self

from pipzap.exceptions import ResolutionError
from pipzap.utils.debug import is_debug


class Workspace:
    """A context manager for creating and managing temporary workspaces for dependency processing.

    Handles the creation of temporary directories, file copying, command execution,
    and cleanup for dependency management operations.
    """

    def __init__(
        self,
        source_path: Union[Path, str, None],
        no_isolation: bool = False,
        restore_backup: bool = True,
        extra_backup_filenames: Optional[List[str]] = None,
    ):
        """
        Args:
            source_path: The path to the source file to be processed. Can be a path-like object,
                         or None if no source file is needed.
            no_isolation: Whether to disable the creation of a temp directory to operate in.
            restore_backup: Whether to restore the backup file after the exit.
            extra_backup_filenames: Additional files to silently backup from the same dir as source_path.
        """
        self.source_path = Path(source_path) if source_path else None
        self._restore_backup = restore_backup
        self._no_isolation = no_isolation
        self._base: Optional[Path] = None
        self._path: Optional[Path] = None
        self._backup: Optional[Path] = None

        if extra_backup_filenames and source_path is None:
            logger.warning("Extra backup files requested, but no source path is provided. Ignoring.")
            extra_backup_filenames = []

        extra_backup_files = []
        if self.source_path:
            extra_backup_files = [self.source_path.parent / fname for fname in extra_backup_filenames or []]

        self._extra_backup_source = [file for file in extra_backup_files if file.is_file()]
        self._extra_backup_target: List[Path] = []

        if self.source_path and self._no_isolation and not self._restore_backup:
            raise ResourceWarning(
                "Creating a non-isolated workspace with the backup disabled "
                "is extremely dangerous and is likely to result in the loss of data."
            )

    @property
    def base(self) -> Path:
        if not self._base:
            raise RuntimeError("Unable to get Workspace.base: context not entered.")
        return self._base

    @property
    def path(self) -> Path:
        if not self._path:
            raise RuntimeError("Unable to get Workspace.path: context not entered.")
        return self._path

    @property
    def backup(self) -> Path:
        if not self._backup:
            raise RuntimeError("Unable to get Workspace.backup: context not entered or backup not used.")
        return self._backup

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
        if self._no_isolation and self.source_path:
            self._base = self.source_path.parent

        elif not is_debug():
            self._base = Path(tempfile.mkdtemp())

        else:
            self._base = Path("./pipzap-temp")

            if self._base.exists():
                shutil.rmtree(self._base)
            self._base.mkdir(parents=True)

        logger.debug(f"Entered workspace: '{self._base}' from '{self.source_path}' ({self._no_isolation =})")

        if not self.source_path:
            logger.debug("No source path provided")
            return self

        self._path = self._base / self.source_path.name
        self._backup = self._base / self._format_backup(self.source_path)

        logger.debug(f"Backing up (copying) '{self.source_path}' -> '{self._path}'")
        shutil.copyfile(self.source_path, self._backup)

        self._extra_backup_target = []
        for extra_backup in self._extra_backup_source:
            target = self._base / self._format_backup(extra_backup)
            self._extra_backup_target.append(target)

            logger.debug(f"Backing up (moving) '{extra_backup}' -> '{target}'")
            shutil.move(str(extra_backup.absolute()), target)

        if not self._no_isolation:
            # same path otherwise
            logger.debug(f"Backing up (copying) '{self.source_path}' -> '{self._path}'")
            shutil.copyfile(self.source_path, self._path)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exits the context, cleaning up the workspace.

        Removes the temporary directory unless in debug mode.
        """

        if self._restore_backup:
            restore_from = [self._backup] + self._extra_backup_target
            restore_to = [self.source_path] + self._extra_backup_source

            for source, target in zip(restore_from, restore_to):
                if not source or not target or source == target:
                    continue

                logger.debug(f"Restoring backup '{source}' as '{target}'")
                shutil.move(str(source.absolute()), target)

        if self.base and not self._no_isolation and not is_debug():
            logger.debug(f"Removing base: {self.base}")
            shutil.rmtree(self.base)

        logger.debug(f"Exited workspace: {self.base}")

    def run(self, cmd: List[str], marker: str, log_filter: Callable[[str], bool] = lambda l: True) -> str:
        """Executes the specified (shell) command in the workspace directory and captures its output.

        Args:
            cmd: List of command arguments to execute
            marker: A string identifier for the command (used in error messages).
            log_filter: A callable determining whether the log level inference should happen for a given line.

        Raises:
            ResolutionError: If the command fails to execute successfully

        Returns:
            stdout string of the command.

        Notes:
            - Command output is logged at debug level
            - stderr is captured and included in any error messages
        """
        try:
            inner_logger = logger.opt(depth=1)

            logger.debug(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=(self.base))
            for line in str(result.stderr).splitlines():
                line = line.strip()

                if not line:
                    continue

                log_level = inner_logger.debug
                tokens = set(re.split(r"\W+", line.lower()))
                padding = " " * 7

                if log_filter(line):
                    if tokens & {"warning", "warn"}:
                        log_level = inner_logger.warning

                    if tokens & {"error"}:
                        log_level = inner_logger.error

                    if log_level != inner_logger.debug:
                        padding = f"[{cmd[0][: len(padding)]}]".rjust(len(padding))

                log_level(f"{padding} >>> {line}", depth=1)

            return result.stdout

        except subprocess.CalledProcessError as e:
            raise ResolutionError(f"Failed to execute {marker}:\n{e.stderr}") from e

    @staticmethod
    def _format_backup(file: Path) -> str:
        return f"__pipzap-{file.stem}.backup{file.suffix}"
