"""SOLIDWORKS document operations for native Windows hosts."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .windows import PROG_ID, _com_value, _describe_document, _error


DOCUMENT_TYPES = {
    ".sldprt": 1,
    ".sldasm": 2,
    ".slddrw": 3,
}
_OPEN_SILENT = 1
_OPEN_READ_ONLY = 2


def _unsupported(action: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "action": action,
        "error": {
            "type": "UnsupportedPlatform",
            "message": "native Windows document operations require Windows",
        },
    }


def _document_type(path: Path) -> Optional[int]:
    return DOCUMENT_TYPES.get(path.suffix.casefold())


def open_windows_document(
    path: str, *, read_only: bool = False, configuration: str = ""
) -> Dict[str, Any]:
    """Open a native SOLIDWORKS document silently and report API status codes."""

    if sys.platform != "win32":
        return _unsupported("document.open")

    document_path = Path(path).expanduser().resolve()
    result: Dict[str, Any] = {
        "ok": False,
        "action": "document.open",
        "path": str(document_path),
        "read_only": read_only,
        "configuration": configuration or None,
    }
    if not document_path.is_file():
        result["error"] = {
            "type": "FileNotFound",
            "message": f"document does not exist: {document_path}",
        }
        return result

    document_type = _document_type(document_path)
    if document_type is None:
        result["error"] = {
            "type": "UnsupportedDocumentType",
            "message": f"unsupported SOLIDWORKS document extension: {document_path.suffix}",
        }
        return result

    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    try:
        try:
            app = win32com.client.GetActiveObject(PROG_ID)
        except Exception as exc:
            result["error"] = {
                "type": "HostNotRunning",
                "message": "SOLIDWORKS is not running; run 'sw-cli host start' first",
                "cause": _error(exc),
            }
            return result

        errors = win32com.client.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_I4, 0
        )
        warnings = win32com.client.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_I4, 0
        )
        options = _OPEN_SILENT | (_OPEN_READ_ONLY if read_only else 0)
        document = app.OpenDoc6(
            str(document_path),
            document_type,
            options,
            configuration,
            errors,
            warnings,
        )
        result["api_errors"] = int(errors.value)
        result["api_warnings"] = int(warnings.value)
        if document is None:
            result["error"] = {
                "type": "OpenFailed",
                "message": "SOLIDWORKS OpenDoc6 returned no document",
            }
            return result

        result["document"] = _describe_document(document)
        result["ok"] = True
        return result
    except Exception as exc:
        result["error"] = _error(exc)
        return result
    finally:
        pythoncom.CoUninitialize()


def inspect_active_windows_document() -> Dict[str, Any]:
    """Describe the active SOLIDWORKS document without modifying it."""

    if sys.platform != "win32":
        return _unsupported("document.inspect")

    import pythoncom
    import win32com.client

    result: Dict[str, Any] = {"ok": False, "action": "document.inspect"}
    pythoncom.CoInitialize()
    try:
        try:
            app = win32com.client.GetActiveObject(PROG_ID)
        except Exception as exc:
            result["error"] = {
                "type": "HostNotRunning",
                "message": "SOLIDWORKS is not running; run 'sw-cli host start' first",
                "cause": _error(exc),
            }
            return result

        document = _com_value(app, "ActiveDoc")
        if document is None:
            result["error"] = {
                "type": "NoActiveDocument",
                "message": "SOLIDWORKS has no active document",
            }
            return result

        result["document"] = _describe_document(document)
        result["ok"] = True
        return result
    except Exception as exc:
        result["error"] = _error(exc)
        return result
    finally:
        pythoncom.CoUninitialize()


def close_active_windows_document(*, discard: bool = False) -> Dict[str, Any]:
    """Close the active document, refusing to discard modifications by default."""

    if sys.platform != "win32":
        return _unsupported("document.close")

    import pythoncom
    import win32com.client

    result: Dict[str, Any] = {
        "ok": False,
        "action": "document.close",
        "discard": discard,
        "closed": False,
    }
    pythoncom.CoInitialize()
    try:
        try:
            app = win32com.client.GetActiveObject(PROG_ID)
        except Exception as exc:
            result["error"] = {
                "type": "HostNotRunning",
                "message": "SOLIDWORKS is not running; run 'sw-cli host start' first",
                "cause": _error(exc),
            }
            return result

        document = _com_value(app, "ActiveDoc")
        if document is None:
            result["error"] = {
                "type": "NoActiveDocument",
                "message": "SOLIDWORKS has no active document",
            }
            return result

        snapshot = _describe_document(document)
        result["document"] = snapshot
        if snapshot["modified"] and not discard:
            result["error"] = {
                "type": "ModifiedDocument",
                "message": "refusing to discard modifications; save the document or use --discard",
            }
            return result

        app.CloseDoc(snapshot["title"])
        result.update({"ok": True, "closed": True})
        return result
    except Exception as exc:
        result["error"] = _error(exc)
        return result
    finally:
        pythoncom.CoUninitialize()
