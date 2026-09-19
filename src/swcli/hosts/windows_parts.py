"""Typed part-modeling operations for native Windows hosts."""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .windows import PROG_ID, _com_value, _describe_document, _error
from .windows_documents import _diagnose_features, _inspect_bodies


_SAVE_CURRENT_VERSION = 0
_SAVE_SILENT = 1


def _invalid(message: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "action": "part.create-box",
        "error": {"type": "InvalidArgument", "message": message},
    }


def _validate_box_arguments(
    output: str, width_mm: float, height_mm: float, depth_mm: float
) -> Optional[Dict[str, Any]]:
    if Path(output).suffix.casefold() != ".sldprt":
        return _invalid("output path must use the .SLDPRT extension")
    for name, value in (
        ("width_mm", width_mm),
        ("height_mm", height_mm),
        ("depth_mm", depth_mm),
    ):
        if not math.isfinite(value) or value <= 0:
            return _invalid(f"{name} must be a positive finite number")
    return None


def create_box_part_windows(
    output: str,
    *,
    width_mm: float,
    height_mm: float,
    depth_mm: float,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Create, rebuild, diagnose, and save a centered rectangular extrusion."""

    invalid = _validate_box_arguments(output, width_mm, height_mm, depth_mm)
    if invalid is not None:
        return invalid
    if sys.platform != "win32":
        return {
            "ok": False,
            "action": "part.create-box",
            "error": {
                "type": "UnsupportedPlatform",
                "message": "native Windows part operations require Windows",
            },
        }

    output_path = Path(output).expanduser().resolve()
    result: Dict[str, Any] = {
        "ok": False,
        "action": "part.create-box",
        "output": str(output_path),
        "dimensions": {
            "unit": "millimeter",
            "width": width_mm,
            "height": height_mm,
            "depth": depth_mm,
        },
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

        if _com_value(app, "ActiveDoc") is not None:
            result["error"] = {
                "type": "ActiveDocument",
                "message": "close the active document before creating a new part",
            }
            return result

        document = _com_value(app, "NewPart")
        if document is None:
            result["error"] = {
                "type": "NewPartFailed",
                "message": "SOLIDWORKS could not create a part from the default template",
            }
            return result

        width_m = width_mm / 1000.0
        height_m = height_mm / 1000.0
        depth_m = depth_mm / 1000.0
        sketch_manager = _com_value(document, "SketchManager")
        sketch_manager.InsertSketch(True)
        segments = sketch_manager.CreateCenterRectangle(
            0.0,
            0.0,
            0.0,
            width_m / 2.0,
            height_m / 2.0,
            0.0,
        )
        if not segments:
            result["error"] = {
                "type": "SketchFailed",
                "message": "SOLIDWORKS did not create rectangle sketch segments",
            }
            return result
        sketch_manager.InsertSketch(True)

        feature_manager = _com_value(document, "FeatureManager")
        feature = feature_manager.FeatureExtrusion3(
            True,
            False,
            False,
            0,
            0,
            depth_m,
            0.0,
            False,
            False,
            False,
            False,
            0.0,
            0.0,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            0,
            0,
            False,
        )
        if feature is None:
            result["error"] = {
                "type": "ExtrusionFailed",
                "message": "SOLIDWORKS did not create the extrusion feature",
            }
            return result

        rebuilt = bool(_com_value(document, "EditRebuild3"))
        diagnostics = _diagnose_features(document, 500)
        result["rebuilt"] = rebuilt
        result["diagnostics"] = diagnostics
        if not rebuilt or not diagnostics["healthy"]:
            result["error"] = {
                "type": "ModelInvalid",
                "message": "created model did not pass rebuild diagnostics",
            }
            return result

        document.ClearSelection2(True)
        extension = _com_value(document, "Extension")
        save_errors = win32com.client.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_I4, 0
        )
        save_warnings = win32com.client.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_I4, 0
        )
        saved = bool(
            extension.SaveAs3(
                str(output_path),
                _SAVE_CURRENT_VERSION,
                _SAVE_SILENT,
                None,
                None,
                save_errors,
                save_warnings,
            )
        )
        result["save_errors"] = int(save_errors.value)
        result["save_warnings"] = int(save_warnings.value)
        result["saved"] = saved
        if not saved:
            result["error"] = {
                "type": "SaveFailed",
                "message": "SOLIDWORKS failed to save the created part",
            }
            return result

        result["document"] = _describe_document(document)
        result["bodies"] = _inspect_bodies(document)
        result["feature"] = {
            "name": str(_com_value(feature, "Name")),
            "type": str(_com_value(feature, "GetTypeName2")),
        }
        result["ok"] = True
        return result
    except Exception as exc:
        result["error"] = _error(exc)
        return result
    finally:
        pythoncom.CoUninitialize()
