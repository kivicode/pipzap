from pipzap.core.dependencies import ProjectDependencies
from pipzap.formatting.base import DependenciesFormatter
from pipzap.formatting.poetry import PoetryFormatter
from pipzap.parsing.workspace import Workspace


class UVFormatter(DependenciesFormatter):
    """Builds a uv-style pyproject.toml structure from parsed dependencies.

    Operates on top of the :py:class:`~pipzap.formatting.poetry:PoetryFormatter`,
    converting its output with `uvx migrate-to-uv`.
    """

    def __init__(self, dependencies: ProjectDependencies):
        super().__init__(dependencies)
        self._poetry_formatter = PoetryFormatter(dependencies)

    def format(self) -> str:
        poetry_ir = self._poetry_formatter.format()

        with Workspace(None) as workspace:
            pyproject = workspace.base / "pyproject.toml"
            pyproject.write_text(poetry_ir)

            workspace.run(["uvx", "migrate-to-uv"], "migration")
            uv_content = pyproject.read_text()

        return uv_content
