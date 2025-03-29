import threading
from typing import Union

import pytest

from pipzap.core.dependencies import Dependency, DepKeyT, ProjectDependencies
from pipzap.core.pruner import DependencyPruner
from pipzap.core.source_format import SourceFormat
from pipzap.parsing.converter import ProjectConverter
from pipzap.parsing.parser import DependenciesParser
from pipzap.parsing.workspace import Workspace


def create_project_deps(direct_names: list, graph: dict) -> ProjectDependencies:
    """Helper to create ProjectDependencies for pruning tests."""

    def _make_dep(key_or_name: Union[DepKeyT, str]) -> DepKeyT:
        return Dependency(name=key_or_name).key if isinstance(key_or_name, str) else key_or_name

    return ProjectDependencies(
        direct=[Dependency(name=name) for name in direct_names],
        graph={_make_dep(k): [_make_dep(v) for v in vs] for k, vs in graph.items()},
        source_format=SourceFormat.UV,
        py_version="3.8",
        uv_pyproject_source=None,
        poetry_pyproject_source=None,
    )


@pytest.mark.parametrize(
    "direct_names, graph, expected_direct",
    [
        (["A", "B"], {"A": [], "B": []}, ["A", "B"]),  # No redundancy
        (["A", "B", "C"], {"A": ["B"], "B": ["C"], "C": []}, ["A"]),  # Transitive redundancy
        (["A", "B"], {"A": ["B"], "B": ["A"]}, ["A", "B"]),  # Circular dependency
        ([], {}, []),  # Empty graph
    ],
)
def test_pruning_scenarios(direct_names, graph, expected_direct):
    """Tests various pruning scenarios to ensure correct behavior."""
    proj_deps = create_project_deps(direct_names, graph)
    pruned = DependencyPruner.prune(proj_deps)
    assert {dep.name for dep in pruned.direct} == set(expected_direct)


def test_pruning_with_overlapping_extras():
    """Tests pruning with dependencies that have different extras."""
    dep1 = Dependency(name="pkg", extras=frozenset({"extra1"}))
    dep2 = Dependency(name="pkg", extras=frozenset({"extra2"}))

    proj_deps = create_project_deps([dep1.name, dep2.name], {dep1.key: [], dep2.key: []})
    pruned = DependencyPruner.prune(proj_deps)

    assert len(pruned.direct) == 2  # Both should remain due to different extras


def test_pruning_with_deep_transitive_chains():
    """Test pruning with a deep chain of transitive dependencies."""
    chain = [Dependency(name=f"pkg{i}") for i in range(50)]
    graph = {chain[i].key: [chain[i + 1].key] for i in range(49)}
    graph[chain[-1].key] = []

    proj_deps = create_project_deps([dep.name for dep in chain], graph)
    pruned = DependencyPruner.prune(proj_deps)

    assert len(pruned.direct) == 1 and pruned.direct[0].name == "pkg0"


def test_dependency_cycles():
    """Tests pruning with dependency cycles."""
    depA = Dependency(name="A")
    depB = Dependency(name="B")

    proj_deps = ProjectDependencies(
        direct=[depA, depB],
        graph={depA.key: [depB.key], depB.key: [depA.key]},
        source_format=SourceFormat.REQS,
        py_version="3.8",
        poetry_pyproject_source=None,
        uv_pyproject_source=None,
    )
    pruned = DependencyPruner.prune(proj_deps)
    assert {dep.name for dep in pruned.direct} == {"A", "B"}


def test_concurrent_dependency_resolution(make_pyproject):
    """Tests concurrent dependency resolution consistency."""
    content = {
        "project": {
            "name": "dummy",
            "version": "0.1.0",
            "dependencies": ["packageA==1.0.0"],
            "requires-python": "==3.8",
        },
        "tool": {"uv": {"sources": {}}},
    }
    file = make_pyproject(content)
    results = []

    def worker():
        with Workspace(file) as ws:
            converter = ProjectConverter("3.8")
            fmt = converter.convert_to_uv(ws)
            parsed = DependenciesParser.parse(ws, fmt)
            results.append(len(parsed.direct))

    threads = [threading.Thread(target=worker) for _ in range(5)]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    assert all(count == 1 for count in results)


def test_invalid_python_version_specifications(make_pyproject):
    """Tests handling of invalid Python version specifications."""
    content = {
        "project": {
            "name": "test-project",
            "version": "0.1.0",
            "dependencies": ["packageA==1.0.0"],
            "requires-python": "invalid",
        },
        "tool": {"uv": {}},
    }

    with Workspace(make_pyproject(content)) as ws:
        converter = ProjectConverter("invalid")

        with pytest.raises(Exception):
            converter.convert_to_uv(ws)
