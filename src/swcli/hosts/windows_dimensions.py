"""Internal driving-dimension adapters on the owning worker COM thread.

Not exposed by the operation catalog yet. Native creation may partially mutate
the sketch; the returned handle is evidence, not a transaction/rollback claim.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Optional, Tuple

from .windows import _com_value, _error
from .windows_documents import _diagnose_features
from .windows_measurements import measure_part_windows
from .windows_sketches import _circle_verification, _unabsorbed_profile

_INPUT_VALUE_ON_CREATE = 10
_DRIVING = 2
_CURRENT_CONFIGURATION = 1
_TOLERANCE_MM = 1e-6
_TRAVERSAL_LIMIT = 10000
_EQUATION_LHS = re.compile(r'^\s*"((?:[^"\r\n]|"")+)"\s*=')


class _DimensionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _positive_length(value: Any) -> bool:
    try:
        return (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(value)
            and value > 0
            and value / 2000 > 0
        )
    except (OverflowError, TypeError, ValueError):
        return False


def _live_profile(app: Any, document: Any, sketch_feature: Any) -> Any:
    """Find the exact native sketch, including a profile absorbed by a feature."""
    pending = [(_com_value(document, "FirstFeature"), "GetNextFeature")]
    for _ in range(_TRAVERSAL_LIMIT):
        if not pending:
            raise _DimensionError(
                "SketchUnavailable",
                "the exact owning sketch is no longer live in the selected part",
            )
        feature, next_member = pending.pop()
        if feature is None:
            continue
        if int(app.IsSame(feature, sketch_feature)) == 1:
            if _com_value(feature, "GetTypeName2") != "ProfileFeature":
                raise _DimensionError(
                    "SketchUnavailable", "the owning feature is not a 2D profile"
                )
            return _com_value(feature, "GetSpecificFeature2")
        pending.append((_com_value(feature, next_member), next_member))
        pending.append((_com_value(feature, "GetFirstSubFeature"), "GetNextSubFeature"))
    raise _DimensionError(
        "DimensionObservationUnavailable", "native feature traversal exceeded its limit"
    )


def _owned_dimension(
    app: Any, document: Any, sketch_feature: Any, dimension: Any
) -> Any:
    if int(_com_value(document, "GetType")) != 1:
        raise _DimensionError(
            "UnsupportedDocumentType", "driving diameter operations require a part"
        )
    sketch = _live_profile(app, document, sketch_feature)
    owner = _com_value(dimension, "GetFeatureOwner")
    if owner is None or int(app.IsSame(owner, sketch_feature)) != 1:
        raise _DimensionError(
            "DimensionUnavailable",
            "the native dimension does not belong to its registered sketch",
        )
    display = _com_value(sketch_feature, "GetFirstDisplayDimension")
    for _ in range(_TRAVERSAL_LIMIT):
        if display is None:
            raise _DimensionError(
                "DimensionUnavailable",
                "the exact dimension is no longer live in its owning sketch",
            )
        native = display.GetDimension2(0)
        if native is not None and int(app.IsSame(native, dimension)) == 1:
            return sketch
        display = sketch_feature.GetNextDisplayDimension(display)
    raise _DimensionError(
        "DimensionObservationUnavailable",
        "native dimension traversal exceeded its limit",
    )


def _circle(sketch: Any) -> Tuple[float, float, float]:
    segments = tuple(_com_value(sketch, "GetSketchSegments") or ())
    if (
        len(segments) != 1
        or bool(_com_value(segments[0], "ConstructionGeometry"))
        or int(_com_value(segments[0], "GetType")) != 1
        or int(_com_value(segments[0], "IsCircle")) != 1
    ):
        raise _DimensionError(
            "UnsupportedDimensionProfile",
            "require exactly one complete non-construction circle",
        )
    arc = segments[0]
    point = _com_value(arc, "GetCenterPoint2")
    coordinates = tuple(float(_com_value(point, axis)) * 1000 for axis in "XYZ")
    radius = float(_com_value(arc, "GetRadius")) * 1000
    if (
        not all(math.isfinite(v) for v in (*coordinates, radius))
        or radius <= 0
        or not math.isclose(coordinates[2], 0, rel_tol=0, abs_tol=_TOLERANCE_MM)
    ):
        raise _DimensionError(
            "DimensionObservationUnavailable", "native circle geometry is invalid"
        )
    return radius, coordinates[0], coordinates[1]


def _descriptor(document: Any, dimension: Any) -> Dict[str, Any]:
    configuration = str(
        _com_value(
            _com_value(document, "ConfigurationManager"), "ActiveConfiguration"
        ).Name
    )
    value = float(dimension.GetSystemValue2(configuration)) * 1000
    return {
        "kind": "diameter",
        "unit": "millimeter",
        "value": value if math.isfinite(value) else None,
        "driven_state": int(_com_value(dimension, "DrivenState")),
        "read_only": bool(_com_value(dimension, "ReadOnly")),
        "configuration": configuration,
        "native_name": str(_com_value(dimension, "FullName")),
    }


def _equation_control(document: Any, native_name: str) -> Dict[str, Any]:
    """Observe assignment targets; names never substitute for native identity."""
    manager = _com_value(document, "GetEquationMgr")
    if manager is None:
        raise _DimensionError(
            "DimensionObservationUnavailable", "native equation manager is unavailable"
        )
    count = int(_com_value(manager, "GetCount"))
    if not 0 <= count <= _TRAVERSAL_LIMIT:
        raise _DimensionError(
            "DimensionObservationUnavailable",
            "native equation count is invalid or exceeds its limit",
        )
    # Native equations commonly omit the @model suffix of Dimension.FullName.
    aliases = {native_name.casefold(), "@".join(native_name.split("@")[:2]).casefold()}
    indices = []
    for index in range(count):
        equation = str(manager.Equation(index))
        match = _EQUATION_LHS.match(equation)
        if match is None:
            raise _DimensionError(
                "DimensionObservationUnavailable",
                "cannot safely identify a native equation assignment target",
            )
        if match.group(1).replace('""', '"').casefold() in aliases:
            # Disabled or other-configuration equations still express ownership;
            # the first slice does not overwrite any equation-managed parameter.
            indices.append(index)
    return {"controlled": bool(indices), "equation_indices": indices}


def _failure(result: Dict[str, Any], exc: Exception) -> Dict[str, Any]:
    result["error"] = (
        {"type": exc.code, "message": str(exc)}
        if isinstance(exc, _DimensionError)
        else _error(exc)
    )
    return result


def inspect_dimension_windows(
    *, app: Any, document: Any, sketch_feature: Any, dimension: Any
) -> Dict[str, Any]:
    """Read exact diameter state without activation, selection, edit or rebuild."""
    result: Dict[str, Any] = {"ok": False, "action": "dimension.inspect"}
    try:
        sketch = _owned_dimension(app, document, sketch_feature, dimension)
        _, x, y = _circle(sketch)
        descriptor = _descriptor(document, dimension)
        result.update(
            dimension=descriptor,
            geometry_verification=_circle_verification(
                sketch,
                (
                    descriptor["value"] / 2
                    if descriptor["value"] is not None
                    else math.nan
                ),
                x,
                y,
            ),
            constraint_status=int(_com_value(sketch, "GetConstrainedStatus")),
            editing=_com_value(_com_value(document, "SketchManager"), "ActiveSketch")
            is not None,
            equation_control=_equation_control(document, descriptor["native_name"]),
            design_table_controlled=bool(
                _com_value(dimension, "IsDesignTableDimension")
            ),
        )
        if descriptor["value"] is None or descriptor["value"] <= 0:
            raise _DimensionError(
                "DimensionObservationUnavailable", "native diameter value is invalid"
            )
        result["ok"] = True
        return result
    except Exception as exc:
        return _failure(result, exc)


def _measurement(document: Any) -> Optional[Dict[str, Any]]:
    observation = measure_part_windows(document=document)
    if observation["ok"]:
        return observation["metrics"]
    if observation["error"]["type"] == "NoSolidBodies":
        return None
    raise _DimensionError(
        "DownstreamObservationUnavailable", observation["error"]["message"]
    )


def set_dimension_windows(
    *, app: Any, document: Any, sketch_feature: Any, dimension: Any, value_mm: float
) -> Dict[str, Any]:
    """Set a registered diameter in the current configuration, then verify it."""
    result: Dict[str, Any] = {"ok": False, "action": "dimension.set"}
    if not _positive_length(value_mm):
        return _failure(
            result,
            _DimensionError(
                "InvalidArgument",
                "value_mm must be a positive finite, representable length",
            ),
        )
    result["value_mm"] = value_mm
    try:
        manager = _com_value(document, "SketchManager")
        if _com_value(manager, "ActiveSketch") is not None:
            raise _DimensionError(
                "SketchEditInProgress",
                "finish the existing sketch edit before setting a dimension",
            )
        before = inspect_dimension_windows(
            app=app,
            document=document,
            sketch_feature=sketch_feature,
            dimension=dimension,
        )
        if not before["ok"]:
            result.update(
                {
                    key: value
                    for key, value in before.items()
                    if key not in ("ok", "action")
                }
            )
            return result
        result.update(
            dimension=before["dimension"],
            before_value_mm=before["dimension"]["value"],
            equation_control=before["equation_control"],
            design_table_controlled=before["design_table_controlled"],
        )
        if (
            before["equation_control"]["controlled"]
            or before["design_table_controlled"]
        ):
            raise _DimensionError(
                "DimensionExternallyControlled",
                "do not overwrite an equation or design-table controlled diameter",
            )
        if (
            before["dimension"]["driven_state"] != _DRIVING
            or before["dimension"]["read_only"]
        ):
            raise _DimensionError(
                "DimensionNotDriving", "do not override a driven or read-only dimension"
            )
        if not before["geometry_verification"]["passed"]:
            raise _DimensionError(
                "DimensionVerificationFailed",
                "native diameter and source circle do not agree before editing",
            )
        center = before["geometry_verification"]["actual_center_mm"]
        x, y = center["x"], center["y"]
        measurement_before = _measurement(document)
        result["downstream"] = {
            "applicable": measurement_before is not None,
            "measurement_before": measurement_before,
            "measurement_after": None,
        }
        status = int(
            dimension.SetSystemValue3(
                value_mm / 1000, _CURRENT_CONFIGURATION, _variant("empty", None)
            )
        )
        result["native_status"] = status
        if status != 0:
            raise _DimensionError(
                "DimensionSetFailed", "SOLIDWORKS rejected the driving diameter value"
            )
        result["rebuilt"] = bool(_com_value(document, "EditRebuild3"))
        result["needs_rebuild"] = int(
            _com_value(_com_value(document, "Extension"), "NeedsRebuild2")
        )
        result["diagnostics"] = _diagnose_features(document, 500)
        # Re-resolve ownership after the rebuild; COM success is not evidence of
        # live, correctly driven geometry or unchanged configuration scope.
        sketch = _owned_dimension(app, document, sketch_feature, dimension)
        descriptor = _descriptor(document, dimension)
        result.update(
            dimension=descriptor,
            geometry_verification=_circle_verification(sketch, value_mm / 2, x, y),
            constraint_status=int(_com_value(sketch, "GetConstrainedStatus")),
            editing=_com_value(manager, "ActiveSketch") is not None,
        )
        measurement_after = _measurement(document)
        result["downstream"].update(
            applicable=measurement_before is not None or measurement_after is not None,
            measurement_after=measurement_after,
        )
        if (
            not result["rebuilt"]
            or result["needs_rebuild"] != 0
            or not result["diagnostics"]["healthy"]
            or result["diagnostics"]["truncated"]
        ):
            raise _DimensionError(
                "ModelInvalid",
                "updated diameter did not pass complete rebuild diagnostics",
            )
        if (
            descriptor["value"] is None
            or not math.isclose(
                descriptor["value"], value_mm, rel_tol=0, abs_tol=_TOLERANCE_MM
            )
            or descriptor["configuration"] != before["dimension"]["configuration"]
            or descriptor["driven_state"] != _DRIVING
            or descriptor["read_only"]
            or not result["geometry_verification"]["passed"]
            or result["editing"]
            or (measurement_before is not None and measurement_after is None)
        ):
            raise _DimensionError(
                "DimensionVerificationFailed",
                "final diameter, configuration, circle geometry or downstream evidence did not match",
            )
        result["ok"] = True
        return result
    except Exception as exc:
        return _failure(result, exc)


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
