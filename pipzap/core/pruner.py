from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from loguru import logger
from typing_extensions import Literal

from pipzap.core.dependencies import Dependency, ProjectDependencies
from pipzap.core.resolver import DependenciesResolver
from pipzap.exceptions import DependencyError, ParseError
from pipzap.parsers import PoetryTomlParser, RequirementsTxtParser, UVTomlParser
from pipzap.parsers.base import DependencyParser

KnownParsersT = Literal["requirements-txt", "uv-toml", "poetry-toml"]


class DependencyPruner:
    """Prunes redundant dependencies from a project."""

    def __init__(self, python_version: str) -> None:
        """Initializes a DependencyPruner instance.

        Args:
            python_version: A string representing the python version.

        Raises:
            ParseError: An error indicating an invalid python version specification.
        """
        if not python_version.strip():
            raise ParseError(f"Invalid python version specified: {python_version}")

        if python_version[0].isdigit():
            python_version = f">={python_version}"

        self.python_version = python_version

    def prune(self, file_path: Path, parser_type: KnownParsersT) -> List[Dependency]:
        """Prunes redundant dependencies from a project file.

        Args:
            file_path: A Path to the file containing dependency definitions.
            parser_type: A string specifying the type of dependency parser.

        Returns:
            A list of Dependency objects after pruning redundant dependencies.
        """
        parser = self._create_parser(parser_type)
        project_deps, _ = self._parse_file(parser, file_path)
        resolved_deps = self._resolve_dependencies(project_deps)
        redundant = self._find_redundant_deps(resolved_deps.direct, resolved_deps.graph)
        pruned = self._filter_redundant(resolved_deps.direct, redundant)
        logger.info(f"Pruned {len(resolved_deps.direct) - len(pruned)} redundant dependencies")
        return pruned

    def _create_parser(self, parser_type: str) -> DependencyParser:
        """Creates a dependency parser based on the provided parser type.

        Args:
            parser_type: A string specifying the parser type.

        Returns:
            A DependencyParser instance.

        Raises:
            DependencyError: An error indicating an unsupported parser type.
        """
        if parser_type == "requirements-txt":
            return RequirementsTxtParser()

        if parser_type == "uv-toml":
            return UVTomlParser()

        if parser_type == "poetry-toml":
            return PoetryTomlParser()

        raise DependencyError(f"Unsupported parser type: {parser_type}")

    def _parse_file(
        self, parser: DependencyParser, file_path: Path
    ) -> Tuple[ProjectDependencies, Optional[str]]:
        """Parses a file using the specified dependency parser.

        Args:
            parser: A DependencyParser instance.
            file_path: A Path to the file to be parsed.

        Returns:
            A tuple containing a ProjectDependencies object and an optional string.

        Raises:
            DependencyError: An error indicating failure to parse the file.
        """
        try:
            return parser.parse(file_path)
        except Exception as e:
            raise DependencyError(f"Failed to parse {file_path}: {e}")

    def _resolve_dependencies(self, project_deps: ProjectDependencies) -> ProjectDependencies:
        """Resolves dependencies for the project.

        Args:
            project_deps: A ProjectDependencies object representing the project's dependencies.

        Returns:
            A ProjectDependencies object with resolved dependencies.

        Raises:
            DependencyError: An error indicating failure in dependency resolution.
        """
        resolver = DependenciesResolver()
        try:
            return resolver.resolve(project_deps, self.python_version)
        except Exception as e:
            raise DependencyError(f"Failed to resolve dependencies: {e}")

    def _find_redundant_deps(self, direct: List[Dependency], graph: Dict[str, List[str]]) -> Set[str]:
        """Finds redundant dependencies that appear both as direct and transitive dependencies.

        Args:
            direct: A list of direct Dependency objects.
            graph: A dictionary mapping dependency names to lists of transitive dependency names.

        Returns:
            A set of dependency names that are redundant.
        """
        direct_names = {dep.name.lower() for dep in direct}
        transitive_deps: Set[str] = set()

        for dep in direct:
            self._collect_transitive_deps(dep.name.lower(), graph, transitive_deps)

        redundant = direct_names & transitive_deps
        return redundant

    def _collect_transitive_deps(self, name: str, graph: Dict[str, List[str]], transitive: Set[str]) -> None:
        """Collects transitive dependencies recursively.

        Args:
            name: A string representing the dependency name.
            graph: A dictionary mapping dependency names to lists of transitive dependency names.
            transitive: A set to which collected dependency names are added.
        """
        deps = graph.get(name, [])
        for dep in deps:
            if dep in transitive:
                continue

            transitive.add(dep)
            self._collect_transitive_deps(dep, graph, transitive)

    @staticmethod
    def _filter_redundant(direct: List[Dependency], redundant: Set[str]) -> List[Dependency]:
        """Filters out redundant dependencies from the direct dependencies list.

        Args:
            direct: A list of direct Dependency objects.
            redundant: A set of dependency names that are redundant.

        Returns:
            A list of Dependency objects that are not redundant.
        """
        return [dep for dep in direct if dep.name.lower() not in redundant]
