"""Tests for environment-driven configuration."""
import pytest

from hai_mcp.config import DEFAULT_REGION, DEFAULT_SSH_USER, Config, ConfigError

_ALL_VARS = (
    "TENCENTCLOUD_SECRET_ID",
    "TENCENTCLOUD_SECRET_KEY",
    "HAI_REGION",
    "HAI_SSH_USER",
    "HAI_SSH_PORT",
    "HAI_SSH_KEY_PATH",
    "HAI_SSH_PASSWORD",
)


def _clear(monkeypatch):
    for var in _ALL_VARS:
        monkeypatch.delenv(var, raising=False)


def test_missing_credentials_raises(monkeypatch):
    _clear(monkeypatch)
    with pytest.raises(ConfigError):
        Config.from_env()


def test_from_env_reads_values_and_defaults(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("TENCENTCLOUD_SECRET_ID", "id")
    monkeypatch.setenv("TENCENTCLOUD_SECRET_KEY", "key")

    cfg = Config.from_env()

    assert cfg.secret_id == "id"
    assert cfg.secret_key == "key"
    assert cfg.region == DEFAULT_REGION
    assert cfg.ssh_user == DEFAULT_SSH_USER
    assert cfg.ssh_port == 22
    assert cfg.ssh_key_path is None
    assert cfg.ssh_password is None


def test_overrides_are_applied(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("TENCENTCLOUD_SECRET_ID", "id")
    monkeypatch.setenv("TENCENTCLOUD_SECRET_KEY", "key")
    monkeypatch.setenv("HAI_REGION", "ap-shanghai")
    monkeypatch.setenv("HAI_SSH_PORT", "2222")
    monkeypatch.setenv("HAI_SSH_KEY_PATH", "/tmp/id_rsa")

    cfg = Config.from_env()

    assert cfg.region == "ap-shanghai"
    assert cfg.ssh_port == 2222
    assert cfg.ssh_key_path == "/tmp/id_rsa"


def test_invalid_port_raises(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("TENCENTCLOUD_SECRET_ID", "id")
    monkeypatch.setenv("TENCENTCLOUD_SECRET_KEY", "key")
    monkeypatch.setenv("HAI_SSH_PORT", "not-a-number")

    with pytest.raises(ConfigError):
        Config.from_env()
