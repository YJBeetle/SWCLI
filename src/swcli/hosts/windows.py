"""Read-only discovery for native Windows SOLIDWORKS hosts."""

from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PROG_ID = "SldWorks.Application"
_VERSION_KEY = re.compile(r"^SOLIDWORKS\s+(\d{4})$", re.IGNORECASE)


def _error(exc: BaseException) -> Dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def _command_executable(command: str) -> Optional[str]:
    """Extract an executable path from a LocalServer32 command string."""

    command = command.strip()
    if not command:
        return None
    if command.startswith('"'):
        end = command.find('"', 1)
        return command[1:end] if end > 1 else command.strip('"')
    match = re.match(r"(.+?\.exe)(?:\s|$)", command, re.IGNORECASE)
    return match.group(1) if match else command


def _registry_views(winreg: Any) -> Iterable[Tuple[str, int]]:
    yield "64-bit", getattr(winreg, "KEY_WOW64_64KEY", 0)
    wow32 = getattr(winreg, "KEY_WOW64_32KEY", 0)
    if wow32:
        yield "32-bit", wow32


def _read_value(winreg: Any, root: Any, path: str, view: int = 0) -> Any:
    access = winreg.KEY_READ | view
    with winreg.OpenKey(root, path, 0, access) as key:
        return winreg.QueryValueEx(key, None)[0]


def _subkeys(winreg: Any, root: Any, path: str, view: int = 0) -> List[str]:
    access = winreg.KEY_READ | view
    names: List[str] = []
    with winreg.OpenKey(root, path, 0, access) as key:
        index = 0
        while True:
            try:
                names.append(winreg.EnumKey(key, index))
            except OSError:
                break
            index += 1
    return names


def _discover_com_registration(winreg: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "prog_id": PROG_ID,
        "current_version": None,
        "clsid": None,
        "local_server": None,
        "local_server_exists": None,
        "registry_view": None,
    }
    errors: List[Dict[str, str]] = []

    for view_name, view in _registry_views(winreg):
        try:
            clsid = _read_value(
                winreg, winreg.HKEY_CLASSES_ROOT, f"{PROG_ID}\\CLSID", view
            )
            command = _read_value(
                winreg,
                winreg.HKEY_CLASSES_ROOT,
                f"CLSID\\{clsid}\\LocalServer32",
                view,
            )
        except OSError as exc:
            errors.append({"registry_view": view_name, **_error(exc)})
            continue

        try:
            current_version = _read_value(
                winreg, winreg.HKEY_CLASSES_ROOT, f"{PROG_ID}\\CurVer", view
            )
        except OSError:
            try:
                current_version = _read_value(
                    winreg,
                    winreg.HKEY_CLASSES_ROOT,
                    f"CLSID\\{clsid}\\ProgID",
                    view,
                )
            except OSError:
                current_version = None

        executable = _command_executable(os.path.expandvars(str(command)))
        result.update(
            {
                "current_version": str(current_version),
                "clsid": str(clsid),
                "local_server": executable,
                "local_server_exists": (
                    Path(executable).is_file() if executable is not None else False
                ),
                "registry_view": view_name,
            }
        )
        break

    if errors and result["clsid"] is None:
        result["errors"] = errors
    return result


def _discover_installations(winreg: Any) -> List[Dict[str, Any]]:
    installations: List[Dict[str, Any]] = []
    seen = set()
    roots = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\SolidWorks"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\SolidWorks"),
    )
    value_names = ("SolidWorks Folder", "InstallDir")

    for root, base_path in roots:
        for view_name, view in _registry_views(winreg):
            try:
                names = _subkeys(winreg, root, base_path, view)
            except OSError:
                continue
            for name in names:
                match = _VERSION_KEY.match(name)
                if match is None:
                    continue
                setup_path = f"{base_path}\\{name}\\Setup"
                install_path = None
                for value_name in value_names:
                    try:
                        access = winreg.KEY_READ | view
                        with winreg.OpenKey(root, setup_path, 0, access) as key:
                            install_path = winreg.QueryValueEx(key, value_name)[0]
                        break
                    except OSError:
                        continue
                identity = name.casefold()
                if identity in seen:
                    continue
                seen.add(identity)
                installations.append(
                    {
                        "name": name,
                        "year": int(match.group(1)),
                        "install_dir": str(install_path) if install_path else None,
                        "install_dir_exists": (
                            Path(str(install_path)).is_dir() if install_path else None
                        ),
                        "registry_view": view_name,
                    }
                )

    installations.sort(key=lambda item: item["year"], reverse=True)
    return installations


def _com_value(obj: Any, name: str) -> Any:
    """Read a COM member exposed by pywin32 as either a property or method."""

    value = getattr(obj, name)
    if hasattr(value, "_oleobj_"):
        return value
    return value() if callable(value) else value


def _describe_com_app(app: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "attached": True,
        "revision": str(_com_value(app, "RevisionNumber")),
        "process_id": int(_com_value(app, "GetProcessID")),
        "visible": bool(_com_value(app, "Visible")),
        "active_document": None,
    }
    document = _com_value(app, "ActiveDoc")
    if document is not None:
        result["active_document"] = {
            "title": str(_com_value(document, "GetTitle")),
            "path": str(_com_value(document, "GetPathName")),
            "type": int(_com_value(document, "GetType")),
        }
    return result


def _probe_active_com() -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "pywin32_available": False,
        "attached": False,
        "revision": None,
        "process_id": None,
        "visible": None,
        "active_document": None,
    }
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        result["error"] = _error(exc)
        return result

    result["pywin32_available"] = True
    pythoncom.CoInitialize()
    try:
        app = win32com.client.GetActiveObject(PROG_ID)
        result.update(_describe_com_app(app))
    except Exception as exc:
        result["error"] = _error(exc)
    finally:
        pythoncom.CoUninitialize()
    return result


def probe_windows_host() -> Dict[str, Any]:
    """Inspect Windows, SOLIDWORKS registration, and the running COM server."""

    result: Dict[str, Any] = {
        "host": {
            "platform": sys.platform,
            "os_version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "python_architecture": platform.architecture()[0],
        },
        "supported": sys.platform == "win32",
        "registration": None,
        "installations": [],
        "com": None,
    }
    if not result["supported"]:
        result["error"] = {
            "type": "UnsupportedPlatform",
            "message": "native Windows host probing requires Windows",
        }
        return result

    try:
        import winreg
    except ImportError as exc:
        result["error"] = _error(exc)
        return result

    result["registration"] = _discover_com_registration(winreg)
    result["installations"] = _discover_installations(winreg)
    result["com"] = _probe_active_com()
    return result


def _unsupported_lifecycle(action: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "action": action,
        "error": {
            "type": "UnsupportedPlatform",
            "message": "native Windows lifecycle operations require Windows",
        },
    }


def start_windows_host(
    *, visible: bool = True, timeout_seconds: float = 60.0
) -> Dict[str, Any]:
    """Start SOLIDWORKS from its COM registration, or reuse the active instance."""

    if sys.platform != "win32":
        return _unsupported_lifecycle("start")

    import pythoncom
    import win32com.client
    import winreg

    registration = _discover_com_registration(winreg)
    executable = registration.get("local_server")
    if not executable or not registration.get("local_server_exists"):
        return {
            "ok": False,
            "action": "start",
            "registration": registration,
            "error": {
                "type": "InstallationNotFound",
                "message": "registered SOLIDWORKS LocalServer32 was not found",
            },
        }

    result: Dict[str, Any] = {
        "ok": False,
        "action": "start",
        "started": False,
        "registration": registration,
    }
    pythoncom.CoInitialize()
    try:
        try:
            app = win32com.client.GetActiveObject(PROG_ID)
        except Exception:
            process = subprocess.Popen([executable])
            result["launcher_process_id"] = process.pid
            deadline = time.monotonic() + timeout_seconds
            app = None
            last_error: Optional[BaseException] = None
            while time.monotonic() < deadline:
                try:
                    app = win32com.client.GetActiveObject(PROG_ID)
                    break
                except Exception as exc:
                    last_error = exc
                    time.sleep(0.25)
            if app is None:
                result["error"] = {
                    "type": "StartupTimeout",
                    "message": f"SOLIDWORKS COM server was not ready after {timeout_seconds:g}s",
                }
                if last_error is not None:
                    result["error"]["cause"] = _error(last_error)
                return result
            result["started"] = True

        app.Visible = visible
        if visible:
            app.UserControl = True
        result["com"] = _describe_com_app(app)
        result["ok"] = True
        return result
    except Exception as exc:
        result["error"] = _error(exc)
        return result
    finally:
        pythoncom.CoUninitialize()


def stop_windows_host(
    *, force: bool = False, timeout_seconds: float = 30.0
) -> Dict[str, Any]:
    """Stop the active SOLIDWORKS instance, protecting open documents by default."""

    if sys.platform != "win32":
        return _unsupported_lifecycle("stop")

    import pythoncom
    import win32com.client

    result: Dict[str, Any] = {
        "ok": False,
        "action": "stop",
        "forced": force,
        "stopped": False,
    }
    pythoncom.CoInitialize()
    try:
        try:
            app = win32com.client.GetActiveObject(PROG_ID)
        except Exception:
            result.update({"ok": True, "stopped": True, "already_stopped": True})
            return result

        snapshot = _describe_com_app(app)
        result["previous_com"] = snapshot
        if snapshot["active_document"] is not None and not force:
            result["error"] = {
                "type": "OpenDocument",
                "message": "refusing to stop SOLIDWORKS while a document is open; close it or use --force",
            }
            return result

        if force:
            completed = subprocess.run(
                ["taskkill", "/PID", str(snapshot["process_id"]), "/T", "/F"],
                capture_output=True,
                text=True,
                errors="replace",
                check=False,
            )
            if completed.returncode != 0:
                result["error"] = {
                    "type": "ProcessTerminationFailed",
                    "message": completed.stderr.strip() or completed.stdout.strip(),
                }
                return result
        else:
            _com_value(app, "ExitApp")

        app = None
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                win32com.client.GetActiveObject(PROG_ID)
            except Exception:
                result.update({"ok": True, "stopped": True})
                return result
            time.sleep(0.25)

        result["error"] = {
            "type": "ShutdownTimeout",
            "message": f"SOLIDWORKS COM server remained active after {timeout_seconds:g}s",
        }
        return result
    except Exception as exc:
        result["error"] = _error(exc)
        return result
    finally:
        pythoncom.CoUninitialize()
