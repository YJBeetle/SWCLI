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
    probe_windows_host,
    start_windows_host,
    stop_windows_host,
)
from .protocol import SCHEMA_NAMES, load_schema
from .daemon.client import DEFAULT_ENDPOINT, call_daemon


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sw-cli",
        description="Cross-platform SOLIDWORKS automation client",
    )
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("SWCLI_ENDPOINT", DEFAULT_ENDPOINT),
        help="swclid HOST:PORT endpoint for all typed operations",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=600.0,
        help="daemon request timeout in seconds",
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

    host_parser = subcommands.add_parser("host", help="inspect the automation host")
    host_commands = host_parser.add_subparsers(dest="host_command", required=True)
    probe_parser = host_commands.add_parser(
        "probe", help="probe Windows and the active SOLIDWORKS COM server"
    )
    probe_parser.add_argument("--json", action="store_true", dest="as_json")
    start_parser = host_commands.add_parser(
        "start", help="start SOLIDWORKS or reuse the active instance"
    )
    start_parser.add_argument("--hidden", action="store_true")
    start_parser.add_argument("--timeout", type=float, default=60.0)
    start_parser.add_argument("--json", action="store_true", dest="as_json")
    stop_parser = host_commands.add_parser("stop", help="stop the active SOLIDWORKS instance")
    stop_parser.add_argument(
        "--force",
        action="store_true",
        help="terminate the process tree even when a document is open",
    )
    stop_parser.add_argument("--timeout", type=float, default=30.0)
    stop_parser.add_argument("--json", action="store_true", dest="as_json")

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
    inspect_parser = document_commands.add_parser(
        "inspect", help="inspect the active SOLIDWORKS document"
    )
    inspect_parser.add_argument(
        "--detail", choices=("summary", "structure"), default="summary"
    )
    inspect_parser.add_argument("--max-features", type=int, default=500)
    inspect_parser.add_argument("--json", action="store_true", dest="as_json")
    close_parser = document_commands.add_parser(
        "close", help="close the active SOLIDWORKS document"
    )
    close_parser.add_argument(
        "--discard",
        action="store_true",
        help="discard modifications instead of refusing to close",
    )
    close_parser.add_argument("--json", action="store_true", dest="as_json")
    diagnose_parser = document_commands.add_parser(
        "diagnose", help="report rebuild state and feature errors"
    )
    diagnose_parser.add_argument("--max-features", type=int, default=500)
    diagnose_parser.add_argument("--json", action="store_true", dest="as_json")
    rebuild_parser = document_commands.add_parser(
        "rebuild", help="rebuild the active SOLIDWORKS document"
    )
    rebuild_parser.add_argument("--force", action="store_true")
    rebuild_parser.add_argument(
        "--top-only",
        action="store_true",
        help="with --force, rebuild only top-level assembly features",
    )
    rebuild_parser.add_argument("--max-features", type=int, default=500)
    rebuild_parser.add_argument("--json", action="store_true", dest="as_json")
    render_parser = document_commands.add_parser(
        "render", help="render the active view to a BMP image"
    )
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
        "export", help="export the active document to STEP, PDF, or DWG"
    )
    export_parser.add_argument("output")
    export_parser.add_argument("--overwrite", action="store_true")
    export_parser.add_argument(
        "--allow-source-dirty",
        action="store_true",
        help="accept an export that only changes the source document's dirty flag",
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

    typed = _typed_operation(args)
    if typed is not None:
        operation, parameters, as_json = typed
        try:
            response = call_daemon(
                operation,
                parameters,
                endpoint=args.endpoint,
                timeout_seconds=args.request_timeout,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "action": operation,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        else:
            payload = response.get("result") or {
                "ok": False,
                "action": operation,
                "error": {
                    "type": (response.get("error") or {}).get(
                        "code", "DaemonError"
                    ),
                    "message": (response.get("error") or {}).get(
                        "message", "swclid request failed"
                    ),
                },
            }
        _print_action_result(payload, as_json)
        return 0 if payload.get("ok") else 1

    if args.command == "host" and args.host_command == "probe":
        payload = probe_windows_host()
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            registration = payload.get("registration") or {}
            com = payload.get("com") or {}
            print(f"Platform: {payload['host']['platform']} ({payload['host']['machine']})")
            print(f"Supported: {'yes' if payload['supported'] else 'no'}")
            print(f"SOLIDWORKS registration: {registration.get('current_version') or 'not found'}")
            print(f"SOLIDWORKS executable: {registration.get('local_server') or 'not found'}")
            print(f"Active COM server: {'attached' if com.get('attached') else 'not attached'}")
            if com.get("revision"):
                print(f"SOLIDWORKS revision: {com['revision']}")
        return 0

    if args.command == "host" and args.host_command == "start":
        payload = start_windows_host(
            visible=not args.hidden, timeout_seconds=args.timeout
        )
        _print_action_result(payload, args.as_json)
        return 0 if payload["ok"] else 1

    if args.command == "host" and args.host_command == "stop":
        payload = stop_windows_host(
            force=args.force, timeout_seconds=args.timeout
        )
        _print_action_result(payload, args.as_json)
        return 0 if payload["ok"] else 1

    return 2


def _typed_operation(
    args: argparse.Namespace,
) -> Optional[Tuple[str, Dict[str, Any], bool]]:
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
            )
        if command == "inspect":
            return (
                "document.inspect",
                {"detail": args.detail, "max_features": args.max_features},
                args.as_json,
            )
        if command == "close":
            return "document.close", {"discard": args.discard}, args.as_json
        if command == "diagnose":
            return (
                "document.diagnose",
                {"max_features": args.max_features},
                args.as_json,
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
            )
        if command == "export":
            return (
                "document.export",
                {
                    "output": args.output,
                    "overwrite": args.overwrite,
                    "allow_source_dirty": args.allow_source_dirty,
                },
                args.as_json,
            )
    if args.command == "part" and args.part_command == "create-box":
        return (
            "part.create-box",
            {
                "output": args.output,
                "width_mm": args.width_mm,
                "height_mm": args.height_mm,
                "depth_mm": args.depth_mm,
                "overwrite": args.overwrite,
            },
            args.as_json,
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
