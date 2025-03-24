from typing import Any, Dict

from pipzap.formatting.base import DependenciesFormatter
from pipzap.parsing.converter import ProjectConverter


class PoetryFormatter(DependenciesFormatter):
    """Builds a Poetry pyproject.toml structure from parsed dependencies."""

    TEMPLATE: Dict[str, Any] = {
        "tool": {
            "poetry": {
                "name": ProjectConverter.DUMMY_PROJECT_NAME,
                "version": "0.0.0",
                "description": "",
                "authors": ["Generated <generated@example.com>"],
            }
        }
    }

    def format(self) -> str:
        raise NotImplementedError("Exporting into a poetry-style pyproject.toml is not supported yet.")
