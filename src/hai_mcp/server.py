"""Entry point for the Tencent HAI MCP server (stdio transport)."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import tools

INSTRUCTIONS = """\
This server controls Tencent Cloud HAI (High-Performance Application Service).

Typical workflows:
- Deploy YOUR OWN app onto an existing instance:
    hai_list_instances -> hai_deploy(instance_id, ["cd ~/app && git pull", "./start.sh"])
  hai_deploy powers the instance on if needed, runs your steps, and returns the web URL.
- Launch a prebuilt template (Stable Diffusion, ChatGLM, ...):
    hai_list_applications -> hai_inquire_price -> hai_create_instance -> (wait) -> hai_get_login_url
- Manage cost: hai_stop_instance when finished (stops billing, keeps data);
  hai_terminate_instances only to delete permanently.

Notes:
- Instance states: RUNNING, STOPPED_NO_CHARGE (off, no charge), PENDING, ARREARS.
- hai_create_instance and hai_terminate_instances are flagged destructive (cost / data loss).
- Remote tools (hai_run_command, hai_upload_file, hai_deploy) need HAI_SSH_* configured.
"""


def build_server() -> FastMCP:
    """Construct the FastMCP server with all HAI tools registered."""
    mcp = FastMCP("tencent-hai", instructions=INSTRUCTIONS)
    tools.register_all(mcp)
    return mcp


def main() -> None:
    """Run the server over stdio (the entry point used by MCP clients)."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
