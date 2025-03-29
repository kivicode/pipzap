import pytest
import tomlkit

from pipzap.core.source_format import SourceFormat
from pipzap.exceptions import ParsingError, ResolutionError
from pipzap.parsing.workspace import Workspace
from pipzap.utils.debug import is_debug
from pipzap.utils.io import read_toml, write_toml
from pipzap.utils.pretty_string import remove_prefix


def test_external_command_failures():
    """Tests Workspace handling of external command failures."""

    with Workspace(None) as ws:
        with pytest.raises(ResolutionError):
            ws.run(["uv", "nonexistent-command-hopefully"], "test")


def test_invalid_file_formats(tmp_path):
    """Tests detection of unsupported file formats."""
    file = tmp_path / "invalid.xyz"
    file.write_text("not a valid TOML content")

    with pytest.raises(ParsingError, match="Cannot determine format"):
        SourceFormat.detect_format(file)


def test_remove_prefix():
    """Tests prefix removal with various cases."""
    assert remove_prefix("pipzap_dependency", "pipzap_") == "dependency", "Prefix should be removed"
    assert remove_prefix("aaa", "a", num_iters=3) == "", "Multiple prefix iterations should work :/"
    assert remove_prefix("no_prefix", "prefix_") == "no_prefix", "No prefix should leave string unchanged"


def test_read_write_toml(tmp_path):
    """Tests that TOML data is correctly written and read back."""
    data = {"section": {"key": "value", "list": [1, 2, 3]}}
    file = tmp_path / "config.toml"

    write_toml(data, file)
    result = read_toml(file)

    assert result == data, "Read TOML should match written data"


def test_read_toml_invalid(tmp_path):
    """Test reading an invalid TOML file raises an error."""
    file = tmp_path / "invalid.toml"
    file.write_text("invalid content")

    with pytest.raises(tomlkit.exceptions.ParseError):
        read_toml(file)


def test_is_debug_env(monkeypatch):
    """Test debug flag detection from environment variables."""
    monkeypatch.setenv("PIPZAP_DEBUG", "1")
    assert is_debug() is True, "Debug should be True when PIPZAP_DEBUG is set"

    monkeypatch.delenv("PIPZAP_DEBUG", raising=False)
    assert is_debug() is False, "Debug should be False when PIPZAP_DEBUG is unset"
