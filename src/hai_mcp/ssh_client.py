"""SSH / SFTP helpers for running commands and transferring files on a HAI instance.

``paramiko`` is imported lazily so the MCP server can start (and serve all
cloud-control tools) even when ``paramiko`` is not installed. Credentials are
validated before the import so configuration errors are reported clearly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover
    import paramiko


class SSHError(RuntimeError):
    """Raised when an SSH/SFTP operation fails, with an actionable message."""


@dataclass(frozen=True)
class CommandResult:
    """Outcome of a single remote command."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


# Directories we refuse to read from when uploading, to reduce the blast radius
# of a prompt-injection attack that tries to exfiltrate local credentials.
_SENSITIVE_DIRS = tuple(
    os.path.normcase(os.path.abspath(os.path.expanduser(p)))
    for p in ("~/.ssh", "~/.aws", "~/.gnupg", "~/.config/gcloud", "~/.kube", "~/.docker")
)


def _ensure_uploadable(resolved_path: str) -> None:
    norm = os.path.normcase(resolved_path)
    for sensitive in _SENSITIVE_DIRS:
        if norm == sensitive or norm.startswith(sensitive + os.sep):
            raise SSHError(
                f"Refusing to upload from a sensitive directory ({sensitive}). "
                "Copy the file somewhere else if this is intentional."
            )


def _connect(
    host: str,
    port: int,
    user: str,
    key_path: Optional[str] = None,
    password: Optional[str] = None,
    known_hosts: Optional[str] = None,
    timeout: int = 30,
) -> "paramiko.SSHClient":
    if not key_path and not password:
        raise SSHError(
            "No SSH credential configured. Set HAI_SSH_KEY_PATH (a private key "
            "file) or HAI_SSH_PASSWORD so the server can log into the instance."
        )
    if key_path and not os.path.isfile(key_path):
        raise SSHError(f"SSH key file not found: {key_path}")

    try:
        import paramiko
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise SSHError(
            "paramiko is required for remote execution. Install it with "
            "`pip install paramiko`."
        ) from exc

    client = paramiko.SSHClient()
    if known_hosts:
        if not os.path.isfile(known_hosts):
            raise SSHError(f"HAI_SSH_KNOWN_HOSTS file not found: {known_hosts}")
        client.load_host_keys(known_hosts)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    else:
        # HAI instances are ephemeral with first-seen host keys; auto-accept.
        # Set HAI_SSH_KNOWN_HOSTS to enforce verification instead.
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            hostname=host,
            port=port,
            username=user,
            key_filename=key_path or None,
            password=password or None,
            timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
        )
    except Exception as exc:
        # Do not embed the raw exception text — it can carry server-supplied
        # banner data. The original is preserved on the chain via ``from exc``.
        raise SSHError(
            f"Could not SSH into {user}@{host}:{port} — connection failed. Check "
            "that the instance is RUNNING, its public IP is reachable, and the "
            "SSH user/credential are correct."
        ) from exc
    return client


def run_command(
    host: str,
    command: str,
    *,
    port: int = 22,
    user: str = "ubuntu",
    key_path: Optional[str] = None,
    password: Optional[str] = None,
    known_hosts: Optional[str] = None,
    timeout: int = 300,
) -> CommandResult:
    """Run ``command`` on the host over SSH and return exit code, stdout, stderr."""
    client = _connect(host, port, user, key_path, password, known_hosts)
    try:
        _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        exit_code = stdout.channel.recv_exit_status()
        return CommandResult(exit_code=exit_code, stdout=out, stderr=err)
    finally:
        client.close()


def upload_file(
    host: str,
    local_path: str,
    remote_path: str,
    *,
    port: int = 22,
    user: str = "ubuntu",
    key_path: Optional[str] = None,
    password: Optional[str] = None,
    known_hosts: Optional[str] = None,
) -> None:
    """Upload a single local file to ``remote_path`` on the host via SFTP."""
    resolved = os.path.abspath(os.path.expanduser(local_path))
    if not os.path.isfile(resolved):
        raise SSHError(f"Local file not found: {local_path}")
    _ensure_uploadable(resolved)
    client = _connect(host, port, user, key_path, password, known_hosts)
    try:
        sftp = client.open_sftp()
        try:
            sftp.put(resolved, remote_path)
        finally:
            sftp.close()
    finally:
        client.close()
