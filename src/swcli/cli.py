"""Command-line entry point for SWCLI."""

from __future__ import annotations

import argparse
import json
from typing import Optional, Sequence

from . import PROTOCOL_VERSION, __version__
from .hosts import probe_windows_host
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

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
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

    return 2
