"""Narrow single-edge constant-radius creation on the resident COM STA.

No rollback, persistence, activation or automatic retry. Partial features remain
available to the caller even when native verification or cleanup fails.
"""

import math

from .native_trace import native_call
from .windows import _com_value, _error
from .windows_documents import _diagnose_features
from .windows_edge_observation import EdgeBinding, observe_part_edges_with_handles
from .windows_entity_observation import _identical, _single_body
from .windows_entity_references import capture_verified_reference
from .windows_feature_depth import _running_command
from .windows_feature_inspection import _state, _same

# SW2025 swconst: swFmFillet, swConstRadiusFillet, swFeatureFilletCircular.
# Calibrated against the installed official type library on Windows and Wine.
_FILLET, _CONSTANT_RADIUS, _CIRCULAR = 1, 0, 0


def _check(condition, message):
    if not condition:
        raise RuntimeError(message)


def _null_dispatch():
    import pythoncom
    from win32com.client import VARIANT
    return VARIANT(pythoncom.VT_DISPATCH, None)


def _volume(document):
    body = _single_body(document)
    value = native_call("feature-fillet", "Body.GetMassProperties", lambda: body.GetMassProperties(1.0))[3]
    _check(type(value) in (int, float) and math.isfinite(value) and value > 0,
           "solid volume must be finite and positive")
    converted = value * 1e9
    _check(math.isfinite(converted) and converted > 0, "converted solid volume is invalid")
    return converted


def create_edge_fillet_windows_with_handle(*, app, document, binding: EdgeBinding, radius_mm):
    result = dict(ok=False, action="feature.fillet", radius_mm=radius_mm,
                  mutation=dict(attempted=False, creation_returned=False, may_have_changed=False),
                  cleanup_errors=[])
    feature = selection = None
    before = None
    owned_selection = False

    def call(name, function):
        return native_call("feature-fillet", name, function)

    def cleanup(name, function):
        try:
            call(name, function)
        except Exception as exc:
            result["cleanup_errors"].append(dict(stage=name, error=str(exc)))

    def settings(data):
        radius = _com_value(data, "DefaultRadius")
        _check(type(radius) in (int, float) and math.isfinite(radius) and
               math.isclose(radius, radius_mm / 1000, rel_tol=0, abs_tol=1e-12),
               "native fillet radius differs from requested radius")
        profile = _com_value(data, "ConicTypeForCrossSectionProfile")
        _check(type(profile) is int and profile == _CIRCULAR and
               _com_value(data, "PropagateToTangentFaces") is False,
               "native fillet profile or tangent propagation differs")
        return radius * 1000

    try:
        _check(type(radius_mm) in (int, float) and math.isfinite(radius_mm) and
               radius_mm > 2e-6 and math.ulp(radius_mm) <= 1e-6 and
               math.isfinite(radius_mm / 1000) and radius_mm / 1000 > 0,
               "radius_mm must be finite, greater than 2e-6 mm and numerically resolvable")
        _check(isinstance(binding, EdgeBinding), "an exact edge binding is required")
        _check(type(_com_value(document, "GetType")) is int and _com_value(document, "GetType") == 1,
               "fillet requires a part")
        before, edit_before, foreground_before = _state(app, document)
        _check(_same(app, document, foreground_before) and not before["editing"],
               "fillet requires the active part outside sketch edit")
        _check(_com_value(document, "IsOpenedReadOnly") is False and
               _com_value(document, "IsOpenedViewOnly") is False, "part is not writable")
        names = _com_value(document, "GetConfigurationNames")
        _check(type(_com_value(document, "GetConfigurationCount")) is int and
               _com_value(document, "GetConfigurationCount") == 1 and
               isinstance(names, (tuple, list)) and list(names) == [before["configuration"]],
               "fillet requires exactly one configuration")
        _check(not _running_command(app)["ui_active"], "native command is in progress")
        selection = _com_value(document, "SelectionManager")
        initial_count = selection.GetSelectedObjectCount2(-1)
        _check(type(initial_count) is int and initial_count == 0, "existing selection is not owned or unreadable")
        observed, live = observe_part_edges_with_handles(app, document)
        _check(observed["ok"], "complete live edge observation failed: " + str(observed.get("error")))
        matches = [item for item in live if _identical(app, item.edge, binding.edge)]
        _check(len(matches) == 1 and matches[0].reference == binding.reference and
               _identical(app, matches[0].body, binding.body), "edge identity or owning solid changed")
        extension = _com_value(document, "Extension")
        _check(capture_verified_reference(app, extension, binding.edge) == binding.reference,
               "target persistent reference changed")
        result["before_volume_mm3"] = _volume(document)
        data = _com_value(selection, "CreateSelectData")
        data.Mark = 1
        owned_selection = True
        _check(call("Edge.Select4", lambda: binding.edge.Select4(False, data)) is True,
               "exact edge selection failed")
        selected_count = selection.GetSelectedObjectCount2(-1)
        _check(type(selected_count) is int and selected_count == 1 and
               _identical(app, selection.GetSelectedObject6(1, 1), binding.edge),
               "marked selection does not identify exact edge")
        manager = _com_value(document, "FeatureManager")
        definition = call("CreateDefinition", lambda: manager.CreateDefinition(_FILLET))
        _check(definition is not None, "fillet definition is absent")
        _check(call("Initialize", lambda: definition.Initialize(_CONSTANT_RADIUS)) is True,
               "constant-radius initialization failed")
        for name, value in (("ConicTypeForCrossSectionProfile", _CIRCULAR),
                            ("DefaultRadius", radius_mm / 1000), ("PropagateToTangentFaces", False)):
            call("set." + name, lambda n=name, v=value: setattr(definition, n, v))
        settings(definition)
        result["mutation"].update(attempted=True, may_have_changed=True)
        feature = call("CreateFeature", lambda: manager.CreateFeature(definition))
        result["mutation"]["creation_returned"] = feature is not None
        _check(feature is not None, "fillet creation returned no feature; do not retry")
        result["feature"] = dict(name=_com_value(feature, "Name"), type=_com_value(feature, "GetTypeName2"))
        _check(result["feature"]["type"] == "Fillet", "created feature is not a fillet")
        document.ClearSelection2(True)
        readback = call("GetDefinition", lambda: _com_value(feature, "GetDefinition"))
        _check(readback is not None, "created definition is absent")
        try:
            _check(call("AccessSelections", lambda: readback.AccessSelections(document, _null_dispatch())) is True,
                   "created selection access was refused")
            targets = _com_value(readback, "Edges")
            _check(isinstance(targets, (tuple, list)) and len(targets) == 1 and
                   capture_verified_reference(app, extension, targets[0]) == binding.reference,
                   "created fillet targets another edge")
            actual_radius_mm = settings(readback)
        finally:
            cleanup("ReleaseSelectionAccess", lambda: _com_value(readback, "ReleaseSelectionAccess"))
        _check(not result["cleanup_errors"], "selection access release failed")
        document.ClearSelection2(True)
        _check(call("EditRebuild3", lambda: _com_value(document, "EditRebuild3")) is True, "rebuild failed")
        result["rebuilt"] = True
        result["diagnostics"] = call("diagnose", lambda: _diagnose_features(document, 200))
        _check(result["diagnostics"]["healthy"] is True and result["diagnostics"]["truncated"] is False,
               "rebuild diagnostics are incomplete or unhealthy")
        result["after_volume_mm3"] = _volume(document)
        _check(not math.isclose(result["before_volume_mm3"], result["after_volume_mm3"], rel_tol=1e-12, abs_tol=1e-9),
               "fillet did not measurably change solid volume")
        result.update(bodies=1, verification=dict(passed=True, radius_mm=actual_radius_mm, edge_count=1,
                                                profile="circular", tangent_propagation=False))
    except Exception as exc:
        result["error"] = _error(exc)
    finally:
        if owned_selection:
            cleanup("ClearSelection2", lambda: document.ClearSelection2(True))
        if before is not None:
            def verify_state():
                after, edit_after, foreground_after = _state(app, document)
                if after["update_stamp"] != before["update_stamp"]:
                    result["mutation"]["may_have_changed"] = True
                _check(after["configuration"] == before["configuration"] and
                       _same(app, edit_before, edit_after) and _same(app, foreground_before, foreground_after),
                       "configuration, foreground or edit state was not restored")
                if owned_selection:
                    count = selection.GetSelectedObjectCount2(-1)
                    _check(type(count) is int and count == 0, "owned selection was not cleared")
            cleanup("verify-restoration", verify_state)
    if result["cleanup_errors"] and "error" not in result:
        result["error"] = dict(type="FilletRestorationFailed", message="native cleanup or restoration failed")
    result["ok"] = "error" not in result
    return result, feature
