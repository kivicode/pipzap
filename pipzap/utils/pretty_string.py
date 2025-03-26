from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from pipzap.core.dependencies import Dependency, DepKeyT, ProjectDependencies


def format_project_dependencies(deps: "ProjectDependencies") -> str:
    """Formats a projects dependencies object as a pretty string."""
    parts = [
        *_get_python_version_lines(deps.py_version),
        *["Direct Dependencies:"],
        *_get_direct_deps_lines(deps.direct),
        *["", "Dependency Graph:"],
        *_get_graph_lines(deps.graph),
    ]
    return "\n".join(parts)


def remove_prefix(text, prefix, num_iters=1):
    """Compat re-implementation of python 3.9+ `str.removeprefix`.

    Args:
        text: String to remove the prefix of.
        prefix: Prefix to remove.
        num_iters: How many times to repeat the operation. Default: 1.

    Returns:
        Original text with the prefix removed.
    """
    for _ in range(num_iters):
        if not text.startswith(prefix):
            return text

        text = text[len(prefix) :]

    return text


INDENT = "    "


def _get_python_version_lines(py_version: Optional[str]) -> List[str]:
    if not py_version:
        return []

    return [f"Python Version: {py_version}", ""]


def _get_direct_deps_lines(direct_deps: List["Dependency"]) -> List[str]:
    if not direct_deps:
        return [f"{INDENT}(none)"]

    sorted_deps = sorted(direct_deps, key=(lambda x: x.name.lower()))
    return [f"{INDENT}{dep.name}" + _get_dep_attributes(dep) for dep in sorted_deps]


def _get_dep_attributes(dep: "Dependency") -> str:
    attributes = []

    if dep.marker:
        attributes.append(f"marker={dep.index}")

    if dep.extras:
        attributes.append(f"extras=[{', '.join(dep.extras)}]")

    if dep.groups:
        attributes.append(f"groups=[{', '.join(dep.groups)}]")

    if dep.index:
        attributes.append(f"index={dep.index}")

    if not attributes:
        return ""

    return f" [{', '.join(attributes)}]"


def _get_graph_lines(graph: Dict["DepKeyT", List["DepKeyT"]]) -> List[str]:
    if not graph:
        return [f"{INDENT}(none)"]

    lines: List[str] = []
    sorted_parents = sorted(graph.keys())

    for parent in sorted_parents:
        children = graph[parent]
        lines.append(f"{INDENT}{parent[0]} ->")

        if not children:
            lines.append(f"{INDENT * 2}(no transitive dependencies)")
            continue

        sorted_children = sorted(children)
        for child in sorted_children:
            lines.append(f"{INDENT * 2}{child[0]}")

    return lines
