from pathlib import Path

from pipzap.cli import PipZapCLI
from pipzap.utils.io import write_toml


def test_requirements_with_duplicates_produces_unique_output(tmp_path: Path, cli_args):
    """Test that duplicate entries in requirements.txt result in unique output."""
    reqs_file = tmp_path / "requirements.txt"
    reqs_file.write_text(
        """requests>=2.31.0
numpy>=1.24.0
flask>=2.3.0
requests>=2.31.0
numpy>=1.24.0
colorama>=0.4.6
colorama>=0.4.6
"""
    )

    output_file = tmp_path / "output.txt"
    args = cli_args(file=reqs_file, output=output_file, no_isolation=True)
    PipZapCLI().run(do_raise=True, args=args)

    output_content = output_file.read_text()
    lines = [
        line.strip()
        for line in output_content.strip().split("\n")
        if line.strip() and not line.startswith("#")
    ]

    package_names = []
    for line in lines:
        name = line.split("==")[0].split(">=")[0].split("<=")[0].split(";")[0].strip()
        package_names.append(name.lower())

    assert len(package_names) == len(set(package_names)), (
        f"Found duplicate packages in output: {package_names}"
    )


def test_pyproject_with_duplicates_produces_unique_output(tmp_path: Path, cli_args):
    """Test that duplicate entries in pyproject.toml result in unique output."""

    pyproject_content = {
        "project": {
            "name": "test-project",
            "version": "0.1.0",
            "requires-python": ">=3.8",
            "dependencies": [
                "requests>=2.31.0",
                "numpy>=1.24.0",
                "flask>=2.3.0",
                "requests>=2.31.0",  # duplicate
                "numpy>=1.24.0",  # duplicate
                "colorama>=0.4.6",
                "colorama>=0.4.6",  # duplicate
            ],
        },
        "tool": {"uv": {}},
    }

    pyproject_file = tmp_path / "pyproject.toml"
    write_toml(pyproject_content, pyproject_file)

    output_file = tmp_path / "output.toml"
    args = cli_args(file=pyproject_file, output=output_file, no_isolation=True, format="uv")
    PipZapCLI().run(do_raise=True, args=args)

    output_content = output_file.read_text()

    assert output_content.count("requests") == 1, f"requests appears multiple times:\n{output_content}"
    assert output_content.count("numpy") == 1, f"numpy appears multiple times:\n{output_content}"
    assert output_content.count("colorama") == 1, f"colorama appears multiple times:\n{output_content}"
