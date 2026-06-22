"""Connection-info tools: web login URLs and network status (read-only)."""
from __future__ import annotations

from typing import Annotated, List, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..hai_client import get_client
from ._common import READ_ONLY


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ_ONLY)
    def hai_get_login_url(
        instance_id: Annotated[str, Field(description="The instance to get web URLs for.")],
        service_name: Annotated[
            Optional[str], Field(description="Restrict to one service, e.g. 'JupyterLab'.")
        ] = None,
        region: Annotated[
            Optional[str], Field(description="Region ID; defaults to the server's HAI_REGION.")
        ] = None,
    ) -> dict:
        """Get ready-to-open web URL(s) for an instance (JupyterLab / WebUI / Gradio).

        Each ``url`` already embeds the auth token — open it in a browser
        directly. The instance must be RUNNING for the services to respond.
        """
        params: dict = {"InstanceId": instance_id}
        if service_name:
            params["ServiceName"] = service_name
        data = get_client(region).call("DescribeServiceLoginSettings", params)
        login = [
            {"service": s.get("ServiceName"), "url": s.get("Url")}
            for s in data.get("LoginSettings") or []
        ]
        return {"instance_id": instance_id, "login": login, "count": len(login)}

    @mcp.tool(annotations=READ_ONLY)
    def hai_get_network(
        instance_ids: Annotated[List[str], Field(description="Instances to report on.")],
        region: Annotated[
            Optional[str], Field(description="Region ID; defaults to the server's HAI_REGION.")
        ] = None,
    ) -> dict:
        """Get public IP, bandwidth cap, and traffic usage for instances."""
        data = get_client(region).call(
            "DescribeInstanceNetworkStatus", {"InstanceIds": instance_ids}
        )
        network = [
            {
                "instance_id": n.get("InstanceId"),
                "public_ip": n.get("AddressIp"),
                "bandwidth_mbps": n.get("Bandwidth"),
                "traffic_total_gb": n.get("TotalTrafficAmount"),
                "traffic_remaining_gb": n.get("RemainingTrafficAmount"),
            }
            for n in data.get("NetworkStatusSet") or []
        ]
        return {"network": network, "count": len(network)}
