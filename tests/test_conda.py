"""Tests for conda environment.yml support."""

from pathlib import Path

import pytest

from pipzap.cli import PipZapCLI
from pipzap.core.source_format import SourceFormat


def test_detect_conda_format_yml():
    """Test that .yml files are detected as conda format."""
    assert SourceFormat.detect_format(Path("environment.yml")) == SourceFormat.CONDA


def test_detect_conda_format_yaml():
    """Test that .yaml files are detected as conda format."""
    assert SourceFormat.detect_format(Path("environment.yaml")) == SourceFormat.CONDA


def test_conda_with_pip_deps(tmp_path: Path, cli_args):
    """Test processing a conda environment.yml with pip dependencies."""
    env_file = tmp_path / "environment.yml"
    env_file.write_text(
        """name: test-env
channels:
  - conda-forge
dependencies:
  - python=3.10
  - numpy
  - pip
  - pip:
    - requests>=2.28.0
    - flask>=2.0.0
"""
    )

    output_file = tmp_path / "output.yml"
    args = cli_args(file=env_file, output=output_file, no_isolation=True)
    PipZapCLI().run(do_raise=True, args=args)

    output_content = output_file.read_text()

    # Check conda deps are preserved
    assert "name: test-env" in output_content
    assert "conda-forge" in output_content
    assert "python=3.10" in output_content
    assert "numpy" in output_content

    # Check pip deps are present
    assert "requests" in output_content
    assert "flask" in output_content


def test_conda_preserves_formatting(tmp_path: Path, cli_args):
    """Test that conda formatting is preserved."""
    env_file = tmp_path / "environment.yml"
    # Use specific formatting with comments
    env_file.write_text(
        """# My project environment
name: my-project
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.10
  - numpy>=1.20
  - pip
  - pip:
    - requests>=2.28.0
"""
    )

    output_file = tmp_path / "output.yml"
    args = cli_args(file=env_file, output=output_file, no_isolation=True)
    PipZapCLI().run(do_raise=True, args=args)

    output_content = output_file.read_text()

    assert "# My project environment" in output_content
    assert "name: my-project" in output_content


def test_conda_with_duplicate_pip_deps(tmp_path: Path, cli_args):
    """Test that duplicate pip dependencies are deduplicated."""
    env_file = tmp_path / "environment.yml"
    env_file.write_text(
        """name: test-env
dependencies:
  - python=3.10
  - pip
  - pip:
    - requests>=2.28.0
    - flask>=2.0.0
    - requests>=2.27.0
    - flask>=1.0.0
"""
    )

    output_file = tmp_path / "output.yml"
    args = cli_args(file=env_file, output=output_file, no_isolation=True)
    PipZapCLI().run(do_raise=True, args=args)

    output_content = output_file.read_text()

    assert output_content.count("requests") == 1, f"requests duplicated:\n{output_content}"
    assert output_content.count("flask") == 1, f"flask duplicated:\n{output_content}"


def test_conda_no_pip_section_raises_error(tmp_path: Path, cli_args):
    """Test that conda files without pip section raise an error."""
    env_file = tmp_path / "environment.yml"
    env_file.write_text(
        """name: test-env
dependencies:
  - python=3.10
  - numpy
"""
    )

    args = cli_args(file=env_file, no_isolation=True)

    with pytest.raises(Exception, match="No pip dependencies"):
        PipZapCLI().run(do_raise=True, args=args)


def test_conda_extracts_python_version(tmp_path: Path, cli_args):
    """Test that Python version is extracted from conda dependencies."""
    env_file = tmp_path / "environment.yml"
    env_file.write_text(
        """name: test-env
dependencies:
  - python=3.11
  - pip
  - pip:
    - requests>=2.28.0
"""
    )

    output_file = tmp_path / "output.yml"
    args = cli_args(file=env_file, output=output_file, no_isolation=True, python_version=None)
    PipZapCLI().run(do_raise=True, args=args)

    assert output_file.exists()
