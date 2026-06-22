"""Authenticated client wrapper around the Tencent Cloud HAI SDK.

Centralizes credential handling, region selection, a generic ``call`` method (so
tool code stays declarative), friendly error translation, and a few
orchestration helpers used by the deploy tools.
"""
from __future__ import annotations

import json
import time
from dataclasses import replace
from typing import Any, Optional

from .config import Config
from .errors import HaiApiError, to_friendly_error

_ENDPOINT = "hai.tencentcloudapi.com"


class HaiClient:
    """Thin, authenticated facade over ``tencentcloud.hai.v20230812``."""

    def __init__(self, config: Config) -> None:
        self._config = config
        try:
            from tencentcloud.common import credential
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
            from tencentcloud.hai.v20230812 import hai_client, models
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise HaiApiError(
                "The Tencent Cloud HAI SDK is not installed. Run "
                "`pip install tencentcloud-sdk-python-hai`."
            ) from exc

        self._models = models
        cred = credential.Credential(config.secret_id, config.secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = _ENDPOINT
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        self._client = hai_client.HaiClient(cred, config.region, client_profile)

    @property
    def region(self) -> str:
        return self._config.region

    @property
    def config(self) -> Config:
        return self._config

    def call(self, action: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Invoke a HAI API action by name and return the response as a dict.

        Args:
            action: PascalCase action name, e.g. ``"DescribeInstances"``.
            params: Request parameters using the API's PascalCase field names.

        Raises:
            HaiApiError: with code, message and RequestId when the call fails.
        """
        request_cls = getattr(self._models, f"{action}Request")
        request = request_cls()
        request.from_json_string(json.dumps(params or {}))
        try:
            response = getattr(self._client, action)(request)
        except Exception as exc:  # noqa: BLE001 - normalized into HaiApiError
            raise to_friendly_error(exc, action) from exc
        return json.loads(response.to_json_string())

    # ----- orchestration helpers -----

    def get_instance(self, instance_id: str) -> dict[str, Any]:
        data = self.call("DescribeInstances", {"InstanceIds": [instance_id]})
        instances = data.get("InstanceSet") or []
        if not instances:
            raise HaiApiError(
                f"Instance '{instance_id}' was not found in region '{self.region}'. "
                "Check the id and region."
            )
        return instances[0]

    def get_public_ip(self, instance_id: str) -> str:
        instance = self.get_instance(instance_id)
        for ip in instance.get("PublicIpAddresses") or []:
            if ip:
                return ip
        net = self.call("DescribeInstanceNetworkStatus", {"InstanceIds": [instance_id]})
        for status in net.get("NetworkStatusSet") or []:
            if status.get("AddressIp"):
                return status["AddressIp"]
        raise HaiApiError(
            f"Instance '{instance_id}' has no public IP yet. It may still be "
            "starting or have no public network. Wait until it is RUNNING."
        )

    def wait_until_running(
        self, instance_id: str, timeout: int = 600, interval: int = 10
    ) -> dict[str, Any]:
        """Poll until the instance is RUNNING, or raise on failure/timeout."""
        deadline = time.time() + timeout
        while True:
            instance = self.get_instance(instance_id)
            state = instance.get("InstanceState")
            op_state = instance.get("LatestOperationState")
            if state == "RUNNING" and op_state in (None, "", "SUCCESS"):
                return instance
            if state in ("LAUNCH_FAILED", "TERMINATING", "TERMINATED"):
                raise HaiApiError(
                    f"Instance '{instance_id}' is in state {state}; it will not "
                    "become ready."
                )
            if time.time() >= deadline:
                raise HaiApiError(
                    f"Timed out after {timeout}s waiting for instance "
                    f"'{instance_id}' to be RUNNING (last state: {state})."
                )
            time.sleep(interval)


_base_config: Optional[Config] = None
_clients: "dict[str, HaiClient]" = {}


def get_client(region: Optional[str] = None) -> HaiClient:
    """Return a cached :class:`HaiClient` for ``region`` (or the default region)."""
    global _base_config
    if _base_config is None:
        _base_config = Config.from_env()
    target = region or _base_config.region
    client = _clients.get(target)
    if client is None:
        cfg = _base_config if target == _base_config.region else replace(_base_config, region=target)
        client = HaiClient(cfg)
        _clients[target] = client
    return client


def reset_clients() -> None:
    """Clear cached config/clients. Intended for tests."""
    global _base_config
    _base_config = None
    _clients.clear()
