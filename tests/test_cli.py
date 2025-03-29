import pytest

from pipzap.cli import PipZapCLI


def test_cli_version_flag(dummy_pyproject, cli_args):
    """Tests CLI exits cleanly with version flag."""
    args = cli_args(file=dummy_pyproject, version=True)
    PipZapCLI().run(args=args)


def test_cli_output_exists_error(dummy_pyproject, tmp_path, cli_args):
    """Tests CLI raises error when output file exists without override."""
    out_file = tmp_path / "out.txt"
    out_file.write_text("existing content")

    args = cli_args(file=dummy_pyproject, output=out_file, override=False)
    cli = PipZapCLI()

    with pytest.raises(ValueError, match="already exists"):
        cli.run(do_raise=True, args=args)
