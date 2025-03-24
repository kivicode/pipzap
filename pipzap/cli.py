import argparse
import sys
from pathlib import Path
from typing import Dict, Optional, Type

from loguru import logger

from pipzap import __uv_version__ as uv_version
from pipzap import __version__ as zap_version
from pipzap.core import DependencyPruner, SourceType
from pipzap.formatting import PoetryFormatter, RequirementsTXTFormatter, UVFormatter
from pipzap.formatting.base import DependenciesFormatter
from pipzap.parsing import DependenciesParser, ProjectConverter, Workspace

KNOWN_FORMATTERS: Dict[SourceType, Type[DependenciesFormatter]] = {
    SourceType.POETRY: PoetryFormatter,
    SourceType.REQS: RequirementsTXTFormatter,
    SourceType.UV: UVFormatter,
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
            logger.add(
                sys.stderr,
                format="<level>• {message}</level>",
                level="INFO",
            )

        logger.debug(f"Starting PipZap v{zap_version} (uv v{uv_version})")

        if args.format is not None:
            args.format = SourceType(args.format)

        logger.success(f"Starting processing {args.file}")

        try:
            with Workspace(args.file) as workspace:
                logger.debug(f"Source data:\n{workspace.path.read_text()}")

                source_format = ProjectConverter(args.python_version).convert_to_uv(workspace)
                parsed = DependenciesParser.parse(workspace)
                pruned = DependencyPruner.prune(parsed)

                result = KNOWN_FORMATTERS[args.format or source_format](workspace, pruned).format()

            if not args.output:
                logger.success(f"Result:")
                print("\n" + result)
                return

            if args.output.is_file() and not args.force:
                raise ValueError(
                    f"Output file {args.output} already exists. Specify --force to allow overriding"
                )

            args.output.write_text(result)
            logger.success(f"Results written to {args.output}")

        except Exception as err:
            if args.verbose:
                logger.exception(err)
            else:
                logger.error(err)

            if do_raise:
                raise err

    def _setup_parser(self):
        self.parser.add_argument("file", type=Path, help="Path to the dependency file")
        self.parser.add_argument("-v", "--verbose", action="store_true", help="Produce richer logs")
        self.parser.add_argument(
            "-o",
            "--output",
            type=Path,
            default=None,
            help="Output file (defaults to stdout)",
        )
        self.parser.add_argument("--force", action="store_true", help="Allow overriding existing files")
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
