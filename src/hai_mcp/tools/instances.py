"""Instance lifecycle and pricing tools."""
from __future__ import annotations

from typing import Annotated, List, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..hai_client import get_client
from ._common import DESTRUCTIVE, IDEMPOTENT_WRITE, READ_ONLY

_BUNDLE_TYPES = "XL, XL_2X, 3XL, 3XL_2X, 4XL, 24GB_A"


def _summarize_instance(i: dict) -> dict:
    return {
        "instance_id": i.get("InstanceId"),
        "name": i.get("InstanceName"),
        "state": i.get("InstanceState"),
        "application": i.get("ApplicationName"),
        "bundle": i.get("BundleName"),
        "gpu": i.get("GPUPerformance"),
        "cpu": i.get("CPU"),
        "memory": i.get("Memory"),
        "public_ip": (i.get("PublicIpAddresses") or [None])[0],
        "private_ip": (i.get("PrivateIpAddresses") or [None])[0],
        "latest_operation_state": i.get("LatestOperationState"),
        "created": i.get("CreateTime"),
        "os_type": i.get("OSType"),
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ_ONLY)
    def hai_list_instances(
        instance_ids: Annotated[
            Optional[List[str]], Field(description="Only return these instance ids.")
        ] = None,
        state: Annotated[
            Optional[str],
            Field(description="Filter by state: RUNNING, STOPPED_NO_CHARGE, PENDING, ARREARS."),
        ] = None,
        limit: Annotated[int, Field(ge=1, le=100, description="Maximum instances to return.")] = 20,
        offset: Annotated[int, Field(ge=0, description="Pagination offset.")] = 0,
        region: Annotated[
            Optional[str], Field(description="Region ID; defaults to the server's HAI_REGION.")
        ] = None,
    ) -> dict:
        """List your HAI instances with status and connection info.

        Key states: ``RUNNING`` (billing active), ``STOPPED_NO_CHARGE`` (powered
        off, no compute charge), ``PENDING`` (creating/starting), ``ARREARS``
        (overdue). Note: there is no plain ``STOPPED`` state.
        """
        params: dict = {"Limit": limit, "Offset": offset}
        if instance_ids:
            params["InstanceIds"] = instance_ids
        if state:
            params["Filters"] = [{"Name": "instance-state", "Values": [state]}]
        data = get_client(region).call("DescribeInstances", params)
        instances = [_summarize_instance(i) for i in data.get("InstanceSet") or []]
        return {"instances": instances, "total": data.get("TotalCount"), "count": len(instances)}

    @mcp.tool(annotations=READ_ONLY)
    def hai_inquire_price(
        application_id: Annotated[str, Field(description="Template id from hai_list_applications.")],
        bundle_type: Annotated[str, Field(description=f"Compute package, one of: {_BUNDLE_TYPES}.")],
        disk_size_gb: Annotated[
            Optional[int],
            Field(ge=80, le=1000, description="System disk size; defaults to the template minimum."),
        ] = None,
        instance_count: Annotated[int, Field(ge=1, le=10)] = 1,
        region: Annotated[
            Optional[str], Field(description="Region ID; defaults to the server's HAI_REGION.")
        ] = None,
    ) -> dict:
        """Estimate the price of creating an instance BEFORE creating it.

        Safe, read-only. Run before ``hai_create_instance`` to see the cost.
        """
        params: dict = {
            "ApplicationId": application_id,
            "BundleType": bundle_type,
            "InstanceCount": instance_count,
        }
        if disk_size_gb is not None:
            params["SystemDisk"] = {"DiskSize": disk_size_gb, "DiskType": "CLOUD_PREMIUM"}
        client = get_client(region)
        data = client.call("InquirePriceRunInstances", params)
        return {"price": data.get("Price"), "region": client.region}

    @mcp.tool(annotations=DESTRUCTIVE)
    def hai_create_instance(
        application_id: Annotated[str, Field(description="Template id from hai_list_applications.")],
        bundle_type: Annotated[str, Field(description=f"Compute package, one of: {_BUNDLE_TYPES}.")],
        instance_name: Annotated[
            Optional[str], Field(description="A friendly name (<=128 chars).")
        ] = None,
        disk_size_gb: Annotated[
            Optional[int],
            Field(ge=80, le=1000, description="System disk size in GB (>= template minimum)."),
        ] = None,
        disk_type: Annotated[str, Field(description="CLOUD_PREMIUM or CLOUD_HSSD.")] = "CLOUD_PREMIUM",
        instance_count: Annotated[int, Field(ge=1, le=10)] = 1,
        dry_run: Annotated[
            bool, Field(description="Validate the request without creating anything.")
        ] = False,
        region: Annotated[
            Optional[str], Field(description="Region ID; defaults to the server's HAI_REGION.")
        ] = None,
    ) -> dict:
        """Create (launch) HAI instance(s) from an application template. COSTS MONEY.

        Billing starts as soon as an instance runs. Consider ``hai_inquire_price``
        first, or pass ``dry_run=true`` to validate. Remember ``hai_stop_instance``
        when finished.
        """
        params: dict = {
            "ApplicationId": application_id,
            "BundleType": bundle_type,
            "InstanceCount": instance_count,
            "DryRun": dry_run,
        }
        if instance_name:
            params["InstanceName"] = instance_name
        if disk_size_gb is not None:
            params["SystemDisk"] = {"DiskSize": disk_size_gb, "DiskType": disk_type}
        data = get_client(region).call("RunInstances", params)
        return {"instance_ids": data.get("InstanceIdSet") or [], "dry_run": dry_run}

    @mcp.tool(annotations=IDEMPOTENT_WRITE)
    def hai_start_instance(
        instance_id: Annotated[str, Field(description="The instance to power on.")],
        region: Annotated[
            Optional[str], Field(description="Region ID; defaults to the server's HAI_REGION.")
        ] = None,
    ) -> dict:
        """Power ON a stopped HAI instance. Compute billing resumes while it runs."""
        data = get_client(region).call("StartInstance", {"InstanceId": instance_id})
        return {"instance_id": instance_id, "task_id": data.get("TaskId"), "status": "starting"}

    @mcp.tool(annotations=IDEMPOTENT_WRITE)
    def hai_stop_instance(
        instance_id: Annotated[str, Field(description="The instance to power off.")],
        region: Annotated[
            Optional[str], Field(description="Region ID; defaults to the server's HAI_REGION.")
        ] = None,
    ) -> dict:
        """Power OFF a HAI instance to stop compute billing.

        Uses StopMode ``STOP_CHARGE``: compute is released and billing stops; data
        on the system disk is kept. Start it again with ``hai_start_instance``.
        """
        data = get_client(region).call(
            "StopInstance", {"InstanceId": instance_id, "StopMode": "STOP_CHARGE"}
        )
        return {"instance_id": instance_id, "task_id": data.get("TaskId"), "status": "stopping"}

    @mcp.tool(annotations=DESTRUCTIVE)
    def hai_terminate_instances(
        instance_ids: Annotated[
            List[str], Field(description="The instances to destroy permanently.")
        ],
        region: Annotated[
            Optional[str], Field(description="Region ID; defaults to the server's HAI_REGION.")
        ] = None,
    ) -> dict:
        """PERMANENTLY destroy HAI instance(s). IRREVERSIBLE — all data is lost.

        Use only to delete instances you no longer need. To just pause billing,
        use ``hai_stop_instance`` instead.
        """
        data = get_client(region).call("TerminateInstances", {"InstanceIds": instance_ids})
        return {"terminated": instance_ids, "request_id": data.get("RequestId")}
