"""Typed part-modeling operations for native Windows hosts."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .windows import PROG_ID, _com_value, _describe_document, _error
from .windows_documents import _diagnose_features, _inspect_bodies


_SAVE_CURRENT_VERSION = 0
_SAVE_SILENT = 1
_SW_DEFAULT_TEMPLATE_PART = 8
_BOX_VERIFICATION_TOLERANCE_MM = 0.1


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


def _verify_box_geometry(
    bodies: Dict[str, Any], width_mm: float, height_mm: float, depth_mm: float
) -> Dict[str, Any]:
    expected = {"x": width_mm, "y": height_mm, "z": depth_mm}
    solid_bodies = [
        body
        for body in bodies.get("items", [])
        if body.get("type", {}).get("name") == "solid"
    ]
    actual = None
    if len(solid_bodies) == 1:
        bounding_box = solid_bodies[0].get("approximate_bounding_box")
        if bounding_box is not None:
            actual = bounding_box.get("size_mm")

    passed = actual is not None and all(
        math.isclose(
            float(actual[axis]),
            expected[axis],
            rel_tol=1e-6,
            abs_tol=_BOX_VERIFICATION_TOLERANCE_MM,
        )
        for axis in ("x", "y", "z")
    )
    return {
        "passed": passed,
        "method": "axis-aligned-approximate-body-box",
        "expected_size_mm": expected,
        "actual_size_mm": actual,
        "absolute_tolerance_mm": _BOX_VERIFICATION_TOLERANCE_MM,
        "note": (
            "SOLIDWORKS body boxes are approximate; this is a modeling smoke "
            "check, not a precision metrology result"
        ),
    }


def _resolve_part_template(app: Any, template: Optional[str]) -> Dict[str, Any]:
    """Resolve a real part template without opening SOLIDWORKS template UI."""

    configured = ""
    if template is not None:
        candidate = Path(template).expanduser().resolve()
        source = "explicit"
    else:
        try:
            configured = str(
                app.GetUserPreferenceStringValue(_SW_DEFAULT_TEMPLATE_PART) or ""
            ).strip()
        except Exception:
            configured = ""
        candidate = Path(configured).expanduser().resolve() if configured else None
        source = "solidworks-default"

    if candidate is not None and candidate.suffix.casefold() != ".prtdot":
        return {
            "ok": False,
            "error": {
                "type": "InvalidPartTemplate",
                "message": "part template path must use the .PRTDOT extension",
            },
            "path": str(candidate),
            "source": source,
        }
    if candidate is not None and candidate.is_file():
        return {"ok": True, "path": str(candidate), "source": source}

    searched_roots = []
    if template is None:
        roots = []
        for variable in ("PROGRAMDATA", "ProgramFiles", "ProgramFiles(x86)"):
            value = os.environ.get(variable)
            if value:
                root = Path(value) / "SOLIDWORKS"
                if root not in roots:
                    roots.append(root)
        for root in roots:
            searched_roots.append(str(root))
            if not root.is_dir():
                continue
            try:
                discovered = sorted(
                    path.resolve()
                    for path in root.rglob("*.prtdot")
                    if path.is_file()
                )
            except OSError:
                continue
            if discovered:
                return {
                    "ok": True,
                    "path": str(discovered[0]),
                    "source": "installed-template-discovery",
                    "configured_path": configured or None,
                }

    return {
        "ok": False,
        "error": {
            "type": "PartTemplateUnavailable",
            "message": (
                "no usable SOLIDWORKS part template was found; pass --template "
                "with an existing .PRTDOT file"
            ),
        },
        "path": str(candidate) if candidate is not None else None,
        "source": source,
        "configured_path": configured or None,
        "searched_roots": searched_roots,
    }


def create_box_part_windows(
    output: str,
    *,
    width_mm: float,
    height_mm: float,
    depth_mm: float,
    template: Optional[str] = None,
    overwrite: bool = False,
    app: Any = None,
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

        if _com_value(app, "ActiveDoc") is not None:
            result["error"] = {
                "type": "ActiveDocument",
                "message": "close the active document before creating a new part",
            }
            return result

        template_result = _resolve_part_template(app, template)
        result["template"] = {
            key: value for key, value in template_result.items() if key != "error"
        }
        if not template_result["ok"]:
            result["error"] = template_result["error"]
            return result

        document = app.NewDocument(template_result["path"], 0, 0.0, 0.0)
        if document is None:
            result["error"] = {
                "type": "NewDocumentFailed",
                "message": "SOLIDWORKS could not create a part from the resolved template",
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

        bodies = _inspect_bodies(document)
        geometry_verification = _verify_box_geometry(
            bodies, width_mm, height_mm, depth_mm
        )
        result["bodies"] = bodies
        result["geometry_verification"] = geometry_verification
        if not geometry_verification["passed"]:
            result["error"] = {
                "type": "GeometryVerificationFailed",
                "message": "created body did not match the requested box dimensions",
            }
            return result

        document.ClearSelection2(True)
        # ModelDocExtension.SaveAs3 has two optional COM object parameters that
        # dynamic pywin32 Dispatch cannot marshal as null on the tested host.
        # ModelDoc2.SaveAs3 is scalar-only and returns the swFileSaveError_e code.
        save_error = int(
            document.SaveAs3(
                str(output_path), _SAVE_CURRENT_VERSION, _SAVE_SILENT
            )
        )
        saved = save_error == 0 and output_path.is_file()
        result["save_errors"] = save_error
        result["save_warnings"] = None
        result["saved"] = saved
        if not saved:
            result["error"] = {
                "type": "SaveFailed",
                "message": "SOLIDWORKS failed to save the created part",
            }
            return result

        result["document"] = _describe_document(document)
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
        if owns_com:
            pythoncom.CoUninitialize()
