from pathlib import Path
from typing import Set

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
        imports = pipreqs.get_pkg_names(imports)
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
