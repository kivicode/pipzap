from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple, Union, cast
from urllib.parse import urlparse

import tomlkit
from packaging.requirements import Requirement

from pipzap.utils.pretty_string import remove_prefix
from pipzap.utils.requirement_string import parse_requirement_string


class UVToPoetryConverter:
    """An approximate converter from a uv-based pyproject.toml to a Poetry-based one.

    The following keys from [tool.uv] cannot be directly mapped due to fundamental differences:
        - managed: Controls uv's management of the environment, no direct Poetry equivalent.
        - python-preference: Specifies how uv selects Python interpreters, unique to uv.
        - python-downloads: Controls Python download behavior in uv, not present in Poetry.
        - exclude-newer: Filters out newer package versions in uv, no direct Poetry counterpart.
    """

    def __init__(self, uv_doc: dict):
        self.uv_doc = uv_doc
        self.poetry_doc = tomlkit.document()

    def convert(self) -> dict:
        self.uv_doc = deepcopy(self.uv_doc)
        self.poetry_doc = tomlkit.document()

        self._handle_project_table()
        self._handle_python_version()
        self._handle_dependencies()
        self._handle_optional_dependencies()
        self._set_build_system()
        self._handle_package_indices()
        self._copy_other_tool_configs()

        return cast(dict, self.poetry_doc)

    def _handle_project_table(self) -> None:
        """Copies the [project] table, excluding dependencies which are handled separately."""
        if "project" not in self.uv_doc:
            return

        project_table = self.uv_doc["project"].copy()
        project_table.pop("dependencies", None)
        project_table.pop("optional-dependencies", None)

        self.poetry_doc["project"] = project_table

    def _get_uv_sources(self) -> Dict[str, Dict[str, dict]]:
        """Extracts source configurations from [tool.uv.sources].

        Returns:
            A mapping of package names to their source specifications.
        """
        uv_sources = self.uv_doc.get("tool", {}).get("uv", {}).get("sources", [])
        return {source["name"]: {k: v for k, v in source.items() if k != "name"} for source in uv_sources}

    def _handle_url_dependency(self, req: Requirement, dep: dict) -> None:
        """Handles URL-based dependencies (git, file, etc.)."""
        if req.url.startswith("file://") or not req.url.startswith("git+"):
            dep["url"] = req.url
            return

        git_url = remove_prefix(req.url, "git+")
        parsed = urlparse(git_url)

        if "@" not in parsed.path:
            dep["git"] = git_url
            return

        repo_path, _, rev = parsed.path.rpartition("@")
        repository_url = parsed.scheme + "://" + parsed.netloc + repo_path
        dep["git"] = repository_url
        dep["rev"] = rev

    def _handle_versioned_dependency(
        self,
        req: Requirement,
        sources: Dict[str, Dict[str, dict]],
        dep: dict,
    ) -> Optional[dict]:
        """Handles versioned dependencies and sources, returning source dict if no index is present."""
        if req.specifier:
            version = remove_prefix(str(req.specifier), "=", 2)

            if version.startswith("!="):
                version = f"*,{version}"

            if version and version[0].isdigit():
                version = f"^{version}"

            dep["version"] = version

        if req.name in sources:
            source = sources[req.name]
            if "index" not in source:
                return source

            dep["source"] = source["index"]

        return None

    def _convert_dependency(
        self,
        req_str: str,
        sources: Dict[str, Dict[str, dict]],
    ) -> Tuple[str, Union[str, Dict[str, Any]]]:
        """Converts a PEP 508 requirement string to a Poetry dependency specification.

        Args:
            req_str: The requirement string.
            sources: Source configurations from _get_uv_sources.

        Returns:
            Tuple of form (package_name, spec).
        """
        req = parse_requirement_string(req_str)
        name = req.name
        dep: Dict[str, Union[str, List[str]]] = {}

        if req.url:
            self._handle_url_dependency(req, dep)
        else:
            source_dep = self._handle_versioned_dependency(req, sources, dep)
            if source_dep:
                return name, source_dep

        if req.marker:
            dep["markers"] = str(req.marker).replace('"', "'")

        if req.extras:
            dep["extras"] = list(req.extras)

        if not dep:
            return name, "*"

        dep_table = tomlkit.inline_table()
        dep_table.update(dep)
        return name, dep_table

    def _handle_dependencies(self) -> None:
        """Converts runtime and dev dependencies to Poetry format."""
        sources = self._get_uv_sources()
        poetry_tool = self.poetry_doc.setdefault("tool", tomlkit.table())
        poetry_poetry = poetry_tool.setdefault("poetry", tomlkit.table())
        poetry_deps = poetry_poetry.setdefault("dependencies", tomlkit.table())

        # [project.dependencies]
        for req_str in self.uv_doc.get("project", {}).get("dependencies", []):
            name, dep = self._convert_dependency(req_str, sources)
            poetry_deps[name] = dep

        # [tool.uv.dev-dependencies]
        dev_group = poetry_poetry.setdefault("group", tomlkit.table()).setdefault("dev", tomlkit.table())
        dev_deps = dev_group.setdefault("dependencies", tomlkit.table())

        for req_str in self.uv_doc.get("tool", {}).get("uv", {}).get("dev-dependencies", []):
            name, dep = self._convert_dependency(req_str, sources)
            dev_deps[name] = dep

    def _handle_optional_dependencies(self) -> None:
        """Converts [project.optional-dependencies] to Poetry's [tool.poetry.extras]."""
        sources = self._get_uv_sources()
        poetry_poetry = self.poetry_doc["tool"]["poetry"]
        extras = poetry_poetry.setdefault("extras", tomlkit.table())
        poetry_deps = poetry_poetry["dependencies"]

        for group, reqs in self.uv_doc.get("project", {}).get("optional-dependencies", {}).items():
            extras[group] = tomlkit.array()

            for req_str in reqs:
                name, dep = self._convert_dependency(req_str, sources)

                if name in poetry_deps:
                    extras[group].append(name)
                    continue

                if isinstance(dep, dict):
                    dep["optional"] = True
                else:
                    dep = {"version": dep, "optional": True}

                dep_table = tomlkit.inline_table()
                dep_table.update(dep)
                poetry_deps[name] = dep_table
                extras[group].append(name)

    def _set_build_system(self) -> None:
        """Sets the build system to use poetry-core."""
        build_system = tomlkit.table()
        build_system.update(
            {
                "requires": ["poetry-core>=2.0.0,<3.0.0"],
                "build-backend": "poetry.core.masonry.api",
            }
        )
        self.poetry_doc["build-system"] = build_system

    def _handle_package_indices(self) -> None:
        """Converts uv's package indices to Poetry's [tool.poetry.source]."""
        uv_tool = self.uv_doc["tool"]["uv"]
        if not uv_tool:
            return

        poetry_poetry = self.poetry_doc["tool"]["poetry"]
        sources_list = poetry_poetry.setdefault("source", tomlkit.aot())

        if "index-url" in uv_tool:
            source_table = tomlkit.table()
            source_table.update(
                {
                    "name": "pypi",
                    "url": uv_tool["index-url"],
                    "priority": "primary",
                }
            )
            sources_list.append(source_table)

        if "extra-index-url" in uv_tool:
            for i, url in enumerate(uv_tool["extra-index-url"]):
                source_table = tomlkit.table()
                source_table.update(
                    {
                        "name": f"extra-{i}",
                        "url": url,
                        "priority": "supplemental",
                    }
                )
                sources_list.append(source_table)

        for index in uv_tool.get("index", []):
            source_table = tomlkit.table()
            source_table.update(
                {
                    "name": index["name"],
                    "url": index["url"],
                    "priority": "supplemental",
                }
            )
            sources_list.append(source_table)

    def _copy_other_tool_configs(self) -> None:
        """Transfers non-uv tool configurations."""
        for tool_name, config in self.uv_doc.get("tool", {}).items():
            if tool_name == "uv":
                continue

            self.poetry_doc["tool"][tool_name] = config

    def _handle_python_version(self) -> None:
        """Maps [tool.uv.python]."""
        python_ver = self.uv_doc.get("tool", {}).get("uv", {}).get("python")
        if not python_ver:
            return

        _tool = self.poetry_doc.setdefault("tool", tomlkit.table())
        _poetry = _tool.setdefault("poetry", tomlkit.table())
        _poetry.setdefault("dependencies", tomlkit.table())

        major, minor = python_ver.split(".")
        poetry_python = f"~{major}.{minor}"
        self.poetry_doc["tool"]["poetry"]["dependencies"]["python"] = poetry_python

    @property
    def unmapped_keys(self) -> List[str]:
        """A list of uv-specific keys that were not mapped to Poetry (e.g., '[tool.uv.managed]')."""
        return [
            f"[tool.uv.{key}]"
            for key in ["managed", "python-preference", "python-downloads", "exclude-newer"]
            if key in self.uv_doc.get("tool", {}).get("uv", {})
        ]
