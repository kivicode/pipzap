import json
from pathlib import Path
from typing import List, Set

from loguru import logger
from pipreqs import pipreqs


def discover_dependencies(scan_path: Path) -> Set[str]:
    """Discovers package dependencies by scanning Python source files.

    Uses pipreqs to scan all .py files in the given directory and extract imported packages.

    Args:
        scan_path: Directory to scan for Python files.

    Returns:
        Set of discovered package names (normalized to lowercase).

    """
    if not scan_path.is_dir():
        raise ValueError(f"Scan path must be a directory: {scan_path}")

    logger.info(f"Discovering dependencies in: {scan_path}")

    try:
        imports = pipreqs.get_all_imports(
            str(scan_path),
            encoding="utf-8",
            extra_ignore_dirs=None,
            follow_links=True,
        )
        imports = _get_pkg_names(imports)
    except Exception as e:
        logger.error(f"Failed to scan imports: {e}")
        return set()

    if not imports:
        logger.warning("No imports discovered")
        return set()

    logger.debug(f"Found imports: {imports}")

    try:
        packages = pipreqs.get_pkg_names(imports)
    except Exception as e:
        logger.warning(f"Failed to map some imports to packages: {e}")
        packages = list(imports)

    discovered = {pkg.lower() for pkg in packages}

    logger.info(f"Discovered {len(discovered)} packages")
    logger.debug(f"Discovered packages: {sorted(discovered)}")

    return discovered


def _get_pkg_names(pkgs: List[str]) -> List[str]:
    """Get PyPI package names from a list of imports.

    Args:
        pkgs: List of import names.

    Returns:
        List[str]: The corresponding PyPI package names.

    """
    result: Set[str] = set()
    mapper_path = Path(__file__).parent / "pkg_mapping.json"
    data = {entry["import"]: entry["package"] for entry in json.loads(mapper_path.read_text("utf-8"))}

    for pkg in pkgs:
        result.add(data.get(pkg, pkg))

    return sorted(result, key=lambda s: s.lower())
