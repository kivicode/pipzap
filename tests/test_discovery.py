from pathlib import Path

from pipzap.cli import PipZapCLI
from pipzap.discovery import discover_dependencies


def test_discover_dependencies(tmp_path: Path):
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """
import requests
import numpy as np
from flask import Flask
import sys
"""
    )

    discovered = discover_dependencies(tmp_path)

    assert "requests" in discovered
    assert "numpy" in discovered
    assert "flask" in discovered
    assert "sys" not in discovered


def test_cli_discover_with_requirements(tmp_path: Path, cli_args):
    test_file = tmp_path / "app.py"
    test_file.write_text("import requests")

    reqs_file = tmp_path / "requirements.txt"
    reqs_file.write_text("requests==2.31.0\nnumpy==1.24.0\nflask==2.3.0")

    output_file = tmp_path / "output.txt"

    args = cli_args(file=reqs_file, output=output_file, discover=True, no_isolation=True)
    PipZapCLI().run(do_raise=True, args=args)

    output_content = output_file.read_text()
    assert "requests" in output_content
    assert "numpy" not in output_content
    assert "flask" not in output_content


def test_cli_discover_with_directory_no_file(tmp_path: Path, cli_args):
    test_file = tmp_path / "main.py"
    test_file.write_text("import requests")

    output_file = tmp_path / "requirements.txt"

    args = cli_args(file=tmp_path, output=output_file, discover=True, no_isolation=True)
    PipZapCLI().run(do_raise=True, args=args)

    output_content = output_file.read_text()
    assert "requests" in output_content


def test_cli_discover_with_directory_finds_existing_file(tmp_path: Path, cli_args):
    test_file = tmp_path / "app.py"
    test_file.write_text("import requests")

    reqs_file = tmp_path / "requirements.txt"
    reqs_file.write_text("requests==2.31.0\nnumpy==1.24.0")

    output_file = tmp_path / "output.txt"

    args = cli_args(file=tmp_path, output=output_file, discover=True, no_isolation=True)
    PipZapCLI().run(do_raise=True, args=args)

    output_content = output_file.read_text()
    assert "requests" in output_content
    assert "numpy" not in output_content
