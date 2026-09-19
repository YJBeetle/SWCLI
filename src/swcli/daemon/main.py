"""Command-line entry point for swclid."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional, Sequence

from .client import DEFAULT_ENDPOINT, call_daemon
from .server import SwclidServer, WorkerManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="swclid", description="Resident SOLIDWORKS COM service for SWCLI"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="start the local protocol service")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=18495)
    serve.add_argument("--visible", action="store_true")
    serve.add_argument("--startup-timeout", type=float, default=120.0)
    serve.add_argument(
        "--host-platform",
        choices=("windows", "macos-wine", "linux-wine"),
        default=os.environ.get("SWCLI_HOST_PLATFORM", "windows"),
    )

    status = commands.add_parser("status", help="query a running service")
    status.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    status.add_argument("--json", action="store_true", dest="as_json")

    stop = commands.add_parser("stop", help="stop a running service")
    stop.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    stop.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        if not 1 <= args.port <= 65535:
            raise SystemExit("swclid: port must be between 1 and 65535")
        server = SwclidServer((args.host, args.port))
        manager = None
        try:
            manager = WorkerManager(
                visible=args.visible,
                startup_timeout_seconds=args.startup_timeout,
                host_platform=args.host_platform,
            )
            server.manager = manager
            print(
                json.dumps(
                    {
                        "ok": True,
                        "action": "daemon.serve",
                        "endpoint": f"{args.host}:{args.port}",
                        "host": manager.host,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                flush=True,
            )
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            if manager is not None:
                manager.close()
        return 0

    operation = "daemon.health" if args.command == "status" else "daemon.shutdown"
    try:
        response = call_daemon(
            operation, endpoint=args.endpoint, timeout_seconds=10.0
        )
    except Exception as exc:
        response = {
            "success": False,
            "error": {"code": type(exc).__name__, "message": str(exc)},
        }
    if args.as_json:
        print(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True))
    elif response.get("success"):
        print(f"swclid {args.command}: ok")
    else:
        error = response.get("error") or {}
        print(
            f"swclid {args.command}: {error.get('code', 'failed')}: "
            f"{error.get('message', 'unknown error')}",
            file=sys.stderr,
        )
    return 0 if response.get("success") else 1
