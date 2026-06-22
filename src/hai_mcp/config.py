"""Runtime configuration for the Tencent HAI MCP server.

All configuration comes from environment variables so secrets never live in
source. A local ``.env`` file in the current directory is loaded automatically
when ``python-dotenv`` is installed (a dev convenience only).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

try:  # optional convenience for local development
    from dotenv import load_dotenv

    # Only load a .env in the current directory — never walk up into parent
    # directories, so the server can't silently inherit an unrelated .env.
    load_dotenv(dotenv_path=".env", override=False)
except Exception:  # pragma: no cover - python-dotenv is optional
    pass

DEFAULT_REGION = "ap-guangzhou"
DEFAULT_SSH_USER = "ubuntu"
DEFAULT_SSH_PORT = 22


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    """Resolved server configuration, built from the process environment.

    Secret fields use ``repr=False`` so they never appear in tracebacks or logs.
    """

    secret_id: str = field(repr=False)
    secret_key: str = field(repr=False)
    region: str = field()
    ssh_user: str = field()
    ssh_port: int = field()
    ssh_key_path: Optional[str] = field()
    ssh_password: Optional[str] = field(repr=False)
    ssh_known_hosts: Optional[str] = field()

    @classmethod
    def from_env(cls) -> "Config":
        """Build a :class:`Config` from environment variables.

        Raises:
            ConfigError: if a required credential is missing or a value is
                malformed, with a message that tells the caller how to fix it.
        """
        secret_id = (os.environ.get("TENCENTCLOUD_SECRET_ID") or "").strip()
        secret_key = (os.environ.get("TENCENTCLOUD_SECRET_KEY") or "").strip()

        missing = [
            name
            for name, value in (
                ("TENCENTCLOUD_SECRET_ID", secret_id),
                ("TENCENTCLOUD_SECRET_KEY", secret_key),
            )
            if not value
        ]
        if missing:
            raise ConfigError(
                "Missing required environment variable(s): "
                + ", ".join(missing)
                + ". Set them in your MCP client config (the `env` block) or a "
                ".env file. Create an API key at "
                "https://console.cloud.tencent.com/cam/capi"
            )

        raw_port = os.environ.get("HAI_SSH_PORT") or DEFAULT_SSH_PORT
        try:
            ssh_port = int(raw_port)
        except (TypeError, ValueError) as exc:
            raise ConfigError(
                f"HAI_SSH_PORT must be an integer, got {raw_port!r}"
            ) from exc

        return cls(
            secret_id=secret_id,
            secret_key=secret_key,
            region=(os.environ.get("HAI_REGION") or DEFAULT_REGION).strip()
            or DEFAULT_REGION,
            ssh_user=(os.environ.get("HAI_SSH_USER") or DEFAULT_SSH_USER).strip()
            or DEFAULT_SSH_USER,
            ssh_port=ssh_port,
            ssh_key_path=(os.environ.get("HAI_SSH_KEY_PATH") or "").strip() or None,
            ssh_password=os.environ.get("HAI_SSH_PASSWORD") or None,
            ssh_known_hosts=(os.environ.get("HAI_SSH_KNOWN_HOSTS") or "").strip() or None,
        )
