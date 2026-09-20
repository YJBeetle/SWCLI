"""Read-only discovery for native Windows SOLIDWORKS hosts."""

from __future__ import annotations

import os
import platform
import re
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


def _describe_document(document: Any) -> Dict[str, Any]:
    return {
        "title": str(_com_value(document, "GetTitle")),
        "path": str(_com_value(document, "GetPathName")),
        "type": int(_com_value(document, "GetType")),
        "modified": bool(_com_value(document, "GetSaveFlag")),
    }


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
        result["active_document"] = _describe_document(document)
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


def doctor_windows_host() -> Dict[str, Any]:
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
            "message": "native Windows host diagnostics require Windows",
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


def wait_windows_host_ready(
    app: Any, *, timeout_seconds: float = 60.0, poll_interval_seconds: float = 0.25
) -> float:
    """Wait until SOLIDWORKS has loaded its startup add-ins and accepts API work."""

    started_at = time.monotonic()
    deadline = started_at + timeout_seconds
    while not bool(_com_value(app, "StartupProcessCompleted")):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"SOLIDWORKS startup did not complete within {timeout_seconds:g}s"
            )
        time.sleep(min(poll_interval_seconds, remaining))
    return time.monotonic() - started_at
