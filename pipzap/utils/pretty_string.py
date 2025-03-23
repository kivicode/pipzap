from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from pipzap.core.dependencies import Dependency, ProjectDependencies


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

    lines = []
    sorted_deps = sorted(direct_deps, key=(lambda x: x.name.lower()))

    for dep in sorted_deps:
        base = f"{INDENT}{dep.name}"
        version = _get_version_string(dep)
        attributes = _get_dep_attributes(dep)
        line = base + version + attributes
        lines.append(line)

    return lines


def _get_version_string(dep: "Dependency") -> str:
    if dep.pinned_version:
        return f" ({dep.pinned_version})"

    if dep.version_constraint:
        return f" {dep.version_constraint}"

    return ""


def _get_dep_attributes(dep: "Dependency") -> str:
    attributes = []

    if dep.extra:
        attributes.append(f"extra={dep.extra}")

    elif dep.group:
        attributes.append(f"group={dep.group}")

    if dep.index:
        attributes.append(f"index={dep.index}")

    if dep.url:
        attributes.append(f"url={dep.url}")

    if dep.source:
        source_str = ",".join(f"{k}={v}" for k, v in dep.source.items())
        attributes.append(f"source={{{source_str}}}")

    if not attributes:
        return ""

    return f" [{', '.join(attributes)}]"


def _get_graph_lines(graph: Dict[(str, List[str])]) -> List[str]:
    if not graph:
        return [f"{INDENT}(none)"]

    lines: List[str] = []
    sorted_parents = sorted(graph.keys())

    for parent in sorted_parents:
        children = graph[parent]
        lines.append(f"{INDENT}{parent} ->")

        if not children:
            lines.append(f"{INDENT * 2}(no transitive dependencies)")
            continue

        sorted_children = sorted(children)
        for child in sorted_children:
            lines.append(f"{INDENT * 2}{child}")

    return lines
