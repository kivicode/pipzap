from typing import List, Optional, cast

from pipzap.core.dependencies import Dependency, ProjectDependencies
from pipzap.formatting.base import DependenciesFormatter


class RequirementsTXTFormatter(DependenciesFormatter):
    """Re-builds a requirements.txt file from parsed dependencies."""

    def __init__(self, dependencies: ProjectDependencies):
        super().__init__(dependencies)
        self._lines: List[str] = []

    def format(self) -> str:
        """Build a requirements.txt string from the dependencies.

        Returns:
            A string representing the contents of a requirements.txt file.
        """
        self._lines = [f"# Requires Python {self.python_version}"]
        self._add_index_urls()
        self._add_dependencies()
        return "\n".join(self._lines) + "\n"

    def _add_index_urls(self) -> None:
        """Adds custom index URLs as `--index-url` or `--extra-index-url` lines."""
        seen_indexes = set()
        primary_index = None
        extra_indexes: List[str] = []

        for dep in self.deps:
            if not dep.index or dep.index in seen_indexes:
                continue

            seen_indexes.add(dep.index)

            if primary_index is None:
                primary_index = dep.index
            else:
                extra_indexes.append(dep.index)

        if primary_index:
            self._lines.append(f"--index-url {primary_index}")

        for extra_index in extra_indexes:
            self._lines.append(f"--extra-index-url {extra_index}")

    def _add_dependencies(self) -> None:
        """Adds all dependencies to the requirements list with pinned version comments."""
        for dep in self.deps:
            spec = self._format_dependency_spec(dep)

            pinned = self._get_pinned_version(dep)
            comment = f"# pinned: {pinned}" if pinned else "# pinned: none"
            if "==" in spec:
                comment = ""

            self._lines.append(f"{spec} {comment}")

    def _format_dependency_spec(self, dep: Dependency) -> str:
        """Formats a dependency specification for requirements.txt.

        Args:
            dep: The Dependency object to format.

        Returns:
            A string representing the dependency specification.
        """
        name = dep.name
        if dep.extra:
            name += f"[{dep.extra}]"

        if dep.source and "git" in dep.source:
            git_url = dep.source["git"]
            rev = dep.source.get("rev", "main")
            return f"git+{git_url}@{rev}#egg={dep.name}"

        if dep.url:
            return f"{name} @ {dep.url}"

        if dep.version_constraint:
            return f"{name}{dep.version_constraint}"

        return name

    def _get_pinned_version(self, dep: Dependency) -> Optional[str]:
        """Determines the pinned version for a dependency.

        Args:
            dep: The Dependency object to inspect.

        Returns:
            The pinned version if available, otherwise None.
        """
        if dep.pinned_version:
            return dep.pinned_version

        if (dep.version_constraint or "").startswith("=="):
            return cast(str, dep.version_constraint)[2:].strip()

        return None
