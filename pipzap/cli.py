import argparse
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

import toml
from loguru import logger

from pipzap.core.dependencies import Dependency
from pipzap.core.pruner import DependencyPruner, KnownParsersT
from pipzap.exceptions import DependencyError
from pipzap.formatters import PoetryFormatter, RequirementsFormatter, UVFormatter
from pipzap.formatters.base import DependencyFormatter
from pipzap.parsers import PoetryTomlParser, RequirementsTxtParser, UVTomlParser
from pipzap.parsers.base import DependencyParser

KNOWN_PARSERS = {
    "requirements-txt": RequirementsTxtParser(),
    "uv-toml": UVTomlParser(),
    "poetry-toml": PoetryTomlParser(),
}

KNOWN_FORMATTERS = {
    "requirements": RequirementsFormatter(),
    "poetry": PoetryFormatter(),
    "uv": UVFormatter(),
}


class PipZapCLI:
    def __init__(self) -> None:
        self.parser = argparse.ArgumentParser(description="Dependency pruning and merging tool")
        self.subparsers = self.parser.add_subparsers(dest="command", help="Available commands")

        self.parser.add_argument("-v", "--verbose", action="store_true", help="Produce richer logs")
        self._setup_prune_command()
        self._setup_merge_prune_command()

    def run(self) -> None:
        args = self.parser.parse_args()
        if not args.command:
            self.parser.print_help()
            sys.exit(1)

        if not args.verbose:
            logger.remove()
            logger.add(
                sys.stderr,
                format="<level>• {level: <7}</level> | <level>{message}</level>",
                level="INFO",
            )

        try:
            if args.command == "prune":
                self._handle_prune(args.file, args.python_version, args.output, args.format)

            elif args.command == "merge-prune":
                self._handle_merge_prune(args.files, args.python_version, args.output, args.format)

            else:
                raise NotImplementedError(f"Unknown command: {args.command}")

        except Exception as err:
            if args.verbose:
                logger.exception(err)
            else:
                logger.error(err)

    def _setup_prune_command(self) -> None:
        prune_parser = self.subparsers.add_parser("prune", help="Prune redundant dependencies from a file")
        prune_parser.add_argument("file", type=Path, help="Path to the dependency file")
        self._add_common_args(prune_parser)

    def _setup_merge_prune_command(self) -> None:
        merge_parser = self.subparsers.add_parser(
            "merge-prune", help="Merge and prune multiple dependency files"
        )
        merge_parser.add_argument("files", nargs="+", type=Path, help="Paths to dependency files")
        self._add_common_args(merge_parser)

    def _add_common_args(self, parser: argparse.ArgumentParser):
        parser.add_argument(
            "-p",
            "--python-version",
            type=str,
            default=None,
            help="Python version (required for requirements.txt)",
        )
        parser.add_argument(
            "-o",
            "--output",
            type=Path,
            default=None,
            help="Output file (defaults to stdout)",
        )
        parser.add_argument(
            "-f",
            "--format",
            type=str,
            choices=list(KNOWN_FORMATTERS),
            default="requirements",
            help="Output format for dependency list.",
        )

    def _detect_format(self, file_path: Path) -> KnownParsersT:
        if file_path.name == "requirements.txt":
            return "requirements-txt"

        if file_path.name != "pyproject.toml":
            raise DependencyError(f"Cannot determine format of {file_path}")

        with file_path.open("r") as f:
            data = toml.load(f)

        if "project" in data:
            return "uv-toml"

        if "tool" in data and "poetry" in data["tool"]:
            return "poetry-toml"

        raise DependencyError(f"Invalid format of {file_path}")

    def _get_parser(self, format_type: str) -> DependencyParser:
        parser = KNOWN_PARSERS.get(format_type)

        if parser is None:
            raise DependencyError(f"Unsupported format: {format_type}")
        return parser

    def _resolve_python_version(
        self,
        file_path: Path,
        parser: DependencyParser,
        cli_python_version: Optional[str],
    ) -> str:
        _, file_python_version = parser.parse(file_path)

        if "requirements" in file_path.name and file_path.suffix == ".txt":
            if cli_python_version:
                return cli_python_version
            raise DependencyError(
                "Python version must be specified for requirements.txt via --python-version"
            )

        return file_python_version or cli_python_version or "3.8"

    def _get_formatter(self, format_name: str) -> DependencyFormatter:
        formatter = KNOWN_FORMATTERS.get(format_name)

        if formatter is None:
            raise DependencyError(f"Unsupported output format: {format_name}")
        return formatter

    def _handle_prune(
        self,
        file_path: Path,
        python_version: Optional[str],
        output: Optional[Path],
        format_name: str,
    ) -> None:
        """Handles the 'prune' command.

        Detects the file format, resolves the python version, prunes redundant dependencies,
        and outputs the formatted results.
        """
        format_type = self._detect_format(file_path)
        parser = self._get_parser(format_type)
        resolved_python_version = self._resolve_python_version(file_path, parser, python_version)
        pruner = DependencyPruner(resolved_python_version)

        pruned_deps = pruner.prune(file_path, format_type)
        self._output_results(pruned_deps, output, format_name)

    def _handle_merge_prune(
        self,
        file_paths: List[Path],
        python_version: Optional[str],
        output: Optional[Path],
        format_name: str,
    ) -> None:
        """Handles the 'merge-prune' command.

        Merges dependencies from multiple files, determines the appropriate python version,
        prunes redundant dependencies, and outputs the consolidated, formatted result.
        """
        all_deps: List[Dependency] = []
        resolved_python_version: Optional[str] = python_version

        for file_path in file_paths:
            format_type = self._detect_format(file_path)
            parser = self._get_parser(format_type)
            project_deps, file_python_version = parser.parse(file_path)

            if file_path.name == "requirements.txt" and not resolved_python_version:
                if not python_version:
                    raise DependencyError("Missing --python-version for requirements.txt")
                resolved_python_version = python_version
            elif file_python_version and not resolved_python_version:
                resolved_python_version = file_python_version

            all_deps.extend(project_deps.direct)

        if not resolved_python_version:
            resolved_python_version = "3.8"

        pruner = DependencyPruner(python_version=resolved_python_version)

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write("\n".join(str(dep) for dep in all_deps))
            temp_file.close()
            pruned_deps = pruner.prune(temp_path, "requirements-txt")
            temp_path.unlink()

        self._output_results(pruned_deps, output, format_name)

    def _output_results(self, deps: List[Dependency], output: Optional[Path], format_name: str) -> None:
        """Outputs the formatted pruned dependencies.

        The result is written to the specified output file or printed to stdout if no file is provided.
        """
        formatter = self._get_formatter(format_name)
        result = formatter.format(deps)
        if output:
            output.write_text(result)
            logger.info(f"Results written to {output}")
        else:
            print(result)
