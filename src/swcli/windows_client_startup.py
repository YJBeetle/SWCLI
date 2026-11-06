"""Keep a requested resident daemon outside a Windows MCP client's kill job.

No CAD COM call occurs here. A unique, demand-only, non-elevated interactive
user task runs the existing foreground daemon. The task definition is removed
after startup; deleting it does not stop its running action. No boot/logon
trigger, password, service installation or client Job policy change is used.
"""

from pathlib import Path
import subprocess
import sys
import time
import uuid


def in_client_job():
    if sys.platform != "win32":
        return False
    import win32api
    import win32job
    return bool(win32job.IsProcessInJob(win32api.GetCurrentProcess(), None))


def register_start_task(service, *, name, user_sid, arguments, session_id):
    folder = service.GetFolder("\\")
    definition = service.NewTask(0)
    definition.RegistrationInfo.Description = "SWCLI demand-only resident daemon startup"
    definition.Principal.UserId = user_sid
    definition.Principal.LogonType = 3  # TASK_LOGON_INTERACTIVE_TOKEN
    definition.Principal.RunLevel = 0  # TASK_RUNLEVEL_LUA: no elevation
    settings = definition.Settings
    settings.Enabled = True
    settings.AllowDemandStart = True
    settings.StartWhenAvailable = False
    settings.DisallowStartIfOnBatteries = False
    settings.StopIfGoingOnBatteries = False
    settings.ExecutionTimeLimit = "PT0S"
    action = definition.Actions.Create(0)  # TASK_ACTION_EXEC
    action.Path = sys.executable
    action.Arguments = subprocess.list2cmdline(arguments)
    # TASK_CREATE, never replace an existing definition. There are no triggers.
    task = folder.RegisterTaskDefinition(name, definition, 2, user_sid, None, 3)
    try:
        running = task.RunEx("", 4, session_id, "")  # TASK_RUN_USE_SESSION_ID
    except BaseException:
        folder.DeleteTask(name, 0)
        raise
    return folder, running


def _task_not_running(error):
    # IDispatch may wrap SCHED_E_TASK_NOT_RUNNING in DISP_E_EXCEPTION.
    codes = [getattr(error, "hresult", None)]
    details = getattr(error, "excepinfo", None)
    if isinstance(details, tuple) and len(details) > 5:
        codes.append(details[5])
    return any(isinstance(code, int) and code & 0xffffffff == 0x8004130b for code in codes)


def _cleanup_start_task(folder, running, *, name, log, ready):
    from .daemon.main import _read_startup_host
    errors = []
    def record(stage, error):
        errors.append({"stage": stage, "code": type(error).__name__, "message": str(error)})
    if not ready and running is not None:
        try:
            if running.State in (2, 4):  # only queued/running instances can stop
                running.Stop()
        except Exception as exc:
            # The instance can finish between State and Stop. Other cleanup
            # failures are evidence, never replacements for the startup error.
            if not _task_not_running(exc):
                record("task.stop", exc)
        try:
            host = _read_startup_host(log, start_offset=0)
            if host and host.get("owned_by_daemon"):
                subprocess.run(["taskkill", "/PID", str(host["process_id"]), "/T", "/F"],
                               capture_output=True, timeout=10, check=False)
        except Exception as exc:
            record("host.cleanup", exc)
    if folder is not None:
        try:
            folder.DeleteTask(name, 0)
        except Exception as exc:
            record("task.delete", exc)
    return errors


def start_resident_daemon(*, endpoint, startup_timeout_seconds, visible=False, attach_existing=False, tray="auto"):
    import os
    import pythoncom
    import win32api
    import win32con
    import win32com.client
    import win32security
    from .daemon.client import call_daemon
    from .daemon.main import _failure, _read_startup_failure

    name = "SWCLI-demand-" + uuid.uuid4().hex
    log = Path(os.environ.get("LOCALAPPDATA") or os.environ["TEMP"]) / "SWCLI" / "logs" / (name + ".log")
    log.parent.mkdir(parents=True, exist_ok=True)
    arguments = [str(Path(__file__).with_name("client_bootstrap.py")), "--endpoint", endpoint,
                 "--startup-timeout", str(startup_timeout_seconds), "--log", str(log)]
    from .windows_tray import validate_mode
    validate_mode(tray)
    if tray != "auto":
        arguments.extend(("--tray", tray))
    if visible:
        arguments.append("--visible")
    if attach_existing:
        arguments.append("--attach-existing")
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        sid = win32security.ConvertSidToStringSid(win32security.GetTokenInformation(token, win32security.TokenUser)[0])
    finally:
        token.Close()
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL("kernel32", use_last_error=True).ProcessIdToSessionId
    api.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    api.restype = wintypes.BOOL
    session = wintypes.DWORD()
    if not api(os.getpid(), ctypes.byref(session)):
        raise ctypes.WinError(ctypes.get_last_error())
    session_id = session.value
    folder = running = None
    ready = False
    response = None
    pythoncom.CoInitialize()
    try:
        service = win32com.client.Dispatch("Schedule.Service")
        service.Connect()
        folder, running = register_start_task(service, name=name, user_sid=sid, arguments=arguments, session_id=session_id)
        deadline = time.monotonic() + startup_timeout_seconds + 15
        while time.monotonic() < deadline:
            try:
                health = call_daemon("daemon.health", {}, endpoint=endpoint, timeout_seconds=1, connect_timeout_seconds=0.25)
            except OSError:
                health = None
            if health and health.get("success"):
                ready = True
                response = {"success": True, "result": {"health": health.get("result"), "log": str(log)}}
                return response
            failure = _read_startup_failure(log, start_offset=0)
            if failure:
                response = _failure(failure["code"], failure["message"], log=str(log))
                return response
            if running.State not in (2, 4):  # queued/running
                response = _failure("DaemonExited", "daemon startup task exited before readiness", log=str(log))
                return response
            time.sleep(0.25)
        response = _failure("StartupTimeout", "daemon startup task did not become ready", log=str(log))
        return response
    except Exception as exc:
        response = _failure(type(exc).__name__, str(exc), log=str(log))
        return response
    finally:
        errors = _cleanup_start_task(folder, running, name=name, log=log, ready=ready)
        if errors and response is not None:
            response["cleanup_errors"] = errors
        folder = running = service = None
        pythoncom.CoUninitialize()
