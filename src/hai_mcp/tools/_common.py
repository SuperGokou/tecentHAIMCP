"""Shared MCP tool annotations and helpers."""
from __future__ import annotations

from mcp.types import ToolAnnotations

# Read-only query — safe to call freely.
READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True
)
# Mutating but non-destructive, not safely repeatable.
WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True
)
# Mutating, safe to repeat (e.g. power on an already-running instance).
IDEMPOTENT_WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True
)
# Costly or irreversible — clients may want to confirm first.
DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True
)


def ssh_kwargs(client) -> dict:
    """Build the SSH keyword args for ``ssh_client`` calls from a client's config."""
    cfg = client.config
    return {
        "port": cfg.ssh_port,
        "user": cfg.ssh_user,
        "key_path": cfg.ssh_key_path,
        "password": cfg.ssh_password,
        "known_hosts": cfg.ssh_known_hosts,
    }
