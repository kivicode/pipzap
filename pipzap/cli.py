import argparse
import sys
from pathlib import Path
from typing import Dict, Optional, Set, Type

from loguru import logger

from pipzap import __uv_version__ as uv_version
from pipzap import __version__ as zap_version
from pipzap.core import DependencyPruner, SourceFormat
from pipzap.discovery import discover_dependencies
from pipzap.formatting import CondaFormatter, PoetryFormatter, RequirementsTXTFormatter, UVFormatter
from pipzap.formatting.base import DependenciesFormatter
from pipzap.parsing import DependenciesParser, ProjectConverter, Workspace
from pipzap.parsing.workspace import BackupPath

KNOWN_FORMATTERS: Dict[SourceFormat, Type[DependenciesFormatter]] = {
    SourceFormat.POETRY: PoetryFormatter,
    SourceFormat.REQS: RequirementsTXTFormatter,
    SourceFormat.UV: UVFormatter,
    SourceFormat.CONDA: CondaFormatter,
}


class PipZapCLI:
    def __init__(self) -> None:
        self.parser = argparse.ArgumentParser(
            description="Dependency pruning and merging tool",
            epilog=zap_version,
        )
        self._setup_parser()

    def run(self, do_raise: bool = False, args: Optional[argparse.Namespace] = None) -> None:
        args = args or self.parser.parse_args()

        if not args.verbose:
            logger.remove()
            logger.add(sys.stderr, format="<level>• {message}</level>", level="INFO")

        version_level = logger.debug if not args.version else logger.info
        version_level(f"Starting PipZap v{zap_version} (uv v{uv_version})")

        if args.version:
            return

        if not args.file:
            self.parser.error("The following argument is required: file")

        scan_path: Optional[Path] = None
        if args.discover:
            scan_path = args.file
            if scan_path and scan_path.is_dir():
                potential_files = [
                    scan_path / "requirements.txt",
                    scan_path / "pyproject.toml",
                ]
                existing_file = next((f for f in potential_files if f.exists()), None)
                args.file = existing_file
            else:
                scan_path = args.file.parent

        if args.format is not None:
            args.format = SourceFormat(args.format)

        try:
            if args.output and args.output.is_file() and not args.override:
                raise ValueError(
                    f"Output file {args.output} already exists. Specify --override to allow overriding",
                )

            discovered_packages: Optional[Set[str]] = None
            if args.discover:
                if not scan_path:
                    raise ValueError("Discovery mode requires a valid scan path")

                discovered_packages = discover_dependencies(scan_path)

                if args.file is None:
                    temp_reqs_path = scan_path / "requirements-discovered.txt"
                    temp_reqs_path.write_text("\n".join(sorted(discovered_packages)))
                    args.file = temp_reqs_path
                    logger.info("No source file found, using discovered packages only")

            logger.success(f"Starting processing {args.file}")

            to_backup = [
                BackupPath("uv.lock", keep=False),
                BackupPath("requirements.txt", keep=True),
                BackupPath("pyproject.toml", keep=True),
            ]

            with Workspace(args.file, args.no_isolation, extra_backup=to_backup) as workspace:
                logger.debug(f"Source data:\n{workspace.path.read_text()}")

                source_format = ProjectConverter(args.python_version).convert_to_uv(workspace)
                parsed = DependenciesParser.parse(workspace, source_format)
                pruned = DependencyPruner.prune(
                    parsed,
                    args.keep,
                    preserve_all=args.preserve_all,
                    workspace=workspace,
                )

                if discovered_packages:
                    original_count = len(pruned.direct)
                    pruned.direct = [dep for dep in pruned.direct if dep.name.lower() in discovered_packages]
                    filtered_count = original_count - len(pruned.direct)

                    if filtered_count > 0:
                        if args.verbose:
                            excluded = original_count - len(pruned.direct)
                            logger.warning(f"Excluded {excluded} packages not found in source code")
                        else:
                            logger.info(f"Excluded {filtered_count} unused packages")

                result = KNOWN_FORMATTERS[args.format or source_format](workspace, pruned).format()

            if not args.output:
                logger.success("Result:")
                print("\n" + result)
                return

            args.output.write_text(result)
            logger.success(f"Results written to {args.output}")

            if args.discover and scan_path:
                temp_reqs_path = scan_path / "requirements-discovered.txt"
                if temp_reqs_path.exists():
                    temp_reqs_path.unlink()
                    logger.debug("Cleaned up temporary requirements file")

        except Exception as err:
            if args.verbose:
                logger.exception(err)
            else:
                logger.error(err)

            if do_raise:
                raise err

    def _setup_parser(self):
        self.parser.add_argument("file", type=Path, nargs="?", help="Path to the dependency file")
        self.parser.add_argument("-v", "--verbose", action="store_true", help="Produce richer logs")
        self.parser.add_argument(
            "-o",
            "--output",
            type=Path,
            default=None,
            help="Output file (defaults to stdout)",
        )
        self.parser.add_argument("--override", action="store_true", help="Allow overriding existing files")
        self.parser.add_argument(
            "--no-isolation",
            action="store_true",
            help="Don't isolate the resolution environment",
        )
        self.parser.add_argument(
            "-f",
            "--format",
            type=str,
            choices=[f.name.lower() for f in KNOWN_FORMATTERS],
            help="Output format for dependency list (defaults to the same as input)",
        )
        self.parser.add_argument(
            "-p",
            "--python-version",
            type=str,
            default=None,
            help="Python version (required for requirements.txt)",
        )
        self.parser.add_argument(
            "-k",
            "--keep",
            type=str,
            nargs="+",
            metavar="PACKAGE_NAME",
            help="Not prune this package",
        )
        self.parser.add_argument(
            "-V",
            "--version",
            action="store_true",
            help="Show the version of pipzap",
        )
        self.parser.add_argument(
            "-d",
            "--discover",
            action="store_true",
            help="Discover dependencies by scanning Python source files with pipreqs",
        )
        self.parser.add_argument(
            "--preserve-all",
            action="store_true",
            help="Re-check and add back any dependencies that would be missing after pruning",
        )
