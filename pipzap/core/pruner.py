from dataclasses import replace
from typing import Dict, List, Optional, Set, Tuple

from loguru import logger

from pipzap.core.dependencies import Dependency, DepKeyT, ProjectDependencies
from pipzap.parsing.workspace import Workspace
from pipzap.utils.io import read_toml, write_toml


class DependencyPruner:
    """Prunes redundant (transitive) dependencies from parsed project dependencies tree."""

    @classmethod
    def prune(
        cls,
        resolved_deps: ProjectDependencies,
        keep: Optional[List[str]] = None,
        preserve_all: bool = False,
        workspace: Optional["Workspace"] = None,
    ) -> ProjectDependencies:
        """Identifies and removes the redundant/transitive dependencies.

        Args:
            resolved_deps: Parsed and resolved dependencies and the internal dependency tree to prune.
            keep: Package names to not prune.
            preserve_all: If True, re-lock pruned deps and add back any that would be missing.
            workspace: Workspace for re-locking (required if preserve_all is True).

        Returns:
            A copy of the original project dependencies with the redundant deps removed.
        """
        logger.debug(f"Direct deps: {', '.join(dep.name for dep in resolved_deps.direct)}")
        logger.debug(
            f"Pruning {len(resolved_deps.direct)} direct deps, "  #
            f"graph size: {len(resolved_deps.graph)}"
        )

        redundant = cls._find_redundant_deps(resolved_deps, keep or [])
        pruned = cls._filter_redundant(resolved_deps.direct, redundant)

        logger.info(f"Redundant: {', '.join(name for name, *_ in redundant or [('<empty>', '')])}")
        logger.info(
            f"Pruned {len(resolved_deps.direct) - len(pruned)} "  #
            f"redundant dependencies, kept {len(pruned)}"
        )

        if not preserve_all or not workspace:
            return replace(resolved_deps, direct=pruned)

        missing, original_lock = cls._find_missing_after_prune(pruned, workspace)
        if not missing:
            return replace(resolved_deps, direct=pruned)

        logger.info(f"Preserve-all: adding back {len(missing)} missing deps: {', '.join(missing)}")
        pruned_names = {dep.name.lower() for dep in pruned}

        for dep in resolved_deps.direct:
            if dep.name.lower() in missing and dep.name.lower() not in pruned_names:
                pruned.append(dep)
                pruned_names.add(dep.name.lower())
                missing.discard(dep.name.lower())

        if missing:
            lock_packages = {p["name"].lower(): p for p in original_lock.get("package", [])}
            for name in missing:
                if name in lock_packages and name not in pruned_names:
                    pkg = lock_packages[name]
                    new_dep = Dependency(
                        name=pkg["name"],
                        pinned_version=pkg.get("version"),
                    )
                    pruned.append(new_dep)
                    pruned_names.add(name)

        return replace(resolved_deps, direct=pruned)

    @classmethod
    def _find_missing_after_prune(
        cls,
        pruned_deps: List[Dependency],
        workspace: "Workspace",
    ) -> Tuple[Set[str], dict]:
        """Re-lock pruned deps and find packages that would be missing compared to original.

        Returns:
            Tuple of (missing package names, original lock data).
        """
        original_lock = read_toml(workspace.base / "uv.lock")
        original_packages = {p["name"].lower() for p in original_lock.get("package", [])}

        pyproject_path = workspace.base / "pyproject.toml"
        pyproject = read_toml(pyproject_path)

        pruned_dep_strs = []
        for dep in pruned_deps:
            dep_str = dep.name
            if dep.required_extras:
                dep_str += f"[{','.join(sorted(dep.required_extras))}]"
            if dep.pinned_version:
                dep_str += f"=={dep.pinned_version}"
            if dep.marker:
                dep_str += f"; {dep.marker}"
            pruned_dep_strs.append(dep_str)

        pyproject["project"]["dependencies"] = pruned_dep_strs
        write_toml(pyproject, pyproject_path)

        lock_path = workspace.base / "uv.lock"
        if lock_path.exists():
            lock_path.unlink()

        workspace.run(["uv", "lock"], "preserve-all re-lock")
        pruned_lock = read_toml(workspace.base / "uv.lock")
        pruned_packages = {p["name"].lower() for p in pruned_lock.get("package", [])}

        missing = original_packages - pruned_packages - {"generated-project"}
        return missing, original_lock

    @classmethod
    def _find_redundant_deps(cls, dependencies: ProjectDependencies, keep: List[str]) -> Set[DepKeyT]:
        """Identifies redundant direct dependencies, preserving those with direct or indirect markers."""
        redundant = set()
        keep = [name.lower() for name in keep]

        for dep in dependencies.direct:
            if dep.marker is not None or dep.indirect_markers or dep.name.lower() in keep:
                continue

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
