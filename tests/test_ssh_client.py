"""Tests for SSH helpers (no network or paramiko required)."""
import pytest

from hai_mcp.ssh_client import CommandResult, SSHError, run_command, upload_file


def test_command_result_ok():
    assert CommandResult(0, "out", "").ok is True
    assert CommandResult(1, "", "err").ok is False


def test_run_command_without_credentials_raises():
    # No key_path and no password -> actionable SSHError before any connection.
    with pytest.raises(SSHError):
        run_command("1.2.3.4", "echo hi")


def test_upload_missing_local_file_raises():
    with pytest.raises(SSHError):
        upload_file("1.2.3.4", "/no/such/file", "/tmp/x", password="pw")
