"""SOLIDWORKS document operations for native Windows hosts."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

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
STANDARD_VIEW_IDS = {
    "front": 1,
    "back": 2,
    "left": 3,
    "right": 4,
    "top": 5,
    "bottom": 6,
    "isometric": 7,
    "trimetric": 8,
    "dimetric": 9,
}
RENDER_VIEWS = ("current", *STANDARD_VIEW_IDS)
_EXPORT_FORMATS = {
    1: {".step", ".stp"},
    2: {".step", ".stp", ".glb"},
    3: {".pdf", ".dwg"},
}
_SAVE_ERRORS = {
    1: "generic-save-error",
    2: "read-only-save-error",
    4: "file-name-empty",
    8: "file-name-contains-at-sign",
    16: "file-lock-error",
    32: "save-format-not-available",
    128: "do-not-overwrite",
    256: "invalid-file-extension",
    512: "no-selection",
    1024: "bad-edrawings-version",
    2048: "name-exceeds-max-path-length",
    4096: "save-as-not-supported",
    8192: "requires-saving-references",
    16384: "detached-drawings-not-supported",
}
_SAVE_WARNINGS = {
    1: "rebuild-error",
    2: "needs-rebuild",
    4: "views-need-update",
    8: "animator-needs-solve",
    16: "animator-feature-edits",
    32: "edrawings-bad-selection",
    64: "animator-light-edits",
    128: "animator-camera-views",
    256: "animator-section-views",
    512: "missing-ole-objects",
    1024: "opened-view-only",
    2048: "xml-invalid",
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


def _validate_render_arguments(
    output: str, width: int, height: int, view: str
) -> Optional[Dict[str, Any]]:
    if Path(output).suffix.casefold() != ".bmp":
        return {
            "type": "InvalidArgument",
            "message": "render output path must use the .bmp extension",
        }
    if width <= 0 or height <= 0:
        return {
            "type": "InvalidArgument",
            "message": "render width and height must be positive pixel counts",
        }
    if view not in RENDER_VIEWS:
        return {
            "type": "InvalidArgument",
            "message": f"unsupported render view: {view}",
        }
    return None


def _parse_bmp_dimensions(header: bytes) -> Optional[Dict[str, int]]:
    if len(header) < 26 or header[:2] != b"BM":
        return None
    width = int.from_bytes(header[18:22], "little", signed=True)
    height = int.from_bytes(header[22:26], "little", signed=True)
    if width <= 0 or height == 0:
        return None
    return {"width": width, "height": abs(height)}


def _export_format(document_type: int, output: Path) -> Optional[str]:
    extension = output.suffix.casefold()
    if extension not in _EXPORT_FORMATS.get(document_type, set()):
        return None
    return extension.removeprefix(".").upper()


def _export_signature_valid(export_format: str, header: bytes) -> bool:
    if export_format == "PDF":
        return header.startswith(b"%PDF-")
    if export_format == "DWG":
        return header.startswith(b"AC10")
    if export_format in {"STEP", "STP"}:
        return b"ISO-10303-21;" in header
    if export_format == "GLB":
        return header.startswith(b"glTF\x02\x00\x00\x00")
    return False


def _bitmask_names(code: int, values: Dict[int, str]) -> list[str]:
    return [name for bit, name in values.items() if code & bit]


def _export_source_state(document: Any) -> Dict[str, Any]:
    extension = _com_value(document, "Extension")
    return {
        "document": _describe_document(document),
        "needs_rebuild": int(_com_value(extension, "NeedsRebuild2")),
    }


def _export_source_warnings(state: Dict[str, Any]) -> list[Dict[str, Any]]:
    warnings = []
    if state["document"]["modified"]:
        warnings.append(
            {
                "code": "source-modified",
                "message": "source document has unsaved modifications",
            }
        )
    if state["needs_rebuild"] != 0:
        warnings.append(
            {
                "code": "source-needs-rebuild",
                "message": "source document requires rebuild",
                "needs_rebuild": state["needs_rebuild"],
            }
        )
    return warnings


def _export_source_change_warnings(
    before: Dict[str, Any], after: Dict[str, Any]
) -> list[Dict[str, Any]]:
    warnings = []
    before_document = before["document"]
    after_document = after["document"]
    changed_identity = [
        name
        for name in ("title", "path", "type")
        if before_document.get(name) != after_document.get(name)
    ]
    if changed_identity:
        warnings.append(
            {
                "code": "source-document-changed",
                "message": "export changed the active source document identity",
                "fields": changed_identity,
            }
        )
    if before_document["modified"] != after_document["modified"]:
        warnings.append(
            {
                "code": "source-modified-by-export",
                "message": "export changed the source document modified state",
                "before": before_document["modified"],
                "after": after_document["modified"],
            }
        )
    if before["needs_rebuild"] != after["needs_rebuild"]:
        warnings.append(
            {
                "code": "source-rebuild-state-changed",
                "message": "export changed the source document rebuild state",
                "before": before["needs_rebuild"],
                "after": after["needs_rebuild"],
            }
        )
    return warnings


def open_windows_document(
    path: str,
    *,
    read_only: bool = False,
    configuration: str = "",
    app: Any = None,
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

    owns_com = app is None
    if owns_com:
        pythoncom.CoInitialize()
    try:
        if app is None:
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
        if owns_com:
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
        raw_box = list(_com_value(body, "GetBodyBox") or ())
        approximate_bounding_box = None
        if len(raw_box) == 6:
            minimum = [float(value) for value in raw_box[:3]]
            maximum = [float(value) for value in raw_box[3:]]
            size_m = [upper - lower for lower, upper in zip(minimum, maximum)]
            approximate_bounding_box = {
                "coordinate_system": "model",
                "unit": "meter",
                "minimum": {"x": minimum[0], "y": minimum[1], "z": minimum[2]},
                "maximum": {"x": maximum[0], "y": maximum[1], "z": maximum[2]},
                "size_mm": {
                    "x": size_m[0] * 1000.0,
                    "y": size_m[1] * 1000.0,
                    "z": size_m[2] * 1000.0,
                },
                "accuracy": "approximate",
            }
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
                "approximate_bounding_box": approximate_bounding_box,
            }
        )
    return {"applicable": True, "items": items, "count": len(items)}


def inspect_active_windows_document(
    *, detail: str = "summary", max_features: int = 500, app: Any = None
) -> Dict[str, Any]:
    """Describe the active SOLIDWORKS document without modifying it."""

    if sys.platform != "win32":
        return _unsupported("document.inspect")

    import pythoncom
    import win32com.client

    result: Dict[str, Any] = {"ok": False, "action": "document.inspect"}
    owns_com = app is None
    if owns_com:
        pythoncom.CoInitialize()
    try:
        if app is None:
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
        result["needs_rebuild"] = int(
            _com_value(extension, "NeedsRebuild2")
        )
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
        if owns_com:
            pythoncom.CoUninitialize()


def render_active_windows_document(
    output: str,
    *,
    width: int = 1024,
    height: int = 768,
    view: str = "current",
    fit: bool = True,
    overwrite: bool = False,
    app: Any = None,
) -> Dict[str, Any]:
    """Render the active SOLIDWORKS view to a verified bitmap artifact."""

    invalid = _validate_render_arguments(output, width, height, view)
    if invalid is not None:
        return {"ok": False, "action": "document.render", "error": invalid}
    if sys.platform != "win32":
        return _unsupported("document.render")

    output_path = Path(output).expanduser().resolve()
    result: Dict[str, Any] = {
        "ok": False,
        "action": "document.render",
        "output": str(output_path),
        "requested_size": {"width": width, "height": height, "unit": "pixel"},
        "view": {
            "name": view,
            "standard_id": STANDARD_VIEW_IDS.get(view),
        },
        "fit": fit,
    }
    if not output_path.parent.is_dir():
        result["error"] = {
            "type": "ParentDirectoryNotFound",
            "message": f"output directory does not exist: {output_path.parent}",
        }
        return result
    if output_path.exists() and not overwrite:
        result["error"] = {
            "type": "OutputExists",
            "message": "output already exists; use --overwrite to replace it",
        }
        return result

    import pythoncom
    import win32com.client

    owns_com = app is None
    if owns_com:
        pythoncom.CoInitialize()
    try:
        if app is None:
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
        standard_view_id = STANDARD_VIEW_IDS.get(view)
        if standard_view_id is not None:
            document.ShowNamedView2("", standard_view_id)
        if fit:
            _com_value(document, "ViewZoomtofit2")
        saved = bool(document.SaveBMP(str(output_path), width, height))
        result["api_saved"] = saved
        if not saved or not output_path.is_file():
            result["error"] = {
                "type": "RenderFailed",
                "message": "SOLIDWORKS failed to create the bitmap",
            }
            return result

        with output_path.open("rb") as bitmap:
            actual_size = _parse_bmp_dimensions(bitmap.read(26))
        result["actual_size"] = (
            {**actual_size, "unit": "pixel"} if actual_size is not None else None
        )
        if actual_size != {"width": width, "height": height}:
            result["error"] = {
                "type": "RenderVerificationFailed",
                "message": "bitmap dimensions did not match the requested size",
            }
            return result

        result["artifact"] = {
            "kind": "image",
            "media_type": "image/bmp",
            "path": str(output_path),
            "size_bytes": output_path.stat().st_size,
        }
        result["ok"] = True
        return result
    except Exception as exc:
        result["error"] = _error(exc)
        return result
    finally:
        if owns_com:
            pythoncom.CoUninitialize()


def export_active_windows_document(
    output: str,
    *,
    overwrite: bool = False,
    strict: bool = False,
    app: Any = None,
) -> Dict[str, Any]:
    """Export the active document to a verified neutral or drawing format."""

    if sys.platform != "win32":
        return _unsupported("document.export")

    output_path = Path(output).expanduser().resolve()
    result: Dict[str, Any] = {
        "ok": False,
        "action": "document.export",
        "output": str(output_path),
    }
    if not output_path.parent.is_dir():
        result["error"] = {
            "type": "ParentDirectoryNotFound",
            "message": f"output directory does not exist: {output_path.parent}",
        }
        return result
    if output_path.exists() and not overwrite:
        result["error"] = {
            "type": "OutputExists",
            "message": "output already exists; use --overwrite to replace it",
        }
        return result

    import pythoncom
    import win32com.client

    owns_com = app is None
    temporary_output_path: Optional[Path] = None
    if owns_com:
        pythoncom.CoInitialize()
    try:
        if app is None:
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

        before = _export_source_state(document)
        export_format = _export_format(before["document"]["type"], output_path)
        if export_format is None:
            allowed = sorted(
                _EXPORT_FORMATS.get(before["document"]["type"], set())
            )
            result["error"] = {
                "type": "UnsupportedExportFormat",
                "message": (
                    "unsupported output extension for document type "
                    f"{before['document']['type']}; "
                    f"allowed: {', '.join(allowed) or 'none'}"
                ),
            }
            return result

        warnings = _export_source_warnings(before)
        if strict and warnings:
            result["error"] = {
                "type": "SourceNotClean",
                "message": "source document is not ready for strict export",
                "violations": warnings,
            }
            return result

        export_path = output_path
        if strict:
            temporary_output_path = output_path.with_name(
                f".{output_path.stem}.{uuid4().hex}.swcli{output_path.suffix}"
            )
            export_path = temporary_output_path

        document.ClearSelection2(True)
        save_error = int(document.SaveAs3(str(export_path), 0, 1))
        if save_error != 0 or not export_path.is_file():
            result["error"] = {
                "type": "ExportFailed",
                "message": "SOLIDWORKS failed to export the active document",
                "save_errors": save_error,
            }
            return result

        size_bytes = export_path.stat().st_size
        with export_path.open("rb") as exported_file:
            signature_valid = _export_signature_valid(
                export_format, exported_file.read(128)
            )
        if size_bytes <= 0 or not signature_valid:
            result["error"] = {
                "type": "ExportVerificationFailed",
                "message": "exported file did not pass content verification",
                "verification": {
                    "non_empty": size_bytes > 0,
                    "signature_valid": signature_valid,
                },
            }
            return result

        after = _export_source_state(document)
        changes = _export_source_change_warnings(before, after)
        if strict and changes:
            result["error"] = {
                "type": "SourceStateChanged",
                "message": "export changed the source document state",
                "violations": changes,
            }
            return result
        warnings.extend(changes)

        if strict:
            export_path.replace(output_path)
            temporary_output_path = None

        result["artifact"] = {
            "kind": "cad-export",
            "format": export_format,
            "path": str(output_path),
            "size_bytes": size_bytes,
        }
        if warnings:
            result["warnings"] = warnings
        result["ok"] = True
        return result
    except Exception as exc:
        result["error"] = _error(exc)
        return result
    finally:
        if temporary_output_path is not None:
            try:
                temporary_output_path.unlink(missing_ok=True)
            except OSError:
                pass
        if owns_com:
            pythoncom.CoUninitialize()


def save_active_windows_document(*, app: Any = None) -> Dict[str, Any]:
    """Save the active native document in place and report SOLIDWORKS status."""

    if sys.platform != "win32":
        return _unsupported("document.save")

    result: Dict[str, Any] = {
        "ok": False,
        "action": "document.save",
    }

    import pythoncom
    import win32com.client

    owns_com = app is None
    if owns_com:
        pythoncom.CoInitialize()
    try:
        if app is None:
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

        before = _describe_document(document)
        result["document"] = before
        errors = win32com.client.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_I4, 0
        )
        warnings = win32com.client.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_I4, 0
        )
        saved = bool(document.Save3(1, errors, warnings))
        result["api_saved"] = saved
        error_code = int(errors.value)
        warning_code = int(warnings.value)
        result["save_errors"] = error_code
        result["save_error_names"] = _bitmask_names(error_code, _SAVE_ERRORS)
        result["save_warnings"] = warning_code
        result["save_warning_names"] = _bitmask_names(
            warning_code, _SAVE_WARNINGS
        )
        after = _describe_document(document)
        result["document_after"] = after

        if not saved or error_code != 0:
            result["error"] = {
                "type": "SaveFailed",
                "message": "SOLIDWORKS failed to save the active document",
            }
            return result
        if after.get("modified"):
            result["error"] = {
                "type": "DocumentStillModified",
                "message": "SOLIDWORKS left the document modified after saving",
            }
            return result

        result["ok"] = True
        return result
    except Exception as exc:
        result["error"] = _error(exc)
        return result
    finally:
        if owns_com:
            pythoncom.CoUninitialize()


def close_active_windows_document(
    *, discard: bool = False, app: Any = None
) -> Dict[str, Any]:
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
    owns_com = app is None
    if owns_com:
        pythoncom.CoInitialize()
    try:
        if app is None:
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
        if owns_com:
            pythoncom.CoUninitialize()


def diagnose_active_windows_document(
    *, max_features: int = 500, app: Any = None
) -> Dict[str, Any]:
    """Report rebuild state and per-feature errors without modifying the model."""

    if sys.platform != "win32":
        return _unsupported("document.diagnose")

    import pythoncom
    import win32com.client

    result: Dict[str, Any] = {"ok": False, "action": "document.diagnose"}
    owns_com = app is None
    if owns_com:
        pythoncom.CoInitialize()
    try:
        if app is None:
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
        if owns_com:
            pythoncom.CoUninitialize()


def rebuild_active_windows_document(
    *,
    force: bool = False,
    top_only: bool = False,
    max_features: int = 500,
    app: Any = None,
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
    owns_com = app is None
    if owns_com:
        pythoncom.CoInitialize()
    try:
        if app is None:
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
        if owns_com:
            pythoncom.CoUninitialize()
