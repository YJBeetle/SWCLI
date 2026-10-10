"""Internal owned selection-access observation for future depth writes.

This is not a public read-only operation: access/release may advance the native
update stamp even when model geometry and modified state are restored.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

from .native_trace import native_call
from .windows import _com_value, _error
from .windows_documents import _diagnose_features
from .windows_feature_depth_profiles import (
    prepare_profiled_extrusion_depth_edit_windows_with_definition,
)
from .windows_feature_inspection import _FeatureError, _boolean, _integer, _same, _state
from .windows_measurements import measure_part_windows


def _null_dispatch():
    import pythoncom
    from win32com.client import VARIANT

    return VARIANT(pythoncom.VT_DISPATCH, None)


def _direction(definition: Any) -> Dict[str, Any]:
    import pythoncom
    from win32com.client import VARIANT

    # GetDirectionReference expects IDispatch**; VARIANT* is rejected by native
    # SW2025. Types start at an impossible sentinel, not the observed -1 marker.
    refs = [VARIANT(pythoncom.VT_BYREF | pythoncom.VT_DISPATCH, None) for _ in range(2)]
    types = [
        VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, -2147483648) for _ in range(2)
    ]
    count = _integer(
        native_call(
            "feature-selection-scope",
            "ExtrudeFeatureData.GetDirectionReference",
            lambda: definition.GetDirectionReference(
                refs[0], types[0], refs[1], types[1]
            ),
        ),
        "direction reference count",
    )
    values = [_integer(value.value, "direction reference type") for value in types]
    if count in (1, 2):
        raise _FeatureError(
            "UnsupportedDepthDirection",
            "explicit extrusion direction references are outside the first depth slice",
        )
    # A negative count ALONE proves nothing. Native known-default fixtures write
    # all three -1 values and two null objects; a staged plane positive control
    # instead produces 1, (4,-1), (non-null,null), then returns to this marker on
    # release. Unwritten/contradictory outputs fail rather than becoming absence.
    if (
        count != -1
        or values != [-1, -1]
        or any(value.value is not None for value in refs)
    ):
        raise _FeatureError(
            "FeatureSelectionScopeUnavailable",
            "native direction reference outputs are unknown or inconsistent",
        )
    return {
        "state": "native-default-marker",
        "native_count": count,
        "native_types": values,
    }


def _collection(value: Any, name: str) -> tuple:
    if value is None:
        # Native body arrays can be null when empty. Feature-scope arrays have
        # a separately checked count; rollback arrays permit empty only for a
        # boss (its earlier final-body guard still requires one final solid).
        return ()
    if (
        not isinstance(value, (list, tuple))
        or len(value) > 1000
        or any(item is None for item in value)
    ):
        raise _FeatureError(
            "FeatureSelectionScopeUnavailable", f"native {name} is invalid"
        )
    return tuple(value)


def _selection_scope(
    app: Any, document: Any, definition: Any, kind: str
) -> Dict[str, Any]:
    contours = _integer(
        _com_value(definition, "GetContoursCount"), "selected contour count"
    )
    if contours < 0:
        raise _FeatureError(
            "FeatureSelectionScopeUnavailable", "selected contours are not observable"
        )
    if contours:
        raise _FeatureError(
            "UnsupportedDepthContours",
            "selected sketch contours/regions are outside the first depth slice",
        )
    direction = _direction(definition)
    feature_scope = _boolean(_com_value(definition, "FeatureScope"), "FeatureScope")
    auto_select = _boolean(_com_value(definition, "AutoSelect"), "AutoSelect")
    count = _integer(
        _com_value(definition, "GetFeatureScopeBodiesCount"), "feature scope body count"
    )
    bodies = _collection(
        _com_value(definition, "FeatureScopeBodies"), "feature scope bodies"
    )
    if count < 0 or count != len(bodies):
        raise _FeatureError(
            "FeatureSelectionScopeUnavailable", "native scope body count/array disagree"
        )
    rollback_bodies = _collection(
        native_call(
            "feature-selection-scope",
            "PartDoc.GetBodies2",
            lambda: document.GetBodies2(-1, False),
        ),
        "rollback part bodies",
    )
    if len(rollback_bodies) > 1 or any(
        _integer(_com_value(body, "GetType"), "rollback body type") != 0
        or _boolean(_com_value(body, "IsSheetMetal"), "rollback IsSheetMetal")
        for body in rollback_bodies
    ):
        raise _FeatureError(
            "UnsupportedDepthBodyScope",
            "rollback scope requires at most one non-sheet-metal solid and no surfaces",
        )
    if kind == "boss-extrude":
        if not _boolean(_com_value(definition, "Merge"), "Merge") or count:
            raise _FeatureError(
                "UnsupportedDepthBodyScope",
                "the first depth slice requires a merged boss with no explicit body selections",
            )
        if _boolean(_com_value(definition, "LinkToThickness"), "LinkToThickness"):
            raise _FeatureError(
                "UnsupportedDepthDefinition",
                "a thickness-linked boss is outside the first depth slice",
            )
        scope = "merged-boss"
    elif kind == "cut-extrude":
        if len(rollback_bodies) != 1:
            raise _FeatureError(
                "UnsupportedDepthBodyScope", "a cut requires one live rollback solid"
            )
        if _boolean(_com_value(definition, "NormalCut"), "NormalCut") or _boolean(
            _com_value(definition, "FlipSideToCut"), "FlipSideToCut"
        ):
            raise _FeatureError(
                "UnsupportedDepthDefinition",
                "normal/flipped-side cuts are outside the first depth slice",
            )
        if feature_scope:
            if count != 1 or not _same(app, bodies[0], rollback_bodies[0]):
                raise _FeatureError(
                    "FeatureSelectionScopeUnavailable",
                    "the selected cut body is not the sole live rollback solid",
                )
            scope = "single-rollback-solid"
        else:
            if count:
                raise _FeatureError(
                    "FeatureSelectionScopeUnavailable",
                    "all-body cut unexpectedly contains selected bodies",
                )
            scope = "all-rollback-solids"
    else:
        raise _FeatureError("UnsupportedDepthDefinition", "unsupported extrusion kind")
    return {
        "selected_contour_count": contours,
        "direction": direction,
        "feature_scope": feature_scope,
        "auto_select": auto_select,
        "selected_body_count": count,
        "rollback_solid_body_count": len(rollback_bodies),
        "affected_scope": scope,
    }


def _measurement(document: Any) -> Dict[str, Any]:
    value = native_call(
        "feature-selection-state",
        "measure_part_windows",
        lambda: measure_part_windows(document=document),
    )
    if not value["ok"]:
        raise _FeatureError(
            "FeatureSelectionScopeUnavailable", value["error"]["message"]
        )
    return value["metrics"]


def _healthy(document: Any) -> Dict[str, Any]:
    needs = _integer(
        _com_value(_com_value(document, "Extension"), "NeedsRebuild2"), "NeedsRebuild2"
    )
    diagnostics = native_call(
        "feature-selection-state",
        "diagnose_features",
        lambda: _diagnose_features(document, 500),
    )
    if needs != 0 or not diagnostics["healthy"] or diagnostics["truncated"]:
        raise _FeatureError(
            "ModelInvalid",
            "selection observation requires complete, healthy rebuild diagnostics",
        )
    return diagnostics


def _same_geometry(before: Dict[str, Any], after: Dict[str, Any]) -> bool:
    return before["solid_body_count"] == after["solid_body_count"] and all(
        math.isclose(first, second, rel_tol=1e-12, abs_tol=1e-6)
        for first, second in (
            (before["volume_mm3"], after["volume_mm3"]),
            (before["surface_area_mm2"], after["surface_area_mm2"]),
            *(
                (before["centroid_mm"][axis], after["centroid_mm"][axis])
                for axis in "xyz"
            ),
        )
    )


def _failure(result: Dict[str, Any], exc: Exception, warning: str = "") -> None:
    error = (
        {"type": exc.code, "message": str(exc)}
        if isinstance(exc, _FeatureError)
        else _error(exc)
    )
    if "error" in result:
        result.setdefault("warnings", []).append(
            {
                "code": warning or "feature-selection-state-check-failed",
                "message": str(exc),
            }
        )
    else:
        result["error"] = error


def observe_extrusion_selection_scope_windows_with_definition(
    *, app: Any, document: Any, feature: Any
) -> Tuple[Dict[str, Any], Optional[Any]]:
    """Own access/release, prove restored model state and return fresh data.

    Caller must already activate the exact part. Does not select a GUI entity,
    set feature data, rebuild, save or retry. Successful access may advance the
    stamp: that change is reported rather than misrepresented as a pure read.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "action": "feature.selection-scope-preflight",
    }
    attempted = False
    definition = fresh = None
    before = snapshot = measured = None
    result["selection_access"] = {
        "attempted": False,
        "acquired": False,
        "release_attempted": False,
        "released": False,
        "state_restored": False,
    }
    lifecycle = result["selection_access"]
    try:
        before, definition = (
            prepare_profiled_extrusion_depth_edit_windows_with_definition(
                app=app, document=document, feature=feature
            )
        )
        if not before["ok"]:
            raise _FeatureError(before["error"]["type"], before["error"]["message"])
        if definition is None:
            raise _FeatureError(
                "FeatureSelectionScopeUnavailable", "native definition is missing"
            )
        snapshot, edit, foreground = _state(app, document)
        if not _same(app, foreground, document):
            raise _FeatureError(
                "DocumentNotActive",
                "selection access requires the exact selected part to be active",
            )
        measured = _measurement(document)
        _healthy(document)
        result.update(
            feature=before["feature"],
            definition=before["definition"],
            profile=before["profile"],
            measurement_before=measured,
        )
        result["observation"] = {"before": snapshot}
        # Record attempt before invoking: COM can throw after a partial access.
        attempted = lifecycle["attempted"] = True
        acquired = native_call(
            "feature-selection-access",
            "ExtrudeFeatureData.AccessSelections",
            lambda: definition.AccessSelections(document, _null_dispatch()),
        )
        lifecycle["acquired"] = _boolean(acquired, "AccessSelections")
        if not acquired:
            raise _FeatureError(
                "FeatureSelectionAccessFailed",
                "SOLIDWORKS did not grant selection access",
            )
        result["scope"] = _selection_scope(
            app, document, definition, before["feature"]["kind"]
        )
    except Exception as exc:
        _failure(result, exc)
    finally:
        if attempted:
            lifecycle["release_attempted"] = True
            try:
                native_call(
                    "feature-selection-release",
                    "ExtrudeFeatureData.ReleaseSelectionAccess",
                    lambda: definition.ReleaseSelectionAccess(),
                )
                lifecycle["released"] = True
            except Exception as exc:
                _failure(result, exc, "feature-selection-release-failed")
        if attempted and snapshot is not None:
            try:
                after, edit_after, foreground_after = _state(app, document)
                result["observation"].update(
                    after=after,
                    update_stamp_changed=snapshot["update_stamp"]
                    != after["update_stamp"],
                )
                keys = ("configuration", "modified", "editing", "foreground_present")
                if (
                    any(snapshot[key] != after[key] for key in keys)
                    or not _same(app, edit, edit_after)
                    or not _same(app, foreground, foreground_after)
                ):
                    raise _FeatureError(
                        "FeatureSelectionStateNotRestored",
                        "native configuration, modified/edit or foreground state was not restored",
                    )
                post, fresh = (
                    prepare_profiled_extrusion_depth_edit_windows_with_definition(
                        app=app, document=document, feature=feature
                    )
                )
                if not post["ok"]:
                    raise _FeatureError(
                        "FeatureSelectionStateNotRestored", post["error"]["message"]
                    )
                if fresh is None:
                    raise _FeatureError(
                        "FeatureSelectionStateNotRestored",
                        "fresh native definition is missing after release",
                    )
                if any(
                    before[key] != post[key]
                    for key in ("feature", "definition", "controls", "profile", "body")
                ):
                    raise _FeatureError(
                        "FeatureSelectionStateNotRestored",
                        "native definition, controls, profile or body was not restored",
                    )
                result["diagnostics"] = _healthy(document)
                result["direction_after"] = _direction(fresh)
                result["measurement_after"] = _measurement(document)
                if not _same_geometry(measured, result["measurement_after"]):
                    raise _FeatureError(
                        "FeatureSelectionStateNotRestored",
                        "independent model geometry changed during selection observation",
                    )
                lifecycle["state_restored"] = lifecycle["released"]
            except Exception as exc:
                _failure(result, exc, "feature-selection-restoration-failed")
    if "error" in result:
        return result, None
    result["ok"] = True
    return result, fresh
