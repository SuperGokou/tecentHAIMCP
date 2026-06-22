"""Remote-execution tools: run commands, upload files, and one-shot deploy over SSH."""
from __future__ import annotations

from typing import Annotated, List, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..errors import HaiApiError
from ..hai_client import get_client
from ..ssh_client import run_command, upload_file
from ._common import WRITE, ssh_kwargs


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=WRITE)
    def hai_run_command(
        instance_id: Annotated[str, Field(description="Instance to run the command on.")],
        command: Annotated[str, Field(description="Shell command to execute, e.g. 'nvidia-smi'.")],
        timeout: Annotated[
            int, Field(ge=1, le=3600, description="Seconds before the command times out.")
        ] = 300,
        region: Annotated[
            Optional[str], Field(description="Region ID; defaults to the server's HAI_REGION.")
        ] = None,
    ) -> dict:
        """Run a shell command on a HAI instance over SSH; returns stdout, stderr, exit code.

        The instance's public IP is resolved automatically. Requires the
        ``HAI_SSH_*`` settings to be configured. The instance must be RUNNING.
        """
        client = get_client(region)
        host = client.get_public_ip(instance_id)
        result = run_command(host, command, timeout=timeout, **ssh_kwargs(client))
        return {
            "instance_id": instance_id,
            "host": host,
            "exit_code": result.exit_code,
            "ok": result.ok,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    @mcp.tool(annotations=WRITE)
    def hai_upload_file(
        instance_id: Annotated[str, Field(description="Target instance.")],
        local_path: Annotated[str, Field(description="Path to a local file to upload.")],
        remote_path: Annotated[str, Field(description="Destination path on the instance.")],
        region: Annotated[
            Optional[str], Field(description="Region ID; defaults to the server's HAI_REGION.")
        ] = None,
    ) -> dict:
        """Upload a local file to a HAI instance via SFTP (push code or a model file)."""
        client = get_client(region)
        host = client.get_public_ip(instance_id)
        upload_file(host, local_path, remote_path, **ssh_kwargs(client))
        return {
            "instance_id": instance_id,
            "host": host,
            "remote_path": remote_path,
            "uploaded": True,
        }

    @mcp.tool(annotations=WRITE)
    def hai_deploy(
        instance_id: Annotated[str, Field(description="Instance to deploy onto.")],
        commands: Annotated[
            List[str],
            Field(
                description="Deploy steps run in order, e.g. ['cd ~/app && git pull', './start.sh']."
            ),
        ],
        start_if_stopped: Annotated[
            bool, Field(description="Power the instance on first if it is stopped.")
        ] = True,
        wait_timeout: Annotated[
            int,
            Field(ge=30, le=3600, description="Seconds to wait for the instance to reach RUNNING."),
        ] = 600,
        command_timeout: Annotated[
            int,
            Field(ge=1, le=3600, description="Seconds before each deploy command times out."),
        ] = 600,
        region: Annotated[
            Optional[str], Field(description="Region ID; defaults to the server's HAI_REGION.")
        ] = None,
    ) -> dict:
        """One-shot deploy of your own app: ensure RUNNING, run your steps, return URLs.

        The 'deploy my app in one sentence' workflow:
        1. If the instance is stopped and ``start_if_stopped`` is true, power it on
           (which resumes billing) and wait until it is RUNNING.
        2. Run each command in ``commands`` over SSH, stopping at the first failure.
        3. Return every command's output plus the instance's web access URL(s).
        """
        client = get_client(region)
        instance = client.get_instance(instance_id)
        state = instance.get("InstanceState")
        started = False
        if state != "RUNNING":
            if not start_if_stopped:
                raise HaiApiError(
                    f"Instance '{instance_id}' is {state}, not RUNNING. Set "
                    "start_if_stopped=true to power it on automatically."
                )
            if state == "STOPPED_NO_CHARGE":
                client.call("StartInstance", {"InstanceId": instance_id})
                started = True
            elif state != "PENDING":
                raise HaiApiError(
                    f"Instance '{instance_id}' is in state {state}; cannot deploy."
                )
            client.wait_until_running(instance_id, timeout=wait_timeout)

        host = client.get_public_ip(instance_id)
        results = []
        all_ok = True
        for command in commands:
            result = run_command(host, command, timeout=command_timeout, **ssh_kwargs(client))
            results.append(
                {
                    "command": command,
                    "exit_code": result.exit_code,
                    "ok": result.ok,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )
            if not result.ok:
                all_ok = False
                break

        login_error = None
        try:
            login = client.call("DescribeServiceLoginSettings", {"InstanceId": instance_id})
            urls = [
                {"service": s.get("ServiceName"), "url": s.get("Url")}
                for s in login.get("LoginSettings") or []
            ]
        except Exception as exc:  # noqa: BLE001 - URLs are best-effort
            urls = []
            login_error = str(exc)

        response = {
            "instance_id": instance_id,
            "host": host,
            "started": started,
            "all_ok": all_ok,
            "results": results,
            "login": urls,
        }
        if login_error:
            response["login_error"] = login_error
        return response
