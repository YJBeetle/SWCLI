"""Command-line entry point for SWCLI."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from . import PROTOCOL_VERSION, __version__
from .hosts import (
    close_active_windows_document,
    inspect_active_windows_document,
    open_windows_document,
    probe_windows_host,
    start_windows_host,
    stop_windows_host,
)
from .protocol import SCHEMA_NAMES, load_schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sw-cli",
        description="Cross-platform SOLIDWORKS automation client",
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

    if args.command == "document" and args.document_command == "open":
        payload = open_windows_document(
            args.path,
            read_only=args.read_only,
            configuration=args.configuration,
        )
        _print_action_result(payload, args.as_json)
        return 0 if payload["ok"] else 1

    if args.command == "document" and args.document_command == "inspect":
        payload = inspect_active_windows_document()
        _print_action_result(payload, args.as_json)
        return 0 if payload["ok"] else 1

    if args.command == "document" and args.document_command == "close":
        payload = close_active_windows_document(discard=args.discard)
        _print_action_result(payload, args.as_json)
        return 0 if payload["ok"] else 1

    return 2


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
