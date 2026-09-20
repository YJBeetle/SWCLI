"""Command-line entry point for SWCLI."""

from __future__ import annotations

import argparse
import json
import os
import sys
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

    def add_document_selector(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument(
            "--document",
            dest="document_id",
            help="target a d-... document ID, or 'active' for this command only",
        )

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

    typed = _typed_operation(args)
    if typed is not None:
        operation, parameters, as_json, document_id = typed
        try:
            response = call_daemon(
                operation,
                parameters,
                endpoint=args.endpoint,
                timeout_seconds=args.request_timeout,
                connect_timeout_seconds=args.connect_timeout,
                session_id=args.session,
                document_id=document_id,
            )
        except Exception as exc:
            response = _autostart_and_retry(
                args, operation, parameters, document_id, exc
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


def _typed_payload(operation: str, response: Dict[str, Any]) -> Dict[str, Any]:
    return response.get("result") or {
        "ok": False,
        "action": operation,
        "error": {
            "type": (response.get("error") or {}).get("code", "DaemonError"),
            "message": (response.get("error") or {}).get(
                "message", "daemon request failed"
            ),
        },
    }


def _autostart_and_retry(
    args: argparse.Namespace,
    operation: str,
    parameters: Dict[str, Any],
    document_id: Optional[str],
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
            session_id=args.session,
            document_id=document_id,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": {"code": type(exc).__name__, "message": str(exc)},
        }


def _typed_operation(
    args: argparse.Namespace,
) -> Optional[Tuple[str, Dict[str, Any], bool, Optional[str]]]:
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
            )
        if command == "list":
            return "document.list", {}, args.as_json, None
        if command == "use":
            return "document.use", {}, args.as_json, args.document_id
        if command == "inspect":
            return (
                "document.inspect",
                {"detail": args.detail, "max_features": args.max_features},
                args.as_json,
                args.document_id,
            )
        if command == "close":
            return (
                "document.close",
                {"discard": args.discard},
                args.as_json,
                args.document_id,
            )
        if command == "save":
            return "document.save", {}, args.as_json, args.document_id
        if command == "diagnose":
            return (
                "document.diagnose",
                {"max_features": args.max_features},
                args.as_json,
                args.document_id,
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
            )
    if args.command == "part" and args.part_command == "create-box":
        return (
            "part.create-box",
            {
                "output": args.output,
                "width_mm": args.width_mm,
                "height_mm": args.height_mm,
                "depth_mm": args.depth_mm,
                "template": args.template,
                "overwrite": args.overwrite,
            },
            args.as_json,
            None,
        )
    return None


def _configure_output() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


def _print_action_result(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    state = "ok" if payload["ok"] else "failed"
    print(f"SWCLI {payload['action']}: {state}")
    if payload.get("error"):
        print(f"{payload['error']['type']}: {payload['error']['message']}")
