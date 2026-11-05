"""Optional stdio MCP adapter over the existing swclid client; no COM ownership."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from functools import partial
import json
import os
import sys
import threading
import uuid
from typing import Any, Dict, Optional

from jsonschema import Draft202012Validator

from . import __version__
from .daemon.client import DEFAULT_ENDPOINT, call_daemon, parse_endpoint
from .daemon.timeouts import validate_timeout
from .protocol import load_schema


def tool_definitions(*, auto_start: bool = True) -> list[Dict[str, Any]]:
    """Small stable tool list; operation contracts come from the running daemon."""
    fields = load_schema("request")["properties"]
    execute_fields = {
        name: deepcopy(fields[name]) for name in (
            "operation", "parameters", "session_id", "document_id",
            "expected_update_stamp", "lease_id", "request_id",
        )
    }
    descriptions = (
        ("swcli_status", "Read swclid health and host identity. First call lazily starts a local daemon unless connect-only; never automatically attaches a user instance.", {}),
        ("swcli_capabilities", "Discover running daemon operations; pass operation for its exact input/result schemas and x-swcli-context. Start with the small summary.", {
            "operation": {"type": "string", "minLength": 1},
        }),
        ("swcli_execute", "Execute one advertised SWCLI operation with its exact parameters and document/session/lease/CAS context. Read its schema first. Writes, saving and closing require task authority. Paths belong to the host. No retries or rollback; inspect on failure. Daemon lifecycle uses the CLI.", execute_fields),
    )
    return [
        {
            "name": name,
            "description": description,
            "inputSchema": {
                "type": "object", "additionalProperties": False,
                "properties": properties,
                "required": ["operation", "parameters"] if name == "swcli_execute" else [],
            },
            "annotations": {
                "readOnlyHint": name != "swcli_execute" and not auto_start,
                "destructiveHint": name == "swcli_execute",
                "idempotentHint": name != "swcli_execute",
                "openWorldHint": True,
            },
        }
        for name, description, properties in descriptions
    ]


class DaemonBridge:
    """Forward one request once, keeping native errors and request identity."""

    def __init__(
        self, *, endpoint: Optional[str] = None, session_id: Optional[str] = None,
        timeout_seconds: float = 600.0, connect_timeout_seconds: float = 3.0,
        auto_start: bool = True, startup_timeout_seconds: float = 120.0,
    ):
        self.endpoint = endpoint or os.environ.get("SWCLI_ENDPOINT", DEFAULT_ENDPOINT)
        parse_endpoint(self.endpoint)
        self.timeout_seconds = validate_timeout(timeout_seconds, name="request timeout", margin=10)
        self.connect_timeout_seconds = validate_timeout(connect_timeout_seconds, name="connection timeout")
        self.session_id = session_id or os.environ.get("SWCLI_SESSION_ID") or f"mcp-{uuid.uuid4()}"
        self.schemas = {tool["name"]: tool["inputSchema"] for tool in tool_definitions()}
        self.response_validator = Draft202012Validator(load_schema("response"))
        self.auto_start = auto_start
        self.startup_timeout_seconds = validate_timeout(startup_timeout_seconds, name="startup timeout", margin=15)
        self._prepare_lock = threading.Lock()
        self._prepared = False
        self._prepare_error = None

    def _ensure_daemon(self):
        # One lazy preflight per MCP process. Never restart an unhealthy or lost
        # daemon after an established session, and never start a remote host.
        if not self.auto_start:
            return
        with self._prepare_lock:
            if self._prepare_error is not None:
                raise RuntimeError(self._prepare_error)
            if self._prepared:
                return
            try:
                from .client_startup import ensure_local_daemon
                ensure_local_daemon(
                    endpoint=self.endpoint,
                    connect_timeout_seconds=self.connect_timeout_seconds,
                    startup_timeout_seconds=self.startup_timeout_seconds,
                )
                self._prepared = True
            except Exception as exc:
                # Repeated tool calls must not repeatedly launch native hosts.
                self._prepare_error = str(exc)
                raise

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
                operation, parameters = "daemon.health", {}
            elif name == "swcli_capabilities":
                operation, parameters = "daemon.capabilities", {"include_schemas": False, **arguments}
            else:
                operation = arguments.pop("operation")
                parameters = arguments.pop("parameters")
                if operation == "daemon.shutdown":
                    raise ValueError("daemon lifecycle requires an explicit sw-cli daemon command")
            # Reuse DockerSW's optional native-path mapping, exactly as the CLI does.
            from .cli import translate_parameter_paths
            translate_parameter_paths(parameters)
            self._ensure_daemon()
            submitted = True
            response = call_daemon(
                operation, parameters, endpoint=self.endpoint,
                timeout_seconds=self.timeout_seconds if name == "swcli_execute" else 10.0,
                connect_timeout_seconds=self.connect_timeout_seconds,
                request_id=request_id,
                session_id=arguments.get("session_id", self.session_id) if name == "swcli_execute" else self.session_id,
                **{key: arguments[key] for key in ("document_id", "expected_update_stamp", "lease_id") if key in arguments},
            )
            self.response_validator.validate(response)
            return response
        except Exception as exc:
            # A read timeout/disconnect cannot establish whether a mutation occurred.
            # No retry or new native call is made by this adapter.
            return {
                "success": False, "request_id": request_id,
                "error": {"code": type(exc).__name__, "message": str(exc)},
                "outcome_unknown": submitted and getattr(exc, "_swcli_transport_phase", None) != "connect",
            }


def create_server(bridge: DaemonBridge):
    """Load the optional official SDK only when the MCP server is requested."""
    from mcp import types
    from mcp.server.lowlevel import Server
    import anyio

    server = Server(
        "swcli", version=__version__,
        instructions=(
            "Lazily starts or reuses local swclid; remote endpoints are connection-only. First call swcli_status and "
            "swcli_capabilities; request one operation schema before swcli_execute. "
            "Use explicit documents, fresh stamps and leases for writes. Tool structuredContent "
            "is the full swclid response: check success, then result or error. "
            "MCP disconnect/cancellation does not stop SOLIDWORKS or undo work. "
            "Never blindly retry a timeout; retain request_id and inspect native state."
        ),
    )

    @server.list_tools()
    async def list_tools():
        return [types.Tool(**tool) for tool in tool_definitions(auto_start=bridge.auto_start)]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]):
        # Keep stdin/ping responsive while the existing daemon serializes STA work.
        # anyio does not abandon the thread on cancellation by default.
        payload = await anyio.to_thread.run_sync(partial(bridge.call, name, arguments))
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
            structuredContent=payload, isError=not payload.get("success", False),
        )

    return server


def configure_parser(subcommands) -> None:
    parser = subcommands.add_parser("mcp", help="connect MCP clients to existing swclid (optional extra)")
    commands = parser.add_subparsers(dest="mcp_command", required=True)
    serve = commands.add_parser("serve", help="serve MCP over stdio; lazily start/reuse local swclid")
    serve.add_argument("--connect-only", action="store_true", help="only use an existing daemon")
    serve.add_argument("--startup-timeout", type=float, default=120.0, help="local daemon startup timeout in seconds")


async def serve(bridge: DaemonBridge) -> None:
    from mcp.server.stdio import stdio_server

    server = create_server(bridge)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run(args) -> int:
    if sys.version_info < (3, 10):
        print("SWCLI MCP requires Python 3.10+ and the swcli[mcp] extra; the CLI still supports Python 3.9.", file=sys.stderr)
        return 2
    try:
        bridge = DaemonBridge(
            endpoint=args.endpoint, session_id=args.session,
            timeout_seconds=args.request_timeout, connect_timeout_seconds=args.connect_timeout,
            auto_start=not args.connect_only, startup_timeout_seconds=args.startup_timeout,
        )
        asyncio.run(serve(bridge))
    except ModuleNotFoundError as exc:
        if exc.name == "mcp" or (exc.name or "").startswith("mcp."):
            print('Install MCP support in this Python environment: python -m pip install "swcli[mcp]" (or ".[mcp]" from a checkout).', file=sys.stderr)
            return 2
        raise
    except KeyboardInterrupt:
        return 130
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0
