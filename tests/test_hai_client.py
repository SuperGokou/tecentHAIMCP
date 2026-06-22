"""Tests for HaiClient orchestration helpers (mocked — no network)."""
from unittest.mock import MagicMock

import pytest

from hai_mcp.config import Config
from hai_mcp.errors import HaiApiError
from hai_mcp.hai_client import HaiClient


def _client(call_side_effect) -> HaiClient:
    """Build a HaiClient bypassing __init__, with a mocked ``.call``."""
    client = HaiClient.__new__(HaiClient)
    client._config = Config(
        secret_id="x",
        secret_key="y",
        region="ap-guangzhou",
        ssh_user="ubuntu",
        ssh_port=22,
        ssh_key_path=None,
        ssh_password=None,
        ssh_known_hosts=None,
    )
    client.call = MagicMock(side_effect=call_side_effect)
    return client


def test_get_instance_not_found_raises():
    client = _client([{"InstanceSet": []}])
    with pytest.raises(HaiApiError):
        client.get_instance("ins-x")


def test_get_public_ip_prefers_describe_instances():
    client = _client([{"InstanceSet": [{"PublicIpAddresses": ["1.2.3.4"]}]}])
    assert client.get_public_ip("ins-x") == "1.2.3.4"


def test_get_public_ip_falls_back_to_network_status():
    client = _client(
        [
            {"InstanceSet": [{"PublicIpAddresses": []}]},
            {"NetworkStatusSet": [{"AddressIp": "5.6.7.8"}]},
        ]
    )
    assert client.get_public_ip("ins-x") == "5.6.7.8"


def test_get_public_ip_none_available_raises():
    client = _client(
        [
            {"InstanceSet": [{"PublicIpAddresses": []}]},
            {"NetworkStatusSet": [{"AddressIp": None}]},
        ]
    )
    with pytest.raises(HaiApiError):
        client.get_public_ip("ins-x")


def test_wait_until_running_returns_when_ready():
    client = _client(
        [{"InstanceSet": [{"InstanceState": "RUNNING", "LatestOperationState": "SUCCESS"}]}]
    )
    instance = client.wait_until_running("ins-x", timeout=5, interval=0)
    assert instance["InstanceState"] == "RUNNING"


def test_wait_until_running_raises_on_launch_failed():
    client = _client([{"InstanceSet": [{"InstanceState": "LAUNCH_FAILED"}]}])
    with pytest.raises(HaiApiError):
        client.wait_until_running("ins-x", timeout=5, interval=0)


def test_wait_until_running_times_out():
    client = _client(lambda *a, **k: {"InstanceSet": [{"InstanceState": "PENDING"}]})
    with pytest.raises(HaiApiError):
        client.wait_until_running("ins-x", timeout=0, interval=0)
