from typing import Dict, List, Optional, Set, Tuple

from loguru import logger

from pipzap.core.dependencies import Dependency, ProjectDependencies


class DependencyPruner:
    """Prunes redundant (transitive) dependencies from parsed project dependencies tree."""

    @classmethod
    def prune(cls, resolved_deps: ProjectDependencies) -> ProjectDependencies:
        """Identifies and removes the redundant/transitive dependencies.

        Args:
            resolved_deps: Parsed and resolved dependencies and the internal dependency tree to prune.

        Returns:
            A copy of the original project dependencies with the redundant deps removed.
        """
        logger.debug(
            f"Pruning {len(resolved_deps.direct)} direct deps, "  #
            f"graph size: {len(resolved_deps.graph)}"
        )

        redundant = cls._find_redundant_deps(resolved_deps)
        pruned = cls._filter_redundant(resolved_deps.direct, redundant)

        logger.info(
            f"Pruned {len(resolved_deps.direct) - len(pruned)} "  #
            f"redundant dependencies, kept {len(pruned)}"
        )
        return ProjectDependencies(pruned, resolved_deps.graph, resolved_deps.py_version)

    @classmethod
    def _find_redundant_deps(
        cls,
        dependencies: ProjectDependencies,
    ) -> Set[Tuple[str, Tuple[Optional[str], Optional[str]]]]:
        """Finds redundant dependencies by comparing direct and transitive deps.

        Args:
            dependencies: Project dependencies to find the redundancies in.

        Returns:
            A set of redundant dependency names with their context identifiers.
        """

        direct_deps = {(dep.name.lower(), dep.context) for dep in dependencies.direct}
        logger.debug(f"Direct deps: {', '.join(name for name, *_ in direct_deps)}")

        transitive_deps: Set[Tuple[str, Tuple[Optional[str], Optional[str]]]] = set()
        for dep in dependencies.direct:
            logger.debug(f"  {dep.name} (context: {dep.context})")
            cls._collect_transitive_deps(dep.name.lower(), dep.context, dependencies.graph, transitive_deps)

        redundant = direct_deps & transitive_deps
        logger.debug(f"Redundant: {', '.join(name for name, *_ in redundant)}")
        return redundant

    @classmethod
    def _collect_transitive_deps(
        cls,
        name: str,
        context: Tuple[Optional[str], Optional[str]],
        graph: Dict[str, List[str]],
        transitive: Set[Tuple[str, Tuple[Optional[str], Optional[str]]]],
    ) -> None:
        """Collects transitive dependencies recursively.

        Args:
            name: Name of the current root dependency to analyze.
            context: A context key of the root dependency.
            graph: A graph representation of the dependency tree.
            transitive: A cumulative set of transitive dependencies identified.
        """
        indent = "    "
        dep_names = graph.get(name, [])
        logger.debug(f"{indent}{name} -> {len(dep_names)} transitive")

        for name in dep_names:
            key = (name.lower(), context)
            if key in transitive:
                logger.debug(f"{indent * 2}{name} (skipped)")
                continue

            logger.debug(f"{indent * 2}{name} (added)")
            transitive.add(key)
            cls._collect_transitive_deps(name.lower(), context, graph, transitive)

    @staticmethod
    def _filter_redundant(
        direct: List[Dependency],
        redundant: Set[Tuple[str, Tuple[Optional[str], Optional[str]]]],
    ) -> List[Dependency]:
        """Removes the redundant dependencies from direct deps."""
        logger.debug(f"Filtering {len(direct)} deps against {len(redundant)} redundant")
        return [dep for dep in direct if (dep.name.lower(), dep.context) not in redundant]
