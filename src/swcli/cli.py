"""Command-line entry point for SWCLI."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from typing import Any, Dict, Optional, Sequence, Tuple

from . import PROTOCOL_VERSION, __version__
from .hosts import (
    RENDER_VIEWS,
    doctor_windows_host,
)
from .protocol import SCHEMA_NAMES, load_schema
from .daemon.client import DEFAULT_ENDPOINT, call_daemon
from .daemon.main import (
    configure_parser as configure_daemon_parser,
    is_local_daemon_unreachable_error,
    is_local_endpoint,
    run as run_daemon_command,
    start_daemon,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sw-cli",
        description="Cross-platform SOLIDWORKS automation client",
    )
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("SWCLI_ENDPOINT", DEFAULT_ENDPOINT),
        help="daemon HOST:PORT endpoint for all typed operations",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=600.0,
        help="daemon request timeout in seconds",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=3.0,
        help="daemon TCP connection timeout in seconds",
    )
    parser.add_argument(
        "--session",
        default=os.environ.get("SWCLI_SESSION_ID"),
        help="daemon-side current-document session (default: shared default session)",
    )
    parser.add_argument(
        "--request-id",
        help="stable idempotency key for one typed request (default: random UUID)",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    version_parser = subcommands.add_parser("version", help="show client versions")
    version_parser.add_argument("--json", action="store_true", dest="as_json")

    protocol_parser = subcommands.add_parser(
        "protocol", help="inspect the versioned SWCLI protocol"
    )
    protocol_commands = protocol_parser.add_subparsers(
        dest="protocol_command", required=True
    )
    show_parser = protocol_commands.add_parser("show", help="print a JSON Schema")
    show_parser.add_argument("schema", choices=SCHEMA_NAMES)

    daemon_parser = subcommands.add_parser(
        "daemon", help="manage the resident SOLIDWORKS service"
    )
    configure_daemon_parser(daemon_parser)

    doctor_parser = subcommands.add_parser(
        "doctor", help="inspect the local host and daemon without changing either"
    )
    doctor_parser.add_argument("--json", action="store_true", dest="as_json")

    capabilities_parser = subcommands.add_parser(
        "capabilities", help="query the capabilities of a running daemon"
    )
    capabilities_parser.add_argument(
        "--json", action="store_true", dest="as_json"
    )

    document_parser = subcommands.add_parser(
        "document", help="open and inspect SOLIDWORKS documents"
    )
    document_commands = document_parser.add_subparsers(
        dest="document_command", required=True
    )
    open_parser = document_commands.add_parser(
        "open", help="open a SOLIDWORKS document silently"
    )
    open_parser.add_argument("path")
    open_parser.add_argument("--read-only", action="store_true")
    open_parser.add_argument("--configuration", default="")
    open_parser.add_argument("--json", action="store_true", dest="as_json")
    list_parser = document_commands.add_parser(
        "list", help="list open documents and their short-lived IDs"
    )
    list_parser.add_argument("--json", action="store_true", dest="as_json")
    use_parser = document_commands.add_parser(
        "use", help="set the current document for this CLI session"
    )
    use_parser.add_argument("document_id")
    use_parser.add_argument("--json", action="store_true", dest="as_json")

    def add_document_target(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument(
            "--document",
            dest="document_id",
            help="target a d-... document ID, or 'active' for this command only",
        )

    def add_document_selector(command_parser: argparse.ArgumentParser) -> None:
        add_document_target(command_parser)
        command_parser.add_argument(
            "--if-update-stamp",
            type=int,
            dest="expected_update_stamp",
            help="run only if GetUpdateStamp still equals this value",
        )

    def add_lease_token(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument(
            "--lease",
            dest="lease_id",
            help="active l-... lease token for this document operation",
        )

    lease_parser = document_commands.add_parser(
        "lease", help="manage a short-lived exclusive document lease"
    )
    lease_commands = lease_parser.add_subparsers(
        dest="lease_command", required=True
    )
    lease_acquire_parser = lease_commands.add_parser(
        "acquire", help="acquire or renew this session's document lease"
    )
    add_document_target(lease_acquire_parser)
    lease_acquire_parser.add_argument("--ttl-seconds", type=int, default=60)
    lease_acquire_parser.add_argument("--json", action="store_true", dest="as_json")
    lease_status_parser = lease_commands.add_parser(
        "status", help="inspect the selected document lease"
    )
    add_document_target(lease_status_parser)
    lease_status_parser.add_argument("--json", action="store_true", dest="as_json")
    lease_renew_parser = lease_commands.add_parser(
        "renew", help="renew a lease owned by this session"
    )
    lease_renew_parser.add_argument("lease_id")
    lease_renew_parser.add_argument("--ttl-seconds", type=int, default=60)
    lease_renew_parser.add_argument("--json", action="store_true", dest="as_json")
    lease_release_parser = lease_commands.add_parser(
        "release", help="release a lease owned by this session"
    )
    lease_release_parser.add_argument("lease_id")
    lease_release_parser.add_argument("--json", action="store_true", dest="as_json")

    inspect_parser = document_commands.add_parser(
        "inspect", help="inspect the selected or current SOLIDWORKS document"
    )
    add_document_selector(inspect_parser)
    inspect_parser.add_argument(
        "--detail", choices=("summary", "structure"), default="summary"
    )
    inspect_parser.add_argument("--max-features", type=int, default=500)
    inspect_parser.add_argument("--json", action="store_true", dest="as_json")
    close_parser = document_commands.add_parser(
        "close", help="close the selected or current SOLIDWORKS document"
    )
    add_document_selector(close_parser)
    add_lease_token(close_parser)
    close_parser.add_argument(
        "--discard",
        action="store_true",
        help="discard modifications instead of refusing to close",
    )
    close_parser.add_argument("--json", action="store_true", dest="as_json")
    save_parser = document_commands.add_parser(
        "save", help="save the selected or current SOLIDWORKS document in place"
    )
    add_document_selector(save_parser)
    add_lease_token(save_parser)
    save_parser.add_argument("--json", action="store_true", dest="as_json")
    diagnose_parser = document_commands.add_parser(
        "diagnose", help="report rebuild state and feature errors"
    )
    add_document_selector(diagnose_parser)
    diagnose_parser.add_argument("--max-features", type=int, default=500)
    diagnose_parser.add_argument("--json", action="store_true", dest="as_json")
    rebuild_parser = document_commands.add_parser(
        "rebuild", help="rebuild the active SOLIDWORKS document"
    )
    add_document_selector(rebuild_parser)
    add_lease_token(rebuild_parser)
    rebuild_parser.add_argument("--force", action="store_true")
    rebuild_parser.add_argument(
        "--top-only",
        action="store_true",
        help="with --force, rebuild only top-level assembly features",
    )
    rebuild_parser.add_argument("--max-features", type=int, default=500)
    rebuild_parser.add_argument("--json", action="store_true", dest="as_json")
    render_parser = document_commands.add_parser(
        "render", help="render the selected or current document to a BMP image"
    )
    add_document_selector(render_parser)
    add_lease_token(render_parser)
    render_parser.add_argument("output")
    render_parser.add_argument("--width", type=int, default=1024)
    render_parser.add_argument("--height", type=int, default=768)
    render_parser.add_argument(
        "--view",
        choices=RENDER_VIEWS,
        default="current",
        help="use the current orientation or a locale-independent standard view",
    )
    render_parser.add_argument(
        "--no-fit", action="store_false", dest="fit", help="preserve the current zoom"
    )
    render_parser.add_argument("--overwrite", action="store_true")
    render_parser.add_argument("--json", action="store_true", dest="as_json")
    export_parser = document_commands.add_parser(
        "export", help="export the selected or current document"
    )
    add_document_selector(export_parser)
    add_lease_token(export_parser)
    export_parser.add_argument("output")
    export_parser.add_argument("--overwrite", action="store_true")
    export_parser.add_argument(
        "--strict",
        action="store_true",
        help="require a saved, rebuilt source and preserve its state",
    )
    export_parser.add_argument("--json", action="store_true", dest="as_json")

    part_parser = subcommands.add_parser("part", help="create and modify part models")
    part_commands = part_parser.add_subparsers(dest="part_command", required=True)
    box_parser = part_commands.add_parser(
        "create-box", help="create a centered rectangular extrusion"
    )
    box_parser.add_argument("output")
    box_parser.add_argument("--width-mm", type=float, required=True)
    box_parser.add_argument("--height-mm", type=float, required=True)
    box_parser.add_argument("--depth-mm", type=float, required=True)
    box_parser.add_argument(
        "--template",
        help="existing .PRTDOT file; otherwise resolve the configured or installed default",
    )
    box_parser.add_argument("--overwrite", action="store_true")
    box_parser.add_argument("--json", action="store_true", dest="as_json")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    _configure_output()
    args = build_parser().parse_args(argv)

    if args.command == "version":
        payload = {
            "name": "SWCLI",
            "client_version": __version__,
            "protocol_version": PROTOCOL_VERSION,
        }
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(
                f"SWCLI {payload['client_version']} "
                f"(protocol {payload['protocol_version']})"
            )
        return 0

    if args.command == "protocol" and args.protocol_command == "show":
        print(json.dumps(load_schema(args.schema), ensure_ascii=False, indent=2))
        return 0

    if args.command == "daemon":
        return run_daemon_command(args)

    if args.command == "capabilities":
        return _run_capabilities(args)

    typed = _typed_operation(args)
    if typed is not None:
        (
            operation,
            parameters,
            as_json,
            document_id,
            expected_update_stamp,
            lease_id,
        ) = typed
        request_id = args.request_id or str(uuid.uuid4())
        try:
            translate_parameter_paths(parameters)
            response = call_daemon(
                operation,
                parameters,
                endpoint=args.endpoint,
                timeout_seconds=args.request_timeout,
                connect_timeout_seconds=args.connect_timeout,
                request_id=request_id,
                session_id=args.session,
                document_id=document_id,
                expected_update_stamp=expected_update_stamp,
                lease_id=lease_id,
            )
        except Exception as exc:
            response = _autostart_and_retry(
                args,
                operation,
                parameters,
                document_id,
                expected_update_stamp,
                lease_id,
                request_id,
                exc,
            )
            if response is None:
                payload = {
                    "ok": False,
                    "action": operation,
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
            else:
                payload = _typed_payload(operation, response)
        else:
            payload = _typed_payload(operation, response)
        _print_action_result(payload, as_json)
        return 0 if payload.get("ok") else 1

    if args.command == "doctor":
        payload = doctor_windows_host()
        try:
            response = call_daemon(
                "daemon.health",
                endpoint=args.endpoint,
                timeout_seconds=min(args.request_timeout, 10.0),
                connect_timeout_seconds=args.connect_timeout,
            )
        except Exception as exc:
            payload["daemon"] = {
                "reachable": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        else:
            payload["daemon"] = {
                "reachable": bool(response.get("success")),
                "health": response.get("result"),
            }
            if not response.get("success"):
                error = response.get("error") or {}
                payload["daemon"]["error"] = {
                    "type": error.get("code", "DaemonError"),
                    "message": error.get("message", "daemon health check failed"),
                }
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            registration = payload.get("registration") or {}
            com = payload.get("com") or {}
            daemon = payload["daemon"]
            print(f"Platform: {payload['host']['platform']} ({payload['host']['machine']})")
            print(f"Supported: {'yes' if payload['supported'] else 'no'}")
            print(f"SOLIDWORKS registration: {registration.get('current_version') or 'not found'}")
            print(f"SOLIDWORKS executable: {registration.get('local_server') or 'not found'}")
            print(f"Active COM server: {'attached' if com.get('attached') else 'not attached'}")
            if com.get("revision"):
                print(f"SOLIDWORKS revision: {com['revision']}")
            print(f"daemon: {'reachable' if daemon['reachable'] else 'unreachable'}")
        return 0

    return 2


def _run_capabilities(args: argparse.Namespace) -> int:
    """Query a running daemon without implicitly starting a local host."""

    try:
        response = call_daemon(
            "daemon.health",
            endpoint=args.endpoint,
            timeout_seconds=min(args.request_timeout, 10.0),
            connect_timeout_seconds=args.connect_timeout,
        )
    except Exception as exc:
        payload: Dict[str, Any] = {
            "ok": False,
            "action": "capabilities",
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }
    else:
        if not response.get("success"):
            error = response.get("error") or {}
            payload = {
                "ok": False,
                "action": "capabilities",
                "error": {
                    "type": error.get("code", "DaemonError"),
                    "message": error.get(
                        "message", "daemon capability query failed"
                    ),
                },
            }
        else:
            capabilities = response.get("result")
            mismatch = _capabilities_mismatch(capabilities)
            if mismatch is None:
                payload = capabilities
            else:
                payload = {
                    "ok": False,
                    "action": "capabilities",
                    "error": {
                        "type": "CapabilitiesMismatch",
                        "message": mismatch,
                    },
                }

    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    elif payload.get("ok") is False:
        _print_action_result(payload, False)
    else:
        host = payload["host"]
        print(f"Server: {payload['server_version']}")
        print(f"Protocols: {', '.join(payload['protocol_versions'])}")
        print(f"Worker: {'ready' if payload['worker_alive'] else 'unavailable'}")
        print(f"Host connected: {'yes' if payload['host_connected'] else 'no'}")
        if host is None:
            print("Host: unavailable")
        else:
            print(
                "Host: "
                f"{host['platform']} / SOLIDWORKS {host['solidworks_revision']}"
            )
        print(f"Operations: {', '.join(payload['operations'])}")
        if payload["recovery_required"]:
            print(
                "Recovery required: "
                f"{payload['recovery_error']['code']}"
            )
    return 1 if payload.get("ok") is False else 0


def _capabilities_mismatch(payload: Any) -> Optional[str]:
    """Return why a health payload cannot satisfy the public capabilities schema."""

    if not isinstance(payload, dict):
        return "daemon returned a non-object capabilities payload"
    schema = load_schema("capabilities")
    expected = set(schema["properties"])
    actual = set(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        return f"capabilities fields differ; missing={missing}, unknown={unknown}"
    if not isinstance(payload["server_version"], str):
        return "server_version must be a string"
    if not (
        isinstance(payload["protocol_versions"], list)
        and payload["protocol_versions"]
        and all(isinstance(value, str) for value in payload["protocol_versions"])
        and len(payload["protocol_versions"])
        == len(set(payload["protocol_versions"]))
    ):
        return "protocol_versions must be a non-empty unique string array"
    if not (
        isinstance(payload["operations"], list)
        and all(isinstance(value, str) for value in payload["operations"])
        and len(payload["operations"]) == len(set(payload["operations"]))
    ):
        return "operations must be a unique string array"
    operation_schemas = payload["operation_schemas"]
    if not isinstance(operation_schemas, dict) or set(operation_schemas) != set(
        payload["operations"]
    ):
        return "operation_schemas must describe every advertised operation"
    operation_schema_fields = {
        "$schema",
        "$id",
        "title",
        "type",
        "additionalProperties",
        "properties",
        "required",
        "x-swcli-context",
    }
    context_fields = {"document_id", "expected_update_stamp", "lease_id"}
    context_modes = {"forbidden", "optional", "required"}
    for operation, operation_schema in operation_schemas.items():
        if not isinstance(operation_schema, dict) or set(operation_schema) != (
            operation_schema_fields
        ):
            return f"operation schema fields are invalid for {operation}"
        if (
            operation_schema.get("$schema")
            != "https://json-schema.org/draft/2020-12/schema"
            or operation_schema.get("type") != "object"
            or operation_schema.get("additionalProperties") is not False
            or not isinstance(operation_schema.get("properties"), dict)
            or not isinstance(operation_schema.get("required"), list)
            or not set(operation_schema["required"]).issubset(
                operation_schema["properties"]
            )
        ):
            return f"operation parameter schema is invalid for {operation}"
        context = operation_schema.get("x-swcli-context")
        if (
            not isinstance(context, dict)
            or set(context) != context_fields
            or not all(value in context_modes for value in context.values())
        ):
            return f"operation context schema is invalid for {operation}"
    request_replay = payload["request_replay"]
    if (
        not isinstance(request_replay, dict)
        or set(request_replay)
        != {"supported", "max_entries", "max_bytes", "scope"}
        or request_replay.get("supported") is not True
        or not isinstance(request_replay.get("max_entries"), int)
        or isinstance(request_replay.get("max_entries"), bool)
        or request_replay["max_entries"] < 1
        or not isinstance(request_replay.get("max_bytes"), int)
        or isinstance(request_replay.get("max_bytes"), bool)
        or request_replay["max_bytes"] < 1
        or request_replay.get("scope") != "daemon"
    ):
        return "request_replay does not match the capabilities schema"
    if not isinstance(payload["worker_alive"], bool):
        return "worker_alive must be a boolean"
    if not isinstance(payload["host_connected"], bool):
        return "host_connected must be a boolean"
    if not isinstance(payload["recovery_required"], bool):
        return "recovery_required must be a boolean"

    recovery_error = payload["recovery_error"]
    if recovery_error is not None and (
        not isinstance(recovery_error, dict)
        or set(recovery_error) != {"code", "message"}
        or not all(
            isinstance(recovery_error.get(name), str)
            for name in ("code", "message")
        )
        or not recovery_error.get("code")
    ):
        return "recovery_error must be null or contain string code and message"
    if payload["recovery_required"] != (recovery_error is not None):
        return "recovery_required and recovery_error disagree"
    if payload["host_connected"] != (
        payload["worker_alive"]
        and payload["host"] is not None
        and not payload["recovery_required"]
    ):
        return "host_connected disagrees with worker, host, or recovery state"

    host = payload["host"]
    if host is not None:
        host_schema = schema["properties"]["host"]["oneOf"][0]
        if not isinstance(host, dict) or set(host) != set(
            host_schema["properties"]
        ):
            return "host fields do not match the capabilities schema"
        if not all(
            isinstance(host.get(name), str)
            for name in ("revision", "solidworks_revision", "language")
        ):
            return "host revisions and language must be strings"
        if (
            not isinstance(host.get("process_id"), int)
            or isinstance(host.get("process_id"), bool)
            or host["process_id"] < 1
        ):
            return "host process_id must be a positive integer"
        if not all(
            isinstance(host.get(name), bool)
            for name in ("visible", "owned_by_daemon", "shared_interactive")
        ):
            return "host state flags must be booleans"
        startup_wait = host.get("startup_wait_seconds")
        if (
            not isinstance(startup_wait, (int, float))
            or isinstance(startup_wait, bool)
            or startup_wait < 0
        ):
            return "host startup_wait_seconds must be a non-negative number"
        if host.get("platform") not in {"windows", "macos-wine", "linux-wine"}:
            return "host platform is unsupported"
    return None


def _typed_payload(operation: str, response: Dict[str, Any]) -> Dict[str, Any]:
    result = response.get("result")
    if isinstance(result, dict):
        payload = dict(result)
    else:
        payload = {
            "ok": False,
            "action": operation,
            "error": {
                "type": (response.get("error") or {}).get("code", "DaemonError"),
                "message": (response.get("error") or {}).get(
                    "message", "daemon request failed"
                ),
            },
        }
    if response.get("request_id"):
        payload["request_id"] = response["request_id"]
    if response.get("replayed") is True:
        payload["replayed"] = True
    return payload


def _autostart_and_retry(
    args: argparse.Namespace,
    operation: str,
    parameters: Dict[str, Any],
    document_id: Optional[str],
    expected_update_stamp: Optional[int],
    lease_id: Optional[str],
    request_id: str,
    connection_error: BaseException,
) -> Optional[Dict[str, Any]]:
    """Start a missing local Windows daemon, then retry one typed request."""

    if (
        sys.platform != "win32"
        or not is_local_endpoint(args.endpoint)
        or not is_local_daemon_unreachable_error(connection_error)
    ):
        return None
    started = start_daemon(endpoint=args.endpoint)
    if not started.get("success"):
        return started
    try:
        return call_daemon(
            operation,
            parameters,
            endpoint=args.endpoint,
            timeout_seconds=args.request_timeout,
            connect_timeout_seconds=args.connect_timeout,
            request_id=request_id,
            session_id=args.session,
            document_id=document_id,
            expected_update_stamp=expected_update_stamp,
            lease_id=lease_id,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": {"code": type(exc).__name__, "message": str(exc)},
        }


def _typed_operation(
    args: argparse.Namespace,
) -> Optional[
    Tuple[
        str,
        Dict[str, Any],
        bool,
        Optional[str],
        Optional[int],
        Optional[str],
    ]
]:
    """Map public typed CLI arguments to the daemon-only protocol surface."""
    if args.command == "document":
        command = args.document_command
        if command == "open":
            return (
                "document.open",
                {
                    "path": args.path,
                    "read_only": args.read_only,
                    "configuration": args.configuration,
                },
                args.as_json,
                None,
                None,
                None,
            )
        if command == "list":
            return "document.list", {}, args.as_json, None, None, None
        if command == "use":
            return "document.use", {}, args.as_json, args.document_id, None, None
        if command == "lease":
            lease_command = args.lease_command
            if lease_command == "acquire":
                return (
                    "document.lease.acquire",
                    {"ttl_seconds": args.ttl_seconds},
                    args.as_json,
                    args.document_id,
                    None,
                    None,
                )
            if lease_command == "status":
                return (
                    "document.lease.status",
                    {},
                    args.as_json,
                    args.document_id,
                    None,
                    None,
                )
            if lease_command == "renew":
                return (
                    "document.lease.renew",
                    {"ttl_seconds": args.ttl_seconds},
                    args.as_json,
                    None,
                    None,
                    args.lease_id,
                )
            if lease_command == "release":
                return (
                    "document.lease.release",
                    {},
                    args.as_json,
                    None,
                    None,
                    args.lease_id,
                )
        if command == "inspect":
            return (
                "document.inspect",
                {"detail": args.detail, "max_features": args.max_features},
                args.as_json,
                args.document_id,
                args.expected_update_stamp,
                None,
            )
        if command == "close":
            return (
                "document.close",
                {"discard": args.discard},
                args.as_json,
                args.document_id,
                args.expected_update_stamp,
                args.lease_id,
            )
        if command == "save":
            return (
                "document.save",
                {},
                args.as_json,
                args.document_id,
                args.expected_update_stamp,
                args.lease_id,
            )
        if command == "diagnose":
            return (
                "document.diagnose",
                {"max_features": args.max_features},
                args.as_json,
                args.document_id,
                args.expected_update_stamp,
                None,
            )
        if command == "rebuild":
            return (
                "document.rebuild",
                {
                    "force": args.force,
                    "top_only": args.top_only,
                    "max_features": args.max_features,
                },
                args.as_json,
                args.document_id,
                args.expected_update_stamp,
                args.lease_id,
            )
        if command == "render":
            return (
                "document.render",
                {
                    "output": args.output,
                    "width": args.width,
                    "height": args.height,
                    "view": args.view,
                    "fit": args.fit,
                    "overwrite": args.overwrite,
                },
                args.as_json,
                args.document_id,
                args.expected_update_stamp,
                args.lease_id,
            )
        if command == "export":
            return (
                "document.export",
                {
                    "output": args.output,
                    "overwrite": args.overwrite,
                    "strict": args.strict,
                },
                args.as_json,
                args.document_id,
                args.expected_update_stamp,
                args.lease_id,
            )
    if args.command == "part" and args.part_command == "create-box":
        parameters = {
            "output": args.output,
            "width_mm": args.width_mm,
            "height_mm": args.height_mm,
            "depth_mm": args.depth_mm,
            "overwrite": args.overwrite,
        }
        if args.template is not None:
            parameters["template"] = args.template
        return (
            "part.create-box",
            parameters,
            args.as_json,
            None,
            None,
            None,
        )
    return None


def _configure_output() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


PATH_PARAMETER_NAMES = ("path", "output", "template")


def translate_parameter_paths(parameters: Dict[str, Any]) -> None:
    """Translate known path parameters in place using the host helper command.

    Hosts that mix POSIX and Windows filesystems (for example Wine containers)
    export SWCLI_PATH_TRANSLATE_CMD pointing at a helper that maps a single
    path argument to the host's native form. The client knows which parameters
    are paths, so it applies the helper to exactly those fields instead of
    leaving a shell wrapper to guess from argument positions.
    """

    command = os.environ.get("SWCLI_PATH_TRANSLATE_CMD")
    if not command:
        return
    for name in PATH_PARAMETER_NAMES:
        value = parameters.get(name)
        if isinstance(value, str) and value:
            parameters[name] = subprocess.check_output(
                [command, value], text=True
            ).strip()


def _print_action_result(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    state = "ok" if payload["ok"] else "failed"
    print(f"SWCLI {payload['action']}: {state}")
    if payload.get("error"):
        print(f"{payload['error']['type']}: {payload['error']['message']}")
