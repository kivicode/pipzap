from dataclasses import replace
from typing import Dict, List, Set

from loguru import logger

from pipzap.core.dependencies import Dependency, DepKeyT, ProjectDependencies


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
        logger.debug(f"Direct deps: {', '.join(dep.name for dep in resolved_deps.direct)}")
        logger.debug(
            f"Pruning {len(resolved_deps.direct)} direct deps, "  #
            f"graph size: {len(resolved_deps.graph)}"
        )

        redundant = cls._find_redundant_deps(resolved_deps)
        pruned = cls._filter_redundant(resolved_deps.direct, redundant)

        logger.info(f"Redundant: {', '.join(name for name, *_ in redundant or [('<empty>', '')])}")
        logger.info(
            f"Pruned {len(resolved_deps.direct) - len(pruned)} "  #
            f"redundant dependencies, kept {len(pruned)}"
        )
        return replace(resolved_deps, direct=pruned)

    @classmethod
    def _find_redundant_deps(cls, dependencies: ProjectDependencies) -> Set[DepKeyT]:
        """Identifies redundant direct dependencies."""
        redundant = set()

        for dep in dependencies.direct:
            for other_dep in dependencies.direct:
                if other_dep is dep:
                    continue

                # If other_dep can reach dep...
                if not cls._is_in_transitive(other_dep.key, dep.key, dependencies.graph):
                    continue

                # ...but if dep can also reach other_dep, it's a cycle; do not mark as redundant.
                if cls._is_in_transitive(dep.key, other_dep.key, dependencies.graph):
                    continue

                redundant.add(dep.key)
                break

        return redundant

    @classmethod
    def _is_in_transitive(cls, root: DepKeyT, target: DepKeyT, graph: Dict[DepKeyT, List[DepKeyT]]) -> bool:
        """Checks if target is in the transitive closure of root."""
        visited = set()
        stack = [root]

        while stack:
            current = stack.pop()
            if current == target:
                return True

            if current in visited:
                continue

            visited.add(current)
            stack.extend(graph.get(current, []))

        return False

    @staticmethod
    def _filter_redundant(direct: List[Dependency], redundant: Set[DepKeyT]) -> List[Dependency]:
        """Removes the redundant dependencies from direct deps."""
        logger.debug(f"Filtering {len(direct)} deps against {len(redundant)} redundant")
        return [dep for dep in direct if dep.key not in redundant]
