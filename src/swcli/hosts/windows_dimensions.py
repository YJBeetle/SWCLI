"""Internal driving-dimension adapters on the owning worker COM thread.

Not exposed by the operation catalog yet. Native creation may partially mutate
the sketch; the returned handle is evidence, not a transaction/rollback claim.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

from .windows import _com_value, _error
from .windows_sketches import _circle_verification, _unabsorbed_profile

_INPUT_VALUE_ON_CREATE = 10
_DRIVING = 2
_CURRENT_CONFIGURATION = 1
_TOLERANCE_MM = 1e-6


def _variant(kind: str, value: Any) -> Any:
    import pythoncom
    from win32com.client import VARIANT

    types = {
        "dispatch": pythoncom.VT_DISPATCH,
        "empty": pythoncom.VT_EMPTY,
        "double-array": pythoncom.VT_ARRAY | pythoncom.VT_R8,
    }
    return VARIANT(types[kind], value)


def _annotation_location(app: Any, sketch: Any, x: float, y: float) -> Any:
    utility = _com_value(app, "GetMathUtility")
    # Late binding can expose this object-returning method as a property.
    utility._FlagAsMethod("CreatePoint")
    point = utility.CreatePoint(_variant("double-array", (x, y, 0.0)))
    inverse = _com_value(_com_value(sketch, "ModelToSketchTransform"), "Inverse")
    values = tuple(
        float(v) for v in _com_value(point.MultiplyTransform(inverse), "ArrayData")
    )
    if len(values) != 3 or not all(math.isfinite(v) for v in values):
        raise RuntimeError(
            "SOLIDWORKS returned an invalid dimension annotation location"
        )
    return values


def create_circle_diameter_windows_with_handle(
    *, app: Any, document: Any, sketch_feature: Any, diameter_mm: float
) -> Tuple[Dict[str, Any], Optional[Any]]:
    """Add one driving diameter to an exact, unconsumed full-circle sketch."""
    result: Dict[str, Any] = {"ok": False, "action": "sketch.dimension-diameter"}
    dimension = None
    sketch = None
    entered = False
    selected = False
    preference = None
    preference_changed = False
    try:
        valid = (
            not isinstance(diameter_mm, bool)
            and isinstance(diameter_mm, (int, float))
            and math.isfinite(diameter_mm)
            and diameter_mm > 0
            and diameter_mm / 2000 > 0
        )
    except (OverflowError, TypeError, ValueError):
        valid = False
    if not valid:
        result["error"] = {
            "type": "InvalidArgument",
            "message": "diameter_mm must be a positive finite, representable length",
        }
        return result, None
    try:
        if int(_com_value(document, "GetType")) != 1:
            result["error"] = {
                "type": "UnsupportedDocumentType",
                "message": "driving diameter creation currently requires a part",
            }
            return result, None
        manager = _com_value(document, "SketchManager")
        if _com_value(manager, "ActiveSketch") is not None:
            result["error"] = {
                "type": "SketchEditInProgress",
                "message": "finish the existing sketch edit before adding a dimension",
            }
            return result, None
        if _unabsorbed_profile(app, document, sketch_feature) is None:
            result["error"] = {
                "type": "SketchUnavailable",
                "message": "the exact sketch is not an unabsorbed 2D profile in this part",
            }
            return result, None
        sketch = _com_value(sketch_feature, "GetSpecificFeature2")
        segments = tuple(_com_value(sketch, "GetSketchSegments") or ())
        if (
            len(segments) != 1
            or bool(_com_value(segments[0], "ConstructionGeometry"))
            or int(_com_value(segments[0], "GetType")) != 1
            or int(_com_value(segments[0], "IsCircle")) != 1
        ):
            result["error"] = {
                "type": "UnsupportedDimensionProfile",
                "message": "require exactly one complete non-construction circle",
            }
            return result, None
        if _com_value(sketch_feature, "GetFirstDisplayDimension") is not None:
            result["error"] = {
                "type": "SketchAlreadyDimensioned",
                "message": "the profile already has dimensions; do not add an ambiguous duplicate",
            }
            return result, None
        arc = segments[0]
        center = _com_value(arc, "GetCenterPoint2")
        x, y, z = (float(_com_value(center, axis)) for axis in "XYZ")
        radius = float(_com_value(arc, "GetRadius"))
        if not all(math.isfinite(v) for v in (x, y, z, radius)) or radius <= 0:
            raise RuntimeError("SOLIDWORKS returned invalid source circle geometry")
        configuration = str(
            _com_value(
                _com_value(document, "ConfigurationManager"), "ActiveConfiguration"
            ).Name
        )
        location = _annotation_location(app, sketch, x + radius * 2, y + radius * 2)
        document.ClearSelection2(True)
        selected = True
        if not sketch_feature.Select2(False, 0):
            result["error"] = {
                "type": "SketchSelectionFailed",
                "message": "SOLIDWORKS could not select the exact sketch",
            }
            return result, None
        entered = True
        _com_value(document, "EditSketch")
        active = _com_value(manager, "ActiveSketch")
        if active is None or int(app.IsSame(active, sketch)) != 1:
            raise RuntimeError("SOLIDWORKS did not enter the exact registered sketch")
        document.ClearSelection2(True)
        if not arc.Select4(False, _variant("dispatch", None)):
            result["error"] = {
                "type": "SketchSelectionFailed",
                "message": "SOLIDWORKS could not select the circle",
            }
            return result, None
        preference = bool(app.GetUserPreferenceToggle(_INPUT_VALUE_ON_CREATE))
        preference_changed = True
        # Native late binding can return None even after a successful setter.
        # Verify the actual preference instead of inferring success from it.
        app.SetUserPreferenceToggle(_INPUT_VALUE_ON_CREATE, False)
        if bool(app.GetUserPreferenceToggle(_INPUT_VALUE_ON_CREATE)):
            raise RuntimeError(
                "SOLIDWORKS could not suppress the dimension-value dialog"
            )
        display = document.AddDiameterDimension2(*location)
        if display is None:
            result["error"] = {
                "type": "DimensionCreationFailed",
                "message": "SOLIDWORKS did not create a diameter dimension",
            }
            return result, None
        dimension = display.GetDimension2(0)
        if dimension is None:
            raise RuntimeError("SOLIDWORKS did not return the created dimension")
        if int(_com_value(dimension, "DrivenState")) != _DRIVING or bool(
            _com_value(dimension, "ReadOnly")
        ):
            result["error"] = {
                "type": "DimensionNotDriving",
                "message": "created dimension is not a writable driving dimension",
            }
            return result, dimension
        status = int(
            dimension.SetSystemValue3(
                diameter_mm / 1000, _CURRENT_CONFIGURATION, _variant("empty", None)
            )
        )
        result["native_status"] = status
        if status != 0:
            result["error"] = {
                "type": "DimensionSetFailed",
                "message": "SOLIDWORKS rejected the driving diameter value",
            }
            return result, dimension
        manager.InsertSketch(True)
        if _com_value(manager, "ActiveSketch") is not None:
            raise RuntimeError("SOLIDWORKS did not exit the dimension edit")
        entered = False
        actual = float(dimension.GetSystemValue2(configuration)) * 1000
        verification = _circle_verification(sketch, diameter_mm / 2, x * 1000, y * 1000)
        result.update(
            dimension={
                "kind": "diameter",
                "unit": "millimeter",
                "value": actual if math.isfinite(actual) else None,
                "driven_state": int(_com_value(dimension, "DrivenState")),
                "read_only": bool(_com_value(dimension, "ReadOnly")),
                "configuration": configuration,
                "native_name": str(_com_value(dimension, "FullName")),
            },
            geometry_verification=verification,
            constraint_status=int(_com_value(sketch, "GetConstrainedStatus")),
            editing=False,
        )
        if (
            not math.isfinite(actual)
            or not math.isclose(actual, diameter_mm, rel_tol=0, abs_tol=_TOLERANCE_MM)
            or not verification["passed"]
            or result["dimension"]["driven_state"] != _DRIVING
            or result["dimension"]["read_only"]
        ):
            result["error"] = {
                "type": "DimensionVerificationFailed",
                "message": "native driving value or circle geometry did not match the request",
            }
            return result, dimension
        result["ok"] = True
        return result, dimension
    except Exception as exc:
        result["error"] = _error(exc)
        return result, dimension
    finally:

        def cleanup(code, action):
            try:
                action()
            except Exception as exc:
                result.setdefault("warnings", []).append(
                    {"code": code, "message": str(exc)}
                )

        if entered and sketch is not None:

            def exit_owned_edit():
                active = _com_value(manager, "ActiveSketch")
                result["editing"] = active is not None
                if active is None:
                    return
                if int(app.IsSame(active, sketch)) != 1:
                    raise RuntimeError(
                        "another sketch became active; refusing to close its edit"
                    )
                manager.InsertSketch(True)
                result["editing"] = _com_value(manager, "ActiveSketch") is not None
                if result["editing"]:
                    raise RuntimeError(
                        "owned sketch editing remained active after cleanup"
                    )

            cleanup("sketch-edit-cleanup-failed", exit_owned_edit)
        if preference_changed:

            def restore_preference():
                app.SetUserPreferenceToggle(_INPUT_VALUE_ON_CREATE, preference)
                if (
                    bool(app.GetUserPreferenceToggle(_INPUT_VALUE_ON_CREATE))
                    != preference
                ):
                    raise RuntimeError(
                        "SOLIDWORKS could not restore the dimension-value preference"
                    )

            cleanup(
                "dimension-preference-restore-failed",
                restore_preference,
            )
        if selected:
            cleanup("selection-cleanup-failed", lambda: document.ClearSelection2(True))
