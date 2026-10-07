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
from .hosts.windows_sketches import STANDARD_PLANES
from .daemon.client import DEFAULT_ENDPOINT, call_daemon
from .daemon.main import (
    configure_parser as configure_daemon_parser,
    is_local_daemon_unreachable_error,
    is_local_endpoint,
    run as run_daemon_command,
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
    create_parser = document_commands.add_parser(
        "create", help="create an unsaved part from a real SOLIDWORKS template"
    )
    create_parser.add_argument("--type", choices=("part",), default="part")
    create_parser.add_argument("--template", help="explicit .PRTDOT template path")
    create_parser.add_argument("--json", action="store_true", dest="as_json")
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
    measure_parser = document_commands.add_parser(
        "measure", help="measure all solid bodies in the selected part"
    )
    add_document_selector(measure_parser)
    measure_parser.add_argument("--max-bodies", type=int, default=1000)
    measure_parser.add_argument("--json", action="store_true", dest="as_json")
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
    save_as_parser = document_commands.add_parser(
        "save-as", help="save the selected part to a new native filename"
    )
    save_as_parser.add_argument("output")
    add_document_selector(save_as_parser)
    add_lease_token(save_as_parser)
    save_as_parser.add_argument("--json", action="store_true", dest="as_json")
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

    sketch_parser = subcommands.add_parser(
        "sketch", help="create or inspect explicit part sketches"
    )
    sketch_commands = sketch_parser.add_subparsers(dest="sketch_command", required=True)
    sketch_list_parser = sketch_commands.add_parser(
        "list", help="discover live part sketches without activating or editing"
    )
    sketch_list_parser.add_argument("--max-sketches", type=int, default=1000)
    add_document_selector(sketch_list_parser)
    sketch_list_parser.add_argument("--json", action="store_true", dest="as_json")
    sketch_inspect_parser = sketch_commands.add_parser(
        "inspect", help="read a registered sketch without editing it"
    )
    sketch_inspect_parser.add_argument("sketch_id")
    sketch_inspect_parser.add_argument("--max-segments", type=int, default=1000)
    add_document_selector(sketch_inspect_parser)
    sketch_inspect_parser.add_argument("--json", action="store_true", dest="as_json")
    rectangle_parser = sketch_commands.add_parser(
        "rectangle", help="create and close a new rectangle sketch"
    )
    add_document_selector(rectangle_parser)
    add_lease_token(rectangle_parser)
    rectangle_parser.add_argument(
        "--plane", choices=tuple(STANDARD_PLANES), required=True
    )
    rectangle_parser.add_argument("--width-mm", type=float, required=True)
    rectangle_parser.add_argument("--height-mm", type=float, required=True)
    rectangle_parser.add_argument("--center-x-mm", type=float, default=0.0)
    rectangle_parser.add_argument("--center-y-mm", type=float, default=0.0)
    rectangle_parser.add_argument("--json", action="store_true", dest="as_json")

    circle_parser = sketch_commands.add_parser(
        "circle", help="create and close a new full-circle sketch"
    )
    add_document_selector(circle_parser)
    add_lease_token(circle_parser)
    circle_parser.add_argument("--plane", choices=tuple(STANDARD_PLANES), required=True)
    circle_parser.add_argument("--radius-mm", type=float, required=True)
    circle_parser.add_argument("--center-x-mm", type=float, default=0.0)
    circle_parser.add_argument("--center-y-mm", type=float, default=0.0)
    circle_parser.add_argument("--json", action="store_true", dest="as_json")

    diameter_parser = sketch_commands.add_parser(
        "dimension-diameter",
        help="add a driving diameter to a registered circle sketch",
    )
    diameter_parser.add_argument("sketch_id")
    diameter_parser.add_argument("--diameter-mm", type=float, required=True)
    add_document_selector(diameter_parser)
    add_lease_token(diameter_parser)
    diameter_parser.add_argument("--json", action="store_true", dest="as_json")

    dimension_parser = subcommands.add_parser(
        "dimension", help="inspect or modify registered driving dimensions"
    )
    dimension_commands = dimension_parser.add_subparsers(
        dest="dimension_command", required=True
    )
    dimension_inspect_parser = dimension_commands.add_parser(
        "inspect", help="read a registered dimension in the current configuration"
    )
    dimension_inspect_parser.add_argument("dimension_id")
    add_document_selector(dimension_inspect_parser)
    dimension_inspect_parser.add_argument("--json", action="store_true", dest="as_json")
    dimension_set_parser = dimension_commands.add_parser(
        "set", help="set and verify a driving diameter in the current configuration"
    )
    dimension_set_parser.add_argument("dimension_id")
    dimension_set_parser.add_argument("--value-mm", type=float, required=True)
    add_document_selector(dimension_set_parser)
    add_lease_token(dimension_set_parser)
    dimension_set_parser.add_argument("--json", action="store_true", dest="as_json")

    feature_parser = subcommands.add_parser(
        "feature", help="create explicit part features"
    )
    feature_commands = feature_parser.add_subparsers(
        dest="feature_command", required=True
    )
    extrude_parser = feature_commands.add_parser(
        "extrude", help="extrude a registered 2D sketch"
    )
    extrude_parser.add_argument("sketch_id")
    extrude_parser.add_argument("--depth-mm", type=float, required=True)
    extrude_parser.add_argument("--reverse", action="store_true")
    extrude_parser.add_argument("--no-merge", action="store_false", dest="merge")
    add_document_selector(extrude_parser)
    add_lease_token(extrude_parser)
    extrude_parser.add_argument("--json", action="store_true", dest="as_json")

    cut_parser = feature_commands.add_parser(
        "cut-extrude", help="remove material using a registered sketch and blind depth"
    )
    cut_parser.add_argument("sketch_id")
    cut_parser.add_argument("--depth-mm", type=float, required=True)
    cut_parser.add_argument("--reverse", action="store_true")
    add_document_selector(cut_parser)
    add_lease_token(cut_parser)
    cut_parser.add_argument("--json", action="store_true", dest="as_json")

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
            error_type = type(exc).__name__
            error_message = str(exc)
            if is_local_endpoint(args.endpoint) and is_local_daemon_unreachable_error(exc):
                error_type = "DaemonUnavailable"
                error_message = (
                    f"SWCLI daemon is unavailable at {args.endpoint}; start it explicitly "
                    "with 'sw-cli daemon start', or use "
                    "'sw-cli daemon start --attach-existing' when SOLIDWORKS is already running"
                )
            payload = {
                "ok": False,
                "action": operation,
                "error": {"type": error_type, "message": error_message},
            }
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
    result_schemas = payload["operation_result_schemas"]
    if not isinstance(result_schemas, dict) or set(result_schemas) != set(payload["operations"]):
        return "operation_result_schemas must describe every advertised operation"
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
    mismatch = next(Draft202012Validator(schema).iter_errors(payload), None)
    if mismatch is not None:
        return f"capabilities schema mismatch: {mismatch.message}"
    for operation, result_schema in result_schemas.items():
        if not isinstance(result_schema, dict):
            return f"operation result schema is invalid for {operation}"
        try:
            Draft202012Validator.check_schema(result_schema)
        except SchemaError:
            return f"operation result schema is invalid for {operation}"
        if (result_schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
                or result_schema.get("type") != "object"
                or result_schema.get("additionalProperties") is not False
                or not isinstance(result_schema.get("$id"), str)
                or not result_schema["$id"]):
            return f"operation result schema is invalid for {operation}"
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
    if args.command == "sketch" and args.sketch_command == "list":
        return (
            "sketch.list",
            {"max_sketches": args.max_sketches},
            args.as_json,
            args.document_id,
            args.expected_update_stamp,
            None,
        )
    if args.command == "sketch" and args.sketch_command == "dimension-diameter":
        return (
            "sketch.dimension-diameter",
            {"sketch_id": args.sketch_id, "diameter_mm": args.diameter_mm},
            args.as_json,
            args.document_id,
            args.expected_update_stamp,
            args.lease_id,
        )
    if args.command == "dimension":
        parameters = {"dimension_id": args.dimension_id}
        if args.dimension_command == "set":
            parameters["value_mm"] = args.value_mm
        return (
            f"dimension.{args.dimension_command}",
            parameters,
            args.as_json,
            args.document_id,
            args.expected_update_stamp,
            getattr(args, "lease_id", None),
        )
    if args.command == "sketch" and args.sketch_command == "inspect":
        return (
            "sketch.inspect",
            {"sketch_id": args.sketch_id, "max_segments": args.max_segments},
            args.as_json,
            args.document_id,
            args.expected_update_stamp,
            None,
        )
    if args.command == "feature" and args.feature_command == "cut-extrude":
        return (
            "feature.cut-extrude",
            {
                "sketch_id": args.sketch_id,
                "depth_mm": args.depth_mm,
                "reverse": args.reverse,
            },
            args.as_json,
            args.document_id,
            args.expected_update_stamp,
            args.lease_id,
        )
    if args.command == "feature" and args.feature_command == "extrude":
        return (
            "feature.extrude",
            {
                "sketch_id": args.sketch_id,
                "depth_mm": args.depth_mm,
                "reverse": args.reverse,
                "merge": args.merge,
            },
            args.as_json,
            args.document_id,
            args.expected_update_stamp,
            args.lease_id,
        )
    if args.command == "sketch" and args.sketch_command == "circle":
        return (
            "sketch.circle",
            {
                "plane": args.plane,
                "radius_mm": args.radius_mm,
                "center_x_mm": args.center_x_mm,
                "center_y_mm": args.center_y_mm,
            },
            args.as_json,
            args.document_id,
            args.expected_update_stamp,
            args.lease_id,
        )
    if args.command == "sketch" and args.sketch_command == "rectangle":
        return (
            "sketch.rectangle",
            {
                "plane": args.plane,
                "width_mm": args.width_mm,
                "height_mm": args.height_mm,
                "center_x_mm": args.center_x_mm,
                "center_y_mm": args.center_y_mm,
            },
            args.as_json,
            args.document_id,
            args.expected_update_stamp,
            args.lease_id,
        )
    if args.command == "document":
        command = args.document_command
        if command == "create":
            parameters = {"type": args.type}
            if args.template is not None:
                parameters["template"] = args.template
            return "document.create", parameters, args.as_json, None, None, None
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
        if command == "measure":
            return (
                "document.measure",
                {"max_bodies": args.max_bodies},
                args.as_json,
                args.document_id,
                args.expected_update_stamp,
                None,
            )
        if command == "save-as":
            return (
                "document.save-as",
                {"output": args.output},
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
