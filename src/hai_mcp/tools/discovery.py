"""Discovery tools: regions, scenes, and application templates (all read-only)."""
from __future__ import annotations

from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..hai_client import get_client
from ._common import READ_ONLY


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ_ONLY)
    def hai_list_regions() -> dict:
        """List Tencent Cloud regions where HAI is available.

        Call this first to discover valid region IDs (e.g. ``ap-guangzhou``).
        Only regions whose state is ``AVAILABLE`` can host instances.
        """
        data = get_client().call("DescribeRegions")
        regions = [
            {
                "region": r.get("Region"),
                "name": r.get("RegionName"),
                "state": r.get("RegionState"),
            }
            for r in data.get("RegionSet") or []
        ]
        return {"regions": regions, "count": len(regions)}

    @mcp.tool(annotations=READ_ONLY)
    def hai_list_scenes(
        region: Annotated[
            Optional[str],
            Field(description="Region ID; defaults to the server's HAI_REGION."),
        ] = None,
    ) -> dict:
        """List HAI usage scenes (high-level categories of application templates)."""
        data = get_client(region).call("DescribeScenes", {"Limit": 100})
        scenes = [
            {"scene_id": s.get("SceneId"), "name": s.get("SceneName")}
            for s in data.get("SceneSet") or []
        ]
        return {"scenes": scenes, "count": len(scenes)}

    @mcp.tool(annotations=READ_ONLY)
    def hai_list_applications(
        scene_id: Annotated[
            Optional[str], Field(description="Filter by a scene id from hai_list_scenes.")
        ] = None,
        name: Annotated[
            Optional[str],
            Field(description="Filter by application name, e.g. 'Stable Diffusion'."),
        ] = None,
        limit: Annotated[int, Field(ge=1, le=100, description="Maximum templates to return.")] = 100,
        offset: Annotated[int, Field(ge=0, description="Pagination offset.")] = 0,
        region: Annotated[
            Optional[str],
            Field(description="Region ID; defaults to the server's HAI_REGION."),
        ] = None,
    ) -> dict:
        """List deployable HAI application templates (Stable Diffusion, ChatGLM, ComfyUI, ...).

        Each result includes the ``application_id`` you pass to
        ``hai_create_instance`` and ``min_system_disk_gb`` (the smallest valid
        system-disk size for that template).
        """
        filters = []
        if scene_id:
            filters.append({"Name": "scene-id", "Values": [scene_id]})
        if name:
            filters.append({"Name": "application-name", "Values": [name]})
        params: dict = {"Limit": limit, "Offset": offset}
        if filters:
            params["Filters"] = filters
        data = get_client(region).call("DescribeApplications", params)
        applications = [
            {
                "application_id": a.get("ApplicationId"),
                "name": a.get("ApplicationName"),
                "description": a.get("Description"),
                "type": a.get("ApplicationType"),
                "state": a.get("ApplicationState"),
                "min_system_disk_gb": a.get("MinSystemDiskSize"),
                "size_gb": a.get("ApplicationSize"),
            }
            for a in data.get("ApplicationSet") or []
        ]
        return {
            "applications": applications,
            "total": data.get("TotalCount"),
            "count": len(applications),
        }
