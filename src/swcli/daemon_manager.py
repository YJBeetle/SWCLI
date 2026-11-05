"""Client-side daemon manager shared by MCP, CLI and host integrations.

The host launcher is an executable path supplied by trusted process configuration,
not an MCP tool argument. It owns Wine/prefix/Python selection. Never use the
POSIX client's interpreter to guess a Windows daemon runtime.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from jsonschema import Draft202012Validator

from .daemon.client import DEFAULT_ENDPOINT, call_daemon, parse_endpoint
from .daemon.timeouts import validate_timeout
from .protocol import load_schema
from .runtime_state import native_inventory, snapshot

LAUNCHER_ENV = "SWCLI_HOST_LAUNCHER"
DELEGATED_ENV = "SWCLI_HOST_LAUNCHER_ACTIVE"


def failure(code, message, **extra):
    return {"success": False, "error": {"code": code, "message": message}, **extra}


class DaemonManager:
    def __init__(self, *, endpoint=None, host_launcher=None, connect_timeout_seconds=3):
        self.endpoint = endpoint or os.environ.get("SWCLI_ENDPOINT", DEFAULT_ENDPOINT)
        parse_endpoint(self.endpoint)
        self.host_launcher = host_launcher if host_launcher is not None else os.environ.get(LAUNCHER_ENV)
        self.connect_timeout = validate_timeout(connect_timeout_seconds, name="connection timeout")
        self.validator = Draft202012Validator(load_schema("response"))

    def _call(self, operation, *, timeout=10, request_id=None):
        response = call_daemon(operation, {}, endpoint=self.endpoint,
                               timeout_seconds=timeout, connect_timeout_seconds=self.connect_timeout,
                               request_id=request_id or str(uuid.uuid4()))
        self.validator.validate(response)
        return response

    def status(self):
        from .daemon.main import is_local_endpoint
        try:
            response = self._call("daemon.runtime-status")
            if response.get("success"):
                from .runtime_state import result_schema
                Draft202012Validator(result_schema()).validate(response["result"])
                return response
            error = response.get("error") or {}
            if "unsupported operation: daemon.runtime-status" not in error.get("message", ""):
                return {"success": True, "result": snapshot(daemon_running=True, error=error)}
            # Compatibility is read-only: older daemons still have health, but
            # current remote window/process observations must remain unknown.
            health_response = self._call("daemon.health")
            if health_response.get("success"):
                return {"success": True, "result": snapshot(health_response["result"], error={
                    "code": "RuntimeObservationUnavailable", "message": "Older daemon supplies startup visibility only; current process inventory is unknown",
                })}
            return {"success": True, "result": snapshot(daemon_running=True, error=health_response.get("error"))}
        except Exception as exc:
            # Refusal establishes no listener at this endpoint. A timeout or
            # unreadable peer must not be reported as a definitely stopped daemon.
            stopped = isinstance(exc, ConnectionRefusedError) and getattr(exc, "_swcli_transport_phase", None) == "connect"
            inventory = native_inventory() if is_local_endpoint(self.endpoint) else None
            return {"success": True, "result": snapshot(
                inventory=inventory, daemon_running=False if stopped else None,
                reachable=False, scope="client-host", error={"code": type(exc).__name__, "message": str(exc)},
            )}

    def start(self, *, visible=False, attach_existing=False, startup_timeout_seconds=120):
        from .daemon.main import is_local_daemon_unreachable_error, is_local_endpoint, start_daemon
        startup_timeout_seconds = validate_timeout(startup_timeout_seconds, name="startup timeout", margin=30)
        try:
            health = self._call("daemon.health")
        except OSError as exc:
            if (getattr(exc, "_swcli_transport_phase", None) != "connect"
                    or not is_local_daemon_unreachable_error(exc)):
                raise
        else:
            if health.get("success"):
                state = health.get("result") or {}
                if not state.get("host_connected") or not state.get("worker_alive"):
                    return failure("HostNotReady", "Existing daemon needs explicit recovery; it was not restarted", health=state)
                return {"success": True, "result": {"started": False, "already_running": True,
                        "endpoint": self.endpoint, "health": state}}
            return health
        if not is_local_endpoint(self.endpoint):
            return failure("NonLocalEndpoint", "Start the remote daemon on its host; this manager only launches local hosts")
        delegated = os.environ.get(DELEGATED_ENV) == "1"
        if self.host_launcher and not delegated:
            result = self._start_external(visible, attach_existing, startup_timeout_seconds)
            if result.get("success"):
                ready = self._call("daemon.health")
                state = ready.get("result") or {}
                if not ready.get("success") or not state.get("host_connected") or not state.get("worker_alive"):
                    return failure("HostLauncherNotReady", "Host launcher returned without a ready daemon/SW; inspect status before another start", outcome_unknown=True)
            return result
        if sys.platform != "win32":
            return failure("HostLauncherRequired", "Configure SWCLI_HOST_LAUNCHER with the host's absolute sw-cli wrapper; the client Python is not the daemon runtime")
        if delegated:
            return start_daemon(endpoint=self.endpoint, startup_timeout_seconds=startup_timeout_seconds,
                                visible=visible, attach_existing=attach_existing)
        from .windows_client_startup import in_client_job, start_resident_daemon
        if in_client_job():
            return start_resident_daemon(endpoint=self.endpoint, startup_timeout_seconds=startup_timeout_seconds,
                                         visible=visible, attach_existing=attach_existing)
        return start_daemon(endpoint=self.endpoint, startup_timeout_seconds=startup_timeout_seconds,
                            visible=visible, attach_existing=attach_existing)

    def _start_external(self, visible, attach_existing, timeout):
        launcher = Path(self.host_launcher)
        if not launcher.is_absolute() or not launcher.is_file():
            return failure("InvalidHostLauncher", "SWCLI_HOST_LAUNCHER must identify an existing absolute executable path")
        if sys.platform != "win32" and not os.access(launcher, os.X_OK):
            return failure("InvalidHostLauncher", "Host launcher is not executable")
        if sys.platform == "win32":
            from .windows_client_startup import in_client_job
            if in_client_job():
                return failure("HostLauncherIsolationRequired", "This Windows client is inside a kill job; use its native manager or an independently managed host service")
        arguments = [str(launcher), "daemon", "start", "--endpoint", self.endpoint,
                     "--startup-timeout", str(timeout), "--json"]
        if visible:
            arguments.append("--visible")
        if attach_existing:
            arguments.append("--attach-existing")
        environment = dict(os.environ, **{DELEGATED_ENV: "1"})
        try:
            completed = subprocess.run(arguments, stdin=subprocess.DEVNULL, capture_output=True,
                                       timeout=timeout + 30, env=environment, start_new_session=sys.platform != "win32")
        except subprocess.TimeoutExpired:
            return failure("HostLauncherTimeout", "Host launcher did not return before its startup budget; inspect status before another start", outcome_unknown=True)
        try:
            payload = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeError, ValueError):
            return failure("InvalidHostLauncherResponse", "Host launcher did not return UTF-8 lifecycle JSON; inspect status before another start", outcome_unknown=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("success"), bool):
            return failure("InvalidHostLauncherResponse", "Host launcher did not return a lifecycle JSON response", outcome_unknown=True)
        if completed.returncode and payload["success"]:
            return failure("InvalidHostLauncherResponse", "Host launcher exit status disagrees with its JSON response", outcome_unknown=True)
        return payload

    def stop(self, *, request_id=None, timeout_seconds=600):
        try:
            # The existing worker refuses shutdown with an open owned document,
            # and detaches from shared user hosts without closing them.
            return self._call("daemon.shutdown", timeout=timeout_seconds, request_id=request_id)
        except ConnectionRefusedError as exc:
            if getattr(exc, "_swcli_transport_phase", None) != "connect":
                raise
            return {"success": True, "result": {"stopping": False, "already_stopped": True}}
