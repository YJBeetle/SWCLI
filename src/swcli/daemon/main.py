"""Lifecycle commands for the resident SWCLI service."""

from __future__ import annotations

import argparse
import errno
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from .client import DEFAULT_ENDPOINT, call_daemon, parse_endpoint
from .server import SwclidServer, WorkerManager, WorkerStartupError


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Add daemon lifecycle commands to a parser."""

    commands = parser.add_subparsers(dest="daemon_command", required=True)

    serve = commands.add_parser("serve", help="run the local protocol service")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=18495)
    serve.add_argument("--visible", action="store_true")
    serve.add_argument(
        "--attach-existing",
        action="store_true",
        help="explicitly share an already running interactive SOLIDWORKS instance",
    )
    serve.add_argument("--startup-timeout", type=float, default=120.0)
    serve.add_argument(
        "--host-platform",
        choices=("windows", "macos-wine", "linux-wine"),
        default=os.environ.get("SWCLI_HOST_PLATFORM", "windows"),
    )

    start = commands.add_parser("start", help="start the service in the background")
    start.add_argument("--endpoint", dest="daemon_endpoint")
    start.add_argument("--visible", action="store_true")
    start.add_argument(
        "--attach-existing",
        action="store_true",
        help="explicitly share an already running interactive SOLIDWORKS instance",
    )
    start.add_argument("--startup-timeout", type=float, default=120.0)
    start.add_argument("--json", action="store_true", dest="as_json")

    status = commands.add_parser("status", help="query a running service")
    status.add_argument("--endpoint", dest="daemon_endpoint")
    status.add_argument("--json", action="store_true", dest="as_json")

    stop = commands.add_parser("stop", help="stop a running service")
    stop.add_argument("--endpoint", dest="daemon_endpoint")
    stop.add_argument("--json", action="store_true", dest="as_json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m swcli.daemon",
        description="Resident SOLIDWORKS COM service for SWCLI",
    )
    configure_parser(parser)
    return parser


def is_local_endpoint(endpoint: str) -> bool:
    try:
        host, _ = parse_endpoint(endpoint)
    except (TypeError, ValueError):
        return False
    return host.casefold() in {"127.0.0.1", "localhost"}


def is_local_daemon_unreachable_error(exc: BaseException) -> bool:
    """Return whether a local health probe failed before reaching swclid.

    Some Windows networking stacks, including Windows on Parallels, time out
    loopback connects to an unused port instead of returning WSAECONNREFUSED.
    Both outcomes mean automatic startup should be attempted for an explicitly
    local endpoint.
    """

    return isinstance(exc, (ConnectionRefusedError, TimeoutError)) or (
        isinstance(exc, OSError)
        and (
            getattr(exc, "errno", None) == errno.ECONNREFUSED
            or getattr(exc, "winerror", None) == 10061
        )
    )


def _failure(code: str, message: str, **details: Any) -> Dict[str, Any]:
    error: Dict[str, Any] = {"code": code, "message": message}
    error.update(details)
    return {"success": False, "error": error}


def _read_startup_failure(
    log_path: Path, *, start_offset: int = 0
) -> Optional[Dict[str, str]]:
    """Read the current launch's last structured failure from the daemon log."""

    try:
        with log_path.open("rb") as log:
            log.seek(start_offset)
            lines = log.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            payload = json.loads(line)
        except (TypeError, ValueError):
            continue
        if payload.get("action") != "daemon.serve" or payload.get("ok") is not False:
            continue
        error = payload.get("error") or {}
        if isinstance(error.get("code"), str) and isinstance(
            error.get("message"), str
        ):
            return {"code": error["code"], "message": error["message"]}
    return None


def start_daemon(
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    visible: bool = False,
    startup_timeout_seconds: float = 120.0,
    attach_existing: bool = False,
) -> Dict[str, Any]:
    """Idempotently start a detached local daemon and wait for readiness."""

    if sys.platform != "win32":
        return _failure(
            "UnsupportedPlatform",
            "automatic daemon startup requires native Windows or Windows Python under Wine",
        )
    if not is_local_endpoint(endpoint):
        return _failure(
            "NonLocalEndpoint",
            "automatic daemon startup is limited to localhost endpoints",
        )
    if startup_timeout_seconds <= 0:
        return _failure("InvalidTimeout", "startup timeout must be positive")

    try:
        response = call_daemon(
            "daemon.health", endpoint=endpoint, timeout_seconds=1.0
        )
    except Exception as exc:
        if not is_local_daemon_unreachable_error(exc):
            return _failure(type(exc).__name__, str(exc))
    else:
        if response.get("success"):
            return {
                "success": True,
                "result": {
                    "started": False,
                    "already_running": True,
                    "endpoint": endpoint,
                    "health": response.get("result"),
                },
            }
        error = response.get("error") or {}
        return _failure(
            error.get("code", "DaemonError"),
            error.get("message", "daemon health check failed"),
        )

    host, port = parse_endpoint(endpoint)
    log_root = Path(
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("TEMP")
        or tempfile.gettempdir()
    )
    log_path = log_root / "SWCLI" / "logs" / "daemon.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "swcli",
        "daemon",
        "serve",
        "--host",
        host,
        "--port",
        str(port),
        "--startup-timeout",
        str(startup_timeout_seconds),
    ]
    if visible:
        command.append("--visible")
    if attach_existing:
        command.append("--attach-existing")

    creationflags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
    )
    try:
        with log_path.open("ab") as log:
            log_offset = log.tell()
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                close_fds=True,
                creationflags=creationflags,
            )
    except Exception as exc:
        return _failure(type(exc).__name__, str(exc), log=str(log_path))

    deadline = time.monotonic() + startup_timeout_seconds + 5.0
    last_error: Optional[BaseException] = None
    while time.monotonic() < deadline:
        try:
            response = call_daemon(
                "daemon.health", endpoint=endpoint, timeout_seconds=1.0
            )
            if response.get("success"):
                return {
                    "success": True,
                    "result": {
                        "started": True,
                        "already_running": False,
                        "endpoint": endpoint,
                        "log": str(log_path),
                        "health": response.get("result"),
                    },
                }
        except Exception as exc:
            last_error = exc
        if process.poll() is not None:
            startup_error = _read_startup_failure(
                log_path, start_offset=log_offset
            )
            if startup_error is not None:
                return _failure(
                    startup_error["code"],
                    startup_error["message"],
                    log=str(log_path),
                )
            return _failure(
                "DaemonExited",
                f"daemon exited during startup with code {process.returncode}",
                log=str(log_path),
            )
        time.sleep(0.25)

    message = f"daemon did not become ready within {startup_timeout_seconds:g}s"
    if last_error is not None:
        message = f"{message}: {last_error}"
    return _failure("StartupTimeout", message, log=str(log_path))


def run(args: argparse.Namespace) -> int:
    command = args.daemon_command
    if command == "serve":
        if not 1 <= args.port <= 65535:
            raise SystemExit("sw-cli daemon serve: port must be between 1 and 65535")
        server = SwclidServer((args.host, args.port))
        manager = None
        exit_code = 0
        try:
            manager = WorkerManager(
                visible=args.visible,
                startup_timeout_seconds=args.startup_timeout,
                host_platform=args.host_platform,
                attach_existing=args.attach_existing,
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
        except WorkerStartupError as exc:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "action": "daemon.serve",
                        "error": {"code": exc.code, "message": str(exc)},
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                flush=True,
            )
            exit_code = 1
        finally:
            server.server_close()
            if manager is not None:
                manager.close()
        return exit_code

    endpoint = (
        getattr(args, "daemon_endpoint", None)
        or getattr(args, "endpoint", None)
        or os.environ.get("SWCLI_ENDPOINT", DEFAULT_ENDPOINT)
    )
    if command == "start":
        response = start_daemon(
            endpoint=endpoint,
            visible=args.visible,
            startup_timeout_seconds=args.startup_timeout,
            attach_existing=args.attach_existing,
        )
    else:
        operation = "daemon.health" if command == "status" else "daemon.shutdown"
        try:
            response = call_daemon(
                operation,
                endpoint=endpoint,
                timeout_seconds=10.0,
                connect_timeout_seconds=1.0,
            )
        except Exception as exc:
            response = _failure(type(exc).__name__, str(exc))

    if args.as_json:
        print(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True))
    elif response.get("success"):
        print(f"sw-cli daemon {command}: ok")
    else:
        error = response.get("error") or {}
        print(
            f"sw-cli daemon {command}: {error.get('code', 'failed')}: "
            f"{error.get('message', 'unknown error')}",
            file=sys.stderr,
        )
    return 0 if response.get("success") else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    return run(build_parser().parse_args(argv))
