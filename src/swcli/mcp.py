"""Optional MCP stdio frontend; all CAD work uses the existing swclid protocol."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from functools import partial
import json
import os
import sys
import uuid
from typing import Any, Dict, Optional

from jsonschema import Draft202012Validator

from . import __version__
from .daemon.client import DEFAULT_ENDPOINT, call_daemon, parse_endpoint
from .daemon.timeouts import validate_timeout
from .daemon_manager import DaemonManager
from .protocol import load_schema

STARTUP_MESSAGE = (
    "Starting swclid and SOLIDWORKS can take tens of seconds to several minutes. "
    "This call waits for readiness. Do not start again while it is pending; "
    "after a timeout, inspect status before deciding what to do."
)


def tool_definitions() -> list[Dict[str, Any]]:
    fields = load_schema("request")["properties"]
    execute = {name: deepcopy(fields[name]) for name in (
        "operation", "parameters", "session_id", "document_id", "expected_update_stamp", "lease_id", "request_id",
    )}
    definitions = (
        ("swcli_status", "Observe daemon availability, SW ownership, user/other instances and window visibility without starting anything. Unknown and startup-cached observations are explicit.", {}),
        ("swcli_daemon_start", STARTUP_MESSAGE + " Explicitly start or reuse the selected local host. The host launcher owns Wine/Python selection. visible affects only a newly owned SW; attach_existing explicitly shares a user SW and preserves its window.", {
            "visible": {"type": "boolean", "default": False},
            "attach_existing": {"type": "boolean", "default": False},
            "startup_timeout_seconds": {"type": "number", "exclusiveMinimum": 0, "maximum": 600, "default": 120},
        }),
        ("swcli_daemon_stop", "Explicit global daemon shutdown affects every client sharing this endpoint. The existing worker refuses to exit an owned SW while any document is open; save/close explicitly first. Attached user SW is preserved. Does not stop this MCP connection or auto-restart anything.", {
            "request_id": deepcopy(fields["request_id"]),
        }),
        ("swcli_capabilities", "Discover running daemon operations; pass operation for its exact request/result schemas and x-swcli-context. Does not start SW; query status and explicitly start first if needed.", {
            "operation": {"type": "string", "minLength": 1},
        }),
        ("swcli_execute", "Execute one advertised SWCLI operation with exact parameters and session/document/lease/CAS context. Read its schema first. Does not start or recover SW. Writes/save/close require task authority. Host paths, native errors and partial-state rules are preserved. Use the explicit daemon tools for lifecycle.", execute),
    )
    return [{
        "name": name, "description": description,
        "inputSchema": {"type": "object", "additionalProperties": False, "properties": properties,
                        "required": ["operation", "parameters"] if name == "swcli_execute" else []},
        "annotations": {"readOnlyHint": name in ("swcli_status", "swcli_capabilities"),
                        "destructiveHint": name in ("swcli_execute", "swcli_daemon_stop"),
                        "idempotentHint": name in ("swcli_status", "swcli_capabilities"), "openWorldHint": True},
    } for name, description, properties in definitions]


class DaemonBridge:
    def __init__(self, *, endpoint: Optional[str] = None, session_id: Optional[str] = None,
                 timeout_seconds: float = 600.0, connect_timeout_seconds: float = 3.0,
                 host_launcher: Optional[str] = None):
        self.endpoint = endpoint or os.environ.get("SWCLI_ENDPOINT", DEFAULT_ENDPOINT)
        parse_endpoint(self.endpoint)
        self.timeout_seconds = validate_timeout(timeout_seconds, name="request timeout", margin=10)
        self.connect_timeout_seconds = validate_timeout(connect_timeout_seconds, name="connection timeout")
        self.session_id = session_id or os.environ.get("SWCLI_SESSION_ID") or f"mcp-{uuid.uuid4()}"
        self.schemas = {tool["name"]: tool["inputSchema"] for tool in tool_definitions()}
        self.response_validator = Draft202012Validator(load_schema("response"))
        self.manager = DaemonManager(endpoint=self.endpoint, host_launcher=host_launcher,
                                     connect_timeout_seconds=self.connect_timeout_seconds)

    def call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        request_id = str(uuid.uuid4())
        submitted = False
        try:
            if name not in self.schemas:
                raise ValueError(f"unknown MCP tool: {name}")
            Draft202012Validator(self.schemas[name]).validate(arguments)
            arguments = deepcopy(arguments)
            request_id = arguments.pop("request_id", request_id)
            if name == "swcli_status":
                result = self.manager.status()
            elif name == "swcli_daemon_start":
                submitted = True
                result = self.manager.start(**arguments)
            elif name == "swcli_daemon_stop":
                submitted = True
                result = self.manager.stop(request_id=request_id, timeout_seconds=self.timeout_seconds)
            else:
                if name == "swcli_capabilities":
                    operation, parameters = "daemon.capabilities", {"include_schemas": False, **arguments}
                else:
                    operation, parameters = arguments.pop("operation"), arguments.pop("parameters")
                    if operation == "daemon.shutdown":
                        raise ValueError("use swcli_daemon_stop for explicit global shutdown")
                from .cli import translate_parameter_paths
                translate_parameter_paths(parameters)
                submitted = True
                result = call_daemon(
                    operation, parameters, endpoint=self.endpoint,
                    timeout_seconds=self.timeout_seconds if name == "swcli_execute" else 10,
                    connect_timeout_seconds=self.connect_timeout_seconds, request_id=request_id,
                    session_id=arguments.get("session_id", self.session_id) if name == "swcli_execute" else self.session_id,
                    **{key: arguments[key] for key in ("document_id", "expected_update_stamp", "lease_id") if key in arguments},
                )
                self.response_validator.validate(result)
            result.setdefault("request_id", request_id)
            return result
        except Exception as exc:
            return {"success": False, "request_id": request_id,
                    "error": {"code": type(exc).__name__, "message": str(exc)},
                    "outcome_unknown": submitted and getattr(exc, "_swcli_transport_phase", None) != "connect"}


def create_server(bridge: DaemonBridge):
    from mcp import types
    from mcp.server.lowlevel import Server
    import anyio
    server = Server("swcli", version=__version__, instructions=(
        "No lazy startup. First swcli_status; if necessary explicitly call swcli_daemon_start. "
        + STARTUP_MESSAGE + " Then query swcli_capabilities for one operation schema and call swcli_execute. "
        "Use explicit document IDs, leases and fresh stamps for writes. Check success and result/error in "
        "structuredContent; visibility_current=false is a startup report, not a live window observation. "
        "Stopping affects the shared endpoint; never discard open documents to stop it. "
        "MCP disconnect does not stop SW; swcli_daemon_stop is explicit and keeps MCP alive."
    ))

    @server.list_tools()
    async def list_tools():
        return [types.Tool(**tool) for tool in tool_definitions()]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]):
        meta = server.request_context.meta
        token = getattr(meta, "progressToken", None) if meta is not None else None
        if name == "swcli_daemon_start" and token is not None:
            await server.request_context.session.send_progress_notification(token, 0, 1, STARTUP_MESSAGE)
        payload = await anyio.to_thread.run_sync(partial(bridge.call, name, arguments))
        if name == "swcli_daemon_start" and token is not None:
            message = "Daemon/SW startup finished; inspect the returned readiness." if payload.get("success") else "Startup failed; inspect the error and status before another start."
            await server.request_context.session.send_progress_notification(token, 1, 1, message)
        return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
                                    structuredContent=payload, isError=not payload.get("success", False))
    return server


def configure_parser(subcommands):
    parser = subcommands.add_parser("mcp", help="serve the optional MCP frontend for SWCLI")
    commands = parser.add_subparsers(dest="mcp_command", required=True)
    commands.add_parser("serve", help="serve MCP stdio; daemon start/stop are explicit tools")


async def serve(bridge):
    from mcp.server.stdio import stdio_server
    server = create_server(bridge)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run(args):
    if sys.version_info < (3, 10):
        print("SWCLI MCP requires Python 3.10+ and swcli[mcp]; base CLI supports Python 3.9.", file=sys.stderr)
        return 2
    try:
        bridge = DaemonBridge(endpoint=args.endpoint, session_id=args.session,
                              timeout_seconds=args.request_timeout, connect_timeout_seconds=args.connect_timeout,
                              host_launcher=args.host_launcher)
        asyncio.run(serve(bridge))
    except ModuleNotFoundError as exc:
        if exc.name == "mcp" or (exc.name or "").startswith("mcp."):
            print('Install python -m pip install "swcli[mcp]" (or ".[mcp]" from source).', file=sys.stderr)
            return 2
        raise
    except KeyboardInterrupt:
        return 130
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0
