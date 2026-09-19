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
_ALL_BODIES = -1
_LENGTH_UNITS = {
    0: "millimeter",
    1: "centimeter",
    2: "meter",
    3: "inch",
    4: "foot",
    5: "foot-inch",
    6: "angstrom",
    7: "nanometer",
    8: "micron",
    9: "mil",
    10: "microinch",
}
_BODY_TYPES = {
    0: "solid",
    1: "sheet",
    2: "wire",
    3: "minimum",
    4: "general",
    5: "empty",
    6: "mesh",
    7: "graphics",
}


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


def _inspect_configurations(document: Any) -> Dict[str, Any]:
    names = list(_com_value(document, "GetConfigurationNames") or ())
    active = _com_value(document, "GetActiveConfiguration")
    return {
        "active": str(_com_value(active, "Name")) if active is not None else None,
        "names": [str(name) for name in names],
        "count": len(names),
    }


def _inspect_units(document: Any) -> Dict[str, Any]:
    values = list(_com_value(document, "GetUnits") or ())
    if len(values) < 5:
        return {"raw": values}
    length_unit = int(values[0])
    return {
        "length": {
            "code": length_unit,
            "name": _LENGTH_UNITS.get(length_unit, "unknown"),
        },
        "fraction_base": int(values[1]),
        "fraction_value": int(values[2]),
        "significant_digits": int(values[3]),
        "round_to_fraction": bool(values[4]),
    }


def _inspect_features(document: Any, max_features: int) -> Dict[str, Any]:
    features = []
    feature = _com_value(document, "FirstFeature")
    while feature is not None and len(features) < max_features:
        features.append(
            {
                "index": len(features),
                "name": str(_com_value(feature, "Name")),
                "type": str(_com_value(feature, "GetTypeName2")),
                "visibility": int(_com_value(feature, "Visible")),
            }
        )
        feature = _com_value(feature, "GetNextFeature")
    return {
        "order": "model-definition",
        "items": features,
        "count": len(features),
        "truncated": feature is not None,
        "limit": max_features,
    }


def _diagnose_features(document: Any, max_features: int) -> Dict[str, Any]:
    import pythoncom
    import win32com.client

    issues = []
    scanned = 0
    feature = _com_value(document, "FirstFeature")
    while feature is not None and scanned < max_features:
        warning = win32com.client.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_BOOL, False
        )
        code = int(feature.GetErrorCode2(warning))
        if code != 0:
            issues.append(
                {
                    "index": scanned,
                    "name": str(_com_value(feature, "Name")),
                    "type": str(_com_value(feature, "GetTypeName2")),
                    "code": code,
                    "severity": "warning" if bool(warning.value) else "error",
                }
            )
        scanned += 1
        feature = _com_value(feature, "GetNextFeature")
    return {
        "healthy": not issues,
        "issues": issues,
        "issue_count": len(issues),
        "scanned_feature_count": scanned,
        "truncated": feature is not None,
        "limit": max_features,
    }


def _inspect_bodies(document: Any) -> Dict[str, Any]:
    if int(_com_value(document, "GetType")) != 1:
        return {"applicable": False, "items": [], "count": 0}

    bodies = document.GetBodies2(_ALL_BODIES, False) or ()
    items = []
    for body in bodies:
        body_type = int(_com_value(body, "GetType"))
        items.append(
            {
                "name": str(_com_value(body, "Name")),
                "type": {
                    "code": body_type,
                    "name": _BODY_TYPES.get(body_type, "unknown"),
                },
                "visible": bool(_com_value(body, "Visible")),
                "face_count": int(_com_value(body, "GetFaceCount")),
                "edge_count": int(_com_value(body, "GetEdgeCount")),
            }
        )
    return {"applicable": True, "items": items, "count": len(items)}


def inspect_active_windows_document(
    *, detail: str = "summary", max_features: int = 500
) -> Dict[str, Any]:
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
        if detail == "structure":
            result["structure"] = {
                "configurations": _inspect_configurations(document),
                "units": _inspect_units(document),
                "features": _inspect_features(document, max_features),
                "bodies": _inspect_bodies(document),
            }
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


def diagnose_active_windows_document(*, max_features: int = 500) -> Dict[str, Any]:
    """Report rebuild state and per-feature errors without modifying the model."""

    if sys.platform != "win32":
        return _unsupported("document.diagnose")

    import pythoncom
    import win32com.client

    result: Dict[str, Any] = {"ok": False, "action": "document.diagnose"}
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

        extension = _com_value(document, "Extension")
        result["document"] = _describe_document(document)
        result["needs_rebuild"] = int(_com_value(extension, "NeedsRebuild2"))
        result["diagnostics"] = _diagnose_features(document, max_features)
        result["ok"] = True
        return result
    except Exception as exc:
        result["error"] = _error(exc)
        return result
    finally:
        pythoncom.CoUninitialize()


def rebuild_active_windows_document(
    *, force: bool = False, top_only: bool = False, max_features: int = 500
) -> Dict[str, Any]:
    """Rebuild the active configuration and return post-rebuild diagnostics."""

    if sys.platform != "win32":
        return _unsupported("document.rebuild")

    import pythoncom
    import win32com.client

    result: Dict[str, Any] = {
        "ok": False,
        "action": "document.rebuild",
        "force": force,
        "top_only": top_only,
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

        extension = _com_value(document, "Extension")
        result["needs_rebuild_before"] = int(
            _com_value(extension, "NeedsRebuild2")
        )
        if force:
            rebuilt = bool(document.ForceRebuild3(top_only))
        else:
            rebuilt = bool(_com_value(document, "EditRebuild3"))
        result["rebuilt"] = rebuilt
        result["needs_rebuild_after"] = int(
            _com_value(extension, "NeedsRebuild2")
        )
        result["document"] = _describe_document(document)
        result["diagnostics"] = _diagnose_features(document, max_features)
        if not rebuilt:
            result["error"] = {
                "type": "RebuildFailed",
                "message": "SOLIDWORKS reported rebuild errors",
            }
            return result

        result["ok"] = True
        return result
    except Exception as exc:
        result["error"] = _error(exc)
        return result
    finally:
        pythoncom.CoUninitialize()
