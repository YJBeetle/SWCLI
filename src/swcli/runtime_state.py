"""Read-only runtime observations, made in the execution host's PID namespace."""

import sys


def native_inventory():
    result = {"processes": None, "pid_namespace": "unavailable", "errors": []}
    if sys.platform != "win32":
        return result
    result["pid_namespace"] = "windows"
    try:
        from .host_processes import solidworks_process_ids
        pids = solidworks_process_ids()
    except Exception as exc:
        result["errors"].append({"code": type(exc).__name__, "message": str(exc)})
        return result
    visible = None
    try:
        import win32gui
        import win32process
        visible = set()
        def observe(window, _):
            pid = win32process.GetWindowThreadProcessId(window)[1]
            if pid in pids and win32gui.IsWindowVisible(window):
                visible.add(pid)
        win32gui.EnumWindows(observe, None)
    except Exception as exc:
        visible = None
        result["errors"].append({"code": type(exc).__name__, "message": str(exc)})
    result["processes"] = [
        {"process_id": pid, "visible": pid in visible if visible is not None else None}
        for pid in pids
    ]
    return result


def snapshot(health=None, *, inventory=None, daemon_running=True, reachable=True,
             scope="daemon-host", error=None):
    health = health or {}
    host = health.get("host") or {}
    inventory = inventory or {"processes": None, "pid_namespace": "unavailable", "errors": []}
    processes = inventory["processes"]
    pid = host.get("process_id")
    owned = host.get("owned_by_daemon")
    connected = health.get("host_connected")
    visible = host.get("visible")
    visibility_source = "startup-report" if visible is not None else "unavailable"
    current = False
    user_running = True if connected and owned is False else None
    other_running = None
    sw_running = True if connected else None
    if processes is not None:
        pids = {row["process_id"] for row in processes}
        sw_running = bool(pids)
        other_running = bool(pids - ({pid} if pid is not None else set()))
        if not pids:
            user_running = False
        elif owned is True and pids == {pid}:
            user_running = False
        for row in processes:
            if row["process_id"] == pid and row["visible"] is not None:
                visible = row["visible"]
                visibility_source = "top-level-windows"
                current = True
        if pid is not None and pid not in pids and scope == "daemon-host":
            connected = False
            user_running = None if pids else False
            visible = None
            visibility_source = "unavailable"
    state = "unknown"
    if daemon_running is False:
        state = "stopped"
    elif daemon_running is True:
        state = "ready" if connected else "degraded"
    if error and error.get("code") == "Starting":
        state = "starting"
    errors = list(inventory.get("errors", []))
    if error:
        errors.append(error)
    return {
        "daemon_running": daemon_running, "daemon_reachable": reachable,
        "daemon_state": state, "host_connected": connected,
        "sw_running": sw_running, "user_sw_running": user_running,
        "daemon_sw_pid": pid, "daemon_sw_owned": owned,
        "daemon_sw_visible": visible, "visibility_source": visibility_source,
        "visibility_current": current, "other_sw_running": other_running,
        "sw_processes": processes, "pid_namespace": inventory["pid_namespace"],
        "process_scope": scope if processes is not None else "unavailable",
        "health": health or None, "probe_errors": errors,
    }


def result_schema():
    nullable_bool = {"type": ["boolean", "null"]}
    fields = {
        name: nullable_bool for name in (
            "daemon_running", "host_connected", "sw_running", "user_sw_running",
            "daemon_sw_owned", "daemon_sw_visible", "other_sw_running",
        )
    }
    fields.update({
        "daemon_reachable": {"type": "boolean"},
        "daemon_state": {"enum": ["unknown", "stopped", "starting", "ready", "degraded"]},
        "daemon_sw_pid": {"type": ["integer", "null"], "minimum": 1},
        "visibility_source": {"enum": ["startup-report", "top-level-windows", "unavailable"]},
        "visibility_current": {"type": "boolean"},
        "other_sw_running": nullable_bool,
        "sw_processes": {"type": ["array", "null"], "items": {
            "type": "object", "additionalProperties": False,
            "required": ["process_id", "visible"],
            "properties": {"process_id": {"type": "integer", "minimum": 1}, "visible": nullable_bool},
        }},
        "pid_namespace": {"enum": ["windows", "unavailable"]},
        "process_scope": {"enum": ["daemon-host", "client-host", "unavailable"]},
        "health": {"type": ["object", "null"]},
        "probe_errors": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["code", "message"],
            "properties": {"code": {"type": "string"}, "message": {"type": "string"}},
        }},
    })
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://swcli.dev/schema/v1/results/daemon.runtime-status.schema.json",
            "type": "object",
            "properties": fields, "required": list(fields), "additionalProperties": False}
