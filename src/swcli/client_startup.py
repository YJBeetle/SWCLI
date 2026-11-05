"""Explicit client-side lazy startup shared by CLI opt-in and MCP."""

import uuid

from .windows_client_startup import in_client_job, start_resident_daemon

from jsonschema import Draft202012Validator

from .daemon.client import call_daemon
from .protocol import load_schema


def ensure_local_daemon(*, endpoint, connect_timeout_seconds=3.0, startup_timeout_seconds=120.0):
    """Start only a locally unreachable daemon, never recover an existing host."""
    from .daemon.main import is_local_daemon_unreachable_error, is_local_endpoint, start_daemon
    if not is_local_endpoint(endpoint):
        return
    try:
        health = call_daemon(
            "daemon.health", {}, endpoint=endpoint, timeout_seconds=10,
            connect_timeout_seconds=connect_timeout_seconds,
            request_id=str(uuid.uuid4()),
        )
    except OSError as exc:
        if (getattr(exc, "_swcli_transport_phase", None) != "connect"
                or not is_local_daemon_unreachable_error(exc)):
            raise
        if in_client_job():
            started = start_resident_daemon(endpoint=endpoint, startup_timeout_seconds=startup_timeout_seconds)
        else:
            started = start_daemon(endpoint=endpoint, startup_timeout_seconds=startup_timeout_seconds)
        if not started.get("success"):
            error = started.get("error") or {}
            raise RuntimeError(f"{error.get('code', 'DaemonStartupFailed')}: {error.get('message', 'daemon startup failed')}")
    else:
        # A reachable unhealthy or incompatible service must never be replaced.
        Draft202012Validator(load_schema("response")).validate(health)
