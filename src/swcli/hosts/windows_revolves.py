"""Bounded, calibrated native Windows revolve on the owning COM STA.

Internal calibration uses the same candidate without creating a public bypass.
No retries, rollback, save, implicit sketch edit or preference changes.
"""

import math

from ..revolve_geometry import validate_revolve_intent, cylinder_expectation, verify_cylinder_metrics
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_documents import _diagnose_features
from .windows_feature_depth import _running_command
from .windows_feature_inspection import _state, _same, _FeatureError
from .windows_feature_selections import _null_dispatch
from .windows_measurements import measure_part_windows
from .windows_rectangle_profiles import observe_rectangle_profile, _point_mm
from .windows_sketches import _unabsorbed_profile



# Official SW2025 SP5 TLB + native save/reopen calibration:
# head 32812cb, run 42262911836, artifact 13526809695,
# sha256:69aca5b8480ed3f14547ba36e85a23730b042068c32854b6e87541fa1eeb3ac1.
_CALIBRATED_CONSTANTS = {"swEndCondBlind": 0, "swThinWallOneDirection": 0,
                         "swRevolveTypeOneDirection": 0, "swSelSKETCHSEGS": 10}
_CALIBRATED_FRAMES = (
    (1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0),
    (1,0,0,0,0,1,0,-1,0,0,0,0,1,0,0,0),
    (0,0,1,0,1,0,-1,0,0,0,0,0,1,0,0,0),
)


def _native_constants(app):
    """Exact tested native Windows revision only; unknown detection closes."""
    import ctypes
    import sys
    if sys.platform != "win32":
        return None
    try:
        library = ctypes.WinDLL("ntdll")
        if getattr(library, "wine_get_version", None) is not None:
            return None
        if _com_value(app, "RevisionNumber") != "33.5.0":
            return None
    except (AttributeError, OSError):
        return None
    return dict(_CALIBRATED_CONSTANTS)


def _require(condition, code, message):
    if not condition:
        raise _FeatureError(code, message)


def _failure(result, exc):
    result["error"] = (dict(type=exc.code, message=str(exc))
                       if hasattr(exc, "code") else _error(exc))


def observe_revolve_definition(app, document, feature, axis, constants, evidence=None):
    """Owned access/release; exact native axis identity and full definition readback."""
    result = evidence if evidence is not None else {}
    result["cleanup_errors"] = []
    data = _com_value(feature, "GetDefinition")
    _require(data is not None, "RevolveDefinitionUnavailable", "native revolve definition is absent")
    try:
        _require(data.AccessSelections(document, _null_dispatch()) is True,
                 "RevolveSelectionAccessFailed", "native revolve selection access refused")
        result.update(angle_rad=data.GetRevolutionAngle(True),
                      reverse=_com_value(data, "ReverseDirection"),
                      kind=_com_value(data, "Type"), boss=_com_value(data, "IsBossFeature"),
                      thin=_com_value(data, "IsThinFeature"), merge=_com_value(data, "Merge"),
                      axis_type=_com_value(data, "GetAxisType"),
                      contour_count=_com_value(data, "GetContoursCount"))
        _require(type(result["angle_rad"]) in (int, float) and math.isfinite(result["angle_rad"]) and
                 math.isclose(result["angle_rad"], 2*math.pi, rel_tol=0, abs_tol=1e-12) and
                 result["reverse"] is False and result["boss"] is True and
                 result["thin"] is False and result["merge"] is True and
                 type(result["kind"]) is int and result["kind"] == constants["swRevolveTypeOneDirection"] and
                 type(result["axis_type"]) is int and result["axis_type"] == constants["swSelSKETCHSEGS"] and
                 type(result["contour_count"]) is int and result["contour_count"] == 0,
                 "RevolveDefinitionMismatch", "native solid revolve settings differ from explicit request")
        native_axis = _com_value(data, "Axis")
        _require(_same(app, native_axis, axis), "RevolveAxisMismatch", "native axis is not the exact selected profile edge")
        result["axis_matches"] = True
    finally:
        import sys
        primary = sys.exc_info()[1]
        # AccessSelections can throw after partial acquisition. Always release,
        # preserving the primary exception if cleanup also fails.
        try:
            _com_value(data, "ReleaseSelectionAccess")
        except Exception as exc:
            result["cleanup_errors"].append(dict(stage="ReleaseSelectionAccess", error=str(exc)))
            if primary is None:
                raise
    _require(not result["cleanup_errors"], "RevolveRestorationFailed", "native selection release failed")
    return result


def create_revolve_windows_with_handle(*, app, document, sketch_feature,
        expected_profile_mm, axis_mm, angle_deg):
    """Use only the version/platform and profile proven by native calibration."""
    validate_revolve_intent(expected_profile_mm, axis_mm, angle_deg)
    constants = _native_constants(app)
    if constants is None:
        return (dict(ok=False, action="feature.revolve",
            mutation=dict(attempted=False, creation_returned=False, may_have_changed=False),
            cleanup_errors=[], error=dict(type="RevolveNotCalibrated",
            message="bounded revolve is calibrated only for native Windows SOLIDWORKS revision 33.5.0")), None)
    return _calibrate_revolve_windows_with_handle(
        app=app, document=document, sketch_feature=sketch_feature,
        expected_profile_mm=expected_profile_mm, axis_mm=axis_mm, angle_deg=angle_deg,
        constants=constants)


def _calibrate_revolve_windows_with_handle(*, app, document, sketch_feature,
        expected_profile_mm, axis_mm, angle_deg, constants):
    """Shared private creation primitive; constants are official and calibrated."""
    result = dict(ok=False, action="feature.revolve", expected_profile_mm=list(expected_profile_mm),
                  axis_mm=list(axis_mm), angle_deg=angle_deg,
                  mutation=dict(attempted=False, creation_returned=False, may_have_changed=False), cleanup_errors=[])
    feature = before = None
    selected = False

    def call(name, function):
        return native_call("revolve", name, function)

    def cleanup(name, function):
        try:
            call(name, function)
        except Exception as exc:
            result["cleanup_errors"].append(dict(stage=name, error=str(exc)))

    try:
        validate_revolve_intent(expected_profile_mm, axis_mm, angle_deg)
        _require(type(_com_value(document, "GetType")) is int and _com_value(document, "GetType") == 1,
                 "UnsupportedDocumentType", "revolve requires a part")
        before, edit, foreground = _state(app, document)
        _require(not before["editing"] and _same(app, document, foreground),
                 "DocumentNotActive", "exact part must be active outside sketch edit")
        _require(_com_value(document, "IsOpenedReadOnly") is False and
                 _com_value(document, "IsOpenedViewOnly") is False,
                 "DocumentReadOnly", "revolve requires a writable part")
        names = _com_value(document, "GetConfigurationNames")
        _require(type(_com_value(document, "GetConfigurationCount")) is int and
                 _com_value(document, "GetConfigurationCount") == 1 and
                 isinstance(names, (list, tuple)) and list(names) == [before["configuration"]],
                 "UnsupportedRevolveConfiguration", "exactly one configuration is required")
        _require(not _running_command(app)["ui_active"], "NativeCommandInProgress", "native command is active")
        selection = _com_value(document, "SelectionManager")
        count = selection.GetSelectedObjectCount2(-1)
        _require(type(count) is int and count == 0, "SelectionNotEmpty", "existing selection is not owned")
        bodies = document.GetBodies2(-1, False)
        _require(bodies is None or isinstance(bodies, (list, tuple)) and len(bodies) == 0,
                 "UnsupportedRevolveBodyScope", "first revolve requires no existing bodies, including surfaces")
        _require(_unabsorbed_profile(app, document, sketch_feature) is not None,
                 "SketchUnavailable", "exact unabsorbed sketch is unavailable")
        sketch = _com_value(sketch_feature, "GetSpecificFeature2")
        _require(_com_value(sketch, "Is3D") is False, "UnsupportedRevolveProfile", "2D profile is required")
        profile = observe_rectangle_profile(sketch)
        _require(all(math.isclose(actual, expected, rel_tol=0, abs_tol=1e-6)
                     for actual, expected in zip(profile.bounds_mm, expected_profile_mm)),
                 "RevolveProfileConflict", "complete live rectangle bounds differ from expected_profile_mm")
        _require(profile.construction_segment_count == 2 and profile.native_segment_count == 6,
                 "UnsupportedRevolveProfile", "only the existing center rectangle with two construction diagonals is a candidate")
        axis = profile.left_edge
        observed_axis = [_point_mm(_com_value(axis, name)) for name in ("GetStartPoint2", "GetEndPoint2")]
        wanted = [(0, axis_mm[1], 0), (0, axis_mm[3], 0)]
        _require(all(any(all(math.isclose(p[i], q[i], rel_tol=0, abs_tol=1e-6) for i in range(3))
                            for q in wanted) for p in observed_axis),
                 "RevolveAxisMismatch", "axis endpoints do not match explicit edge intent")
        transform = list(_com_value(_com_value(sketch, "ModelToSketchTransform"), "ArrayData"))
        _require(len(transform) == 16 and any(all(math.isclose(a, b, rel_tol=0, abs_tol=1e-12)
                     for a, b in zip(transform, frame)) for frame in _CALIBRATED_FRAMES),
                 "UnsupportedRevolvePlane", "only the three calibrated origin-plane frames are supported")
        expected = cylinder_expectation(expected_profile_mm, transform)
        result.update(model_to_sketch_transform=transform, expected_metrics=expected)
        ready, ready_edit, ready_foreground = _state(app, document)
        _require(ready == before and _same(app, edit, ready_edit) and _same(app, foreground, ready_foreground),
                 "DocumentUpdateConflict", "native state changed during preflight")
        selected = True
        _require(call("Sketch.Select2", lambda: sketch_feature.Select2(False, 0)) is True,
                 "SketchSelectionFailed", "exact profile selection failed")
        data = _com_value(selection, "CreateSelectData")
        data.Mark = 4
        _require(call("Axis.Select4", lambda: axis.Select4(True, data)) is True,
                 "AxisSelectionFailed", "exact axis selection failed")
        _require(selection.GetSelectedObjectCount2(-1) == 2 and
                 _same(app, selection.GetSelectedObject6(1, 4), axis),
                 "RevolveAxisMismatch", "marked selection does not identify exact axis")
        result["mutation"].update(attempted=True, may_have_changed=True)
        feature = call("FeatureRevolve2", lambda: _com_value(document, "FeatureManager").FeatureRevolve2(
            True, True, False, False, False, False,
            constants["swEndCondBlind"], constants["swEndCondBlind"], 2*math.pi, 0.0,
            False, False, 0.0, 0.0, constants["swThinWallOneDirection"], 0.0, 0.0,
            True, False, False))
        result["mutation"]["creation_returned"] = feature is not None
        _require(feature is not None, "RevolveCreationFailed", "native creation returned no feature; do not retry")
        name = _com_value(feature, "Name")
        kind = _com_value(feature, "GetTypeName2")
        _require(isinstance(name, str) and bool(name.strip()) and isinstance(kind, str) and bool(kind.strip()),
                 "RevolveFeatureMetadataUnavailable", "created feature metadata is unreadable; retain its exact handle")
        result["feature"] = dict(name=name, type=kind)
        _require(kind == "Revolution", "RevolveDefinitionMismatch", "created feature is not a native revolution")
        document.ClearSelection2(True)
        result["definition"] = {}
        call("read-definition", lambda: observe_revolve_definition(app, document, feature, axis, constants, result["definition"]))
        _require(call("EditRebuild3", lambda: _com_value(document, "EditRebuild3")) is True,
                 "ModelInvalid", "revolve rebuild failed")
        _require(len(tuple(document.GetBodies2(-1, False) or ())) == 1,
                 "RevolveGeometryMismatch", "revolve must leave exactly one body of any kind")
        result["diagnostics"] = _diagnose_features(document, 500)
        _require(result["diagnostics"]["healthy"] is True and result["diagnostics"]["truncated"] is False,
                 "ModelInvalid", "revolve diagnostics are incomplete or unhealthy")
        measured = measure_part_windows(document=document)
        _require(measured["ok"], "MeasurementUnavailable", "native mass properties unavailable")
        result["metrics"] = measured["metrics"]
        verify_cylinder_metrics(result["metrics"], expected)
        result["verified"] = True
    except Exception as exc:
        _failure(result, exc)
    finally:
        if selected:
            cleanup("ClearSelection2", lambda: document.ClearSelection2(True))
        if before is not None:
            def restored():
                after, after_edit, after_foreground = _state(app, document)
                if after["update_stamp"] != before["update_stamp"]:
                    result["mutation"]["may_have_changed"] = True
                _require(after["configuration"] == before["configuration"] and
                         _same(app, edit, after_edit) and _same(app, foreground, after_foreground),
                         "RevolveRestorationFailed", "native configuration/edit/foreground changed")
                if selected:
                    _require(selection.GetSelectedObjectCount2(-1) == 0,
                             "RevolveRestorationFailed", "owned selections remain")
            cleanup("verify-restoration", restored)
    if result["cleanup_errors"] and "error" not in result:
        result["error"] = dict(type="RevolveRestorationFailed", message="native cleanup failed")
    result["ok"] = "error" not in result
    return result, feature
