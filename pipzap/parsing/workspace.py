import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Union

from loguru import logger
from typing_extensions import Self

from pipzap.exceptions import ResolutionError
from pipzap.utils.debug import is_debug


@dataclass
class BackupPath:
    fname: str
    keep: bool
    original_path: Optional[Path] = None

    _base_path: Optional[Path] = field(init=False, default=None)

    def with_path(self, base_path: Path, fname: Optional[str] = None) -> Self:
        self._base_path = base_path
        if fname:
            self.fname = fname
        return self

    @property
    def path(self) -> Path:
        if self._base_path is None:
            raise RuntimeError("Attempted to get path of a backup file prior to initialization.")

        return self._base_path / self.fname


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
        extra_backup: Optional[List[BackupPath]] = None,
    ):
        """
        Args:
            source_path: The path to the source file to be processed. Can be a path-like object,
                         or None if no source file is needed.
            no_isolation: Whether to disable the creation of a temp directory to operate in.
            restore_backup: Whether to restore the backup file after the exit.
            extra_backup: Additional files to silently backup from the same dir as source_path.
        """
        self.source_path = Path(source_path) if source_path else None
        self._restore_backup = restore_backup
        self._no_isolation = no_isolation
        self._base: Optional[Path] = None
        self._path: Optional[Path] = None
        self._backup: Optional[BackupPath] = None

        if extra_backup and source_path is None:
            logger.warning("Extra backup files requested, but no source path is provided. Ignoring.")
            extra_backup = []

        extra_backup_files = []
        if self.source_path:
            extra_backup_files = [backup.with_path(self.source_path.parent) for backup in extra_backup or []]

        self._extra_backup_source = [file for file in extra_backup_files if file.path.is_file()]
        self._extra_backup_target: List[BackupPath] = []

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
        return self._backup.path

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

        backup_fname = self._format_backup(self.source_path)
        self._backup = BackupPath(backup_fname, keep=True, original_path=self.source_path)
        self._backup.with_path(self._base)

        logger.debug(f"Backing up (copying) '{self.source_path}' -> '{self._backup.path}'")
        shutil.copyfile(self.source_path, self._backup.path)

        self._extra_backup_target = []
        for extra_backup in self._extra_backup_source:
            target_fname = self._format_backup(extra_backup.path)
            target = BackupPath(target_fname, extra_backup.keep, original_path=extra_backup.path)
            target.with_path(self._base)
            self._extra_backup_target.append(target)

            logger.debug(
                f"Backing up ({'copying' if extra_backup.keep else 'moving'}) "
                f"'{extra_backup.path}' -> '{target.path}'"
            )
            backup_op = shutil.copyfile if extra_backup.keep else shutil.move

            if extra_backup.keep and extra_backup.path == target.path:
                continue

            backup_op(str(extra_backup.path.absolute()), target.path)

        if not self._no_isolation:
            # same path otherwise
            logger.debug(f"Backing up (copying) the target file '{self.source_path}' -> '{self._path}'")
            shutil.copyfile(self.source_path.resolve(), self._path)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exits the context, cleaning up the workspace.

        Removes the temporary directory unless in debug mode.
        """

        if self._restore_backup:
            to_restore = []
            if self._backup:
                to_restore.append(self._backup)

            to_restore.extend(self._extra_backup_target)

            for backup in to_restore:
                if not backup.original_path or not backup.path.exists():
                    continue

                if backup.path == backup.original_path:
                    continue

                logger.debug(f"Restoring backup '{backup.path}' as '{backup.original_path}'")
                shutil.move(str(backup.path.absolute()), backup.original_path)

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
