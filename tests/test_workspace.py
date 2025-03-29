import os
import shutil
import stat
import subprocess
from threading import Thread

import pytest

from pipzap.exceptions import ResolutionError
from pipzap.parsing.workspace import BackupPath, Workspace


def test_workspace_backup_restore(tmp_path):
    """Tests that the original file is restored after modification."""
    source = tmp_path / "source.txt"
    source.write_text("original")

    with Workspace(source, no_isolation=True, restore_backup=True) as ws:
        ws.path.write_text("modified")

    assert source.read_text() == "original", "Original file should be restored"


def test_workspace_no_restore_warning(tmp_path):
    """Tests that a warning is raised when no_isolation=True and restore_backup=False."""
    source = tmp_path / "source.txt"
    source.write_text("original")

    with pytest.raises(ResourceWarning, match="dangerous"):
        with Workspace(source, no_isolation=True, restore_backup=False) as ws:
            ws.path.write_text("modified")

    assert source.read_text() == "original"


def test_workspace_isolation(tmp_path):
    """Tests that isolation creates a temporary directory."""
    source = tmp_path / "source.txt"
    source.write_text("original")

    with Workspace(source, no_isolation=False) as ws:
        assert ws.base != tmp_path, "Workspace should use a different directory in isolation mode"
        ws.path.write_text("modified")

    assert source.read_text() == "original", "Original file should remain unchanged in isolation"


def test_workspace_run_success(monkeypatch):
    """Tests successful command execution within Workspace."""

    def fake_run(cmd, *args, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="success", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with Workspace(None) as ws:
        output = ws.run(["dummy"], "test")
        assert "success" in output, "Command output should contain 'success'"


def test_workspace_run_failure(tmp_path, monkeypatch):
    """Tests command failure handling within Workspace."""

    def fake_run(cmd, *args, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, output="fail", stderr="error")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with Workspace(None) as ws:
        with pytest.raises(ResolutionError):
            ws.run(["dummy"], "test")


def test_concurrent_workspace_access(tmp_path):
    """Tests that concurrent Workspace instances manage backups independently."""
    source = tmp_path / "shared.txt"
    source.write_text("original")
    results = []

    def worker(id):
        with Workspace(source, no_isolation=True, restore_backup=True) as ws:
            ws.path.write_text(f"modified by {id}")
            results.append(ws.path.read_text())

    threads = [Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()

    for t in threads:
        t.join()

    assert source.read_text() == "original", "Original file should be restored after concurrent access"
    assert len(results) == 2, "Both threads should have completed"


def test_workspace_permission_error(tmp_path, monkeypatch):
    """Tests backup failure due to permission issues."""
    source = tmp_path / "source.txt"
    source.write_text("original")

    backup_dir = tmp_path / "readonly"
    backup_dir.mkdir()
    os.chmod(backup_dir, stat.S_IREAD)  # read-only

    orig_with_path = BackupPath.with_path

    def fake_with_path(self, base, fname=None):
        return orig_with_path(self, backup_dir, fname)

    monkeypatch.setattr(BackupPath, "with_path", fake_with_path)
    with pytest.raises(PermissionError):
        with Workspace(source):
            ...


def test_workspace_cleanup_failure(tmp_path, monkeypatch):
    """Tests handling of cleanup failures."""
    source = tmp_path / "source.txt"
    source.write_text("original")

    def fake_rmtree(path, ignore_errors=False):
        raise OSError("Cleanup failed")

    monkeypatch.setattr(shutil, "rmtree", fake_rmtree)
    with pytest.raises(OSError, match="Cleanup failed"):
        with Workspace(source):
            ...

    assert source.read_text() == "original", "Original file should remain after cleanup failure"


def test_workspace_symlink_handling(tmp_path):
    """Tests that modifications via symlinks are handled correctly."""
    real_file = tmp_path / "real.txt"
    real_file.write_text("real content")

    symlink = tmp_path / "symlink.txt"
    symlink.symlink_to(real_file)

    with Workspace(symlink) as ws:
        ws.path.write_text("modified via symlink")

    assert real_file.read_text() == "real content", "Original file should remain unchanged via symlink"


def test_workspace_large_file(tmp_path):
    """Tests handling of large files during backup and restore."""
    source = tmp_path / "large.txt"
    data = "X" * (10 * 1024 * 1024)

    source.write_text(data)
    with Workspace(source, no_isolation=True, restore_backup=True) as ws:
        ws.path.write_text("modified")

    assert source.read_text() == data, "Original large file should be restored"
