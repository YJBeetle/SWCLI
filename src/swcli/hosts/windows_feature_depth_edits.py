"""Internal guarded blind-depth editing on the owning COM STA.

No public protocol wiring yet. Selection scope is observed and released before
staging fresh feature data; failed mutations are neither retried nor rolled back.
"""

from __future__ import annotations

import math
from typing import Any, Dict

from .native_trace import native_call
from .windows import _com_value
from .windows_feature_depth_profiles import (
    prepare_profiled_extrusion_depth_edit_windows_with_definition,
)
from .windows_feature_inspection import _FeatureError, _boolean, _same, _state
from .windows_feature_selections import (
    _failure,
    _measurement,
    _null_dispatch,
    _same_geometry,
    observe_extrusion_selection_scope_windows_with_definition,
)

_DEPTH_TOLERANCE_MM = 1e-6
_SNAPSHOT_KEYS = ("feature", "definition", "controls", "profile", "body")


def _empty_variant():
    import pythoncom
    from win32com.client import VARIANT

    return VARIANT(pythoncom.VT_EMPTY, None)


def _depth(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _FeatureError("InvalidArgument", "depth_mm must be numeric")
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise _FeatureError("InvalidArgument", "depth_mm is unrepresentable") from None
    if (
        not math.isfinite(value)
        or value <= 2 * _DEPTH_TOLERANCE_MM
        or math.ulp(value) > _DEPTH_TOLERANCE_MM
        or value / 1000 <= 0
    ):
        raise _FeatureError(
            "InvalidArgument", "depth_mm must be a positive, finite, resolvable length"
        )
    return float(value)


def _staged_depth(definition: Any, expected_mm: float) -> None:
    value = native_call(
        "feature-depth-stage",
        "ExtrudeFeatureData.GetDepth",
        lambda: definition.GetDepth(True),
    )
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not math.isclose(
            value * 1000, expected_mm, rel_tol=0, abs_tol=_DEPTH_TOLERANCE_MM
        )
    ):
        raise _FeatureError(
            "FeatureDepthStagingFailed",
            "native feature-data depth did not match the request",
        )


def _stable(
    app: Any, document: Any, expected: Dict[str, Any], edit: Any, foreground: Any
):
    state, current_edit, current_foreground = _state(app, document)
    if (
        state != expected
        or not _same(app, edit, current_edit)
        or not _same(app, foreground, current_foreground)
    ):
        raise _FeatureError(
            "FeatureObservationUnavailable",
            "native state changed outside the owned mutation lifecycle",
        )
    return state


def set_extrusion_depth_windows(
    *, app: Any, document: Any, feature: Any, depth_mm: float
) -> Dict[str, Any]:
    """Change only forward blind depth; caller owns activation/lease/stamp guards.

    Requires an active exact supported part. Complete scope access can change
    the update stamp even for equal-depth requests; depth_changed is therefore
    not a promise of an unchanged document stamp. Never saves, restarts or undoes.
    """
    result: Dict[str, Any] = {"ok": False, "action": "feature.set-depth"}
    result["mutation"] = {
        "staging_attempted": False,
        "configuration_scope_applied": False,
        "commit_attempted": False,
        "committed": False,
    }
    before = None
    expected_final = None
    edit = foreground = None
    try:
        target = _depth(depth_mm)
        result["requested_depth_mm"] = target
        before, definition = observe_extrusion_selection_scope_windows_with_definition(
            app=app, document=document, feature=feature
        )
        result["preflight"] = before
        if not before["ok"]:
            result["error"] = before["error"]
            return result
        if definition is None:
            raise _FeatureError(
                "FeatureObservationUnavailable", "fresh native feature data is absent"
            )
        current, edit, foreground = _state(app, document)
        if current != before["observation"]["after"] or not _same(
            app, foreground, document
        ):
            raise _FeatureError(
                "FeatureObservationUnavailable",
                "native state changed after scope preflight",
            )
        result.update(
            feature=before["feature"],
            before_depth_mm=before["definition"]["depth_mm"],
            depth_changed=False,
            measurement_before=before["measurement_after"],
        )
        if math.isclose(
            target, result["before_depth_mm"], rel_tol=0, abs_tol=_DEPTH_TOLERANCE_MM
        ):
            result["definition_after"] = before["definition"]
            result["measurement_after"] = before["measurement_after"]
            result["verification"] = {
                "passed": True,
                "method": "guarded-equal-depth",
                "absolute_tolerance_mm": _DEPTH_TOLERANCE_MM,
            }
            _stable(app, document, current, edit, foreground)
            expected_final = current
            result["ok"] = True
            return result

        result["mutation"]["staging_attempted"] = True
        result["depth_changed"] = None
        native_call(
            "feature-depth-stage",
            "ExtrudeFeatureData.SetDepth",
            lambda: definition.SetDepth(True, target / 1000),
        )
        _staged_depth(definition, target)
        scoped = native_call(
            "feature-depth-stage",
            "ExtrudeFeatureData.SetChangeToConfigurations",
            lambda: definition.SetChangeToConfigurations(1, _empty_variant()),
        )
        if not _boolean(scoped, "SetChangeToConfigurations"):
            raise _FeatureError(
                "FeatureConfigurationScopeFailed",
                "native current-configuration scope was rejected",
            )
        result["mutation"]["configuration_scope_applied"] = True
        # Data staging is not model mutation. Verify the live part remains at
        # the original definition/profile/controls/geometry before committing.
        check, _ = prepare_profiled_extrusion_depth_edit_windows_with_definition(
            app=app, document=document, feature=feature
        )
        if not check["ok"]:
            raise _FeatureError(check["error"]["type"], check["error"]["message"])
        if any(check[key] != before[key] for key in _SNAPSHOT_KEYS):
            raise _FeatureError(
                "FeatureDepthStagingChangedModel",
                "live feature, controls or profile changed before commit",
            )
        if not _same_geometry(result["measurement_before"], _measurement(document)):
            raise _FeatureError(
                "FeatureDepthStagingChangedModel", "live geometry changed before commit"
            )
        _stable(app, document, current, edit, foreground)

        result["mutation"]["commit_attempted"] = True
        committed = native_call(
            "feature-depth-commit",
            "Feature.ModifyDefinition",
            lambda: feature.ModifyDefinition(definition, document, _null_dispatch()),
        )
        if not _boolean(committed, "ModifyDefinition"):
            raise _FeatureError(
                "FeatureDepthSetFailed", "SOLIDWORKS rejected the depth modification"
            )
        result["mutation"]["committed"] = True
        result["rebuilt"] = _boolean(
            native_call(
                "feature-depth-rebuild",
                "ModelDoc.EditRebuild3",
                lambda: _com_value(document, "EditRebuild3"),
            ),
            "EditRebuild3",
        )
        if not result["rebuilt"]:
            raise _FeatureError(
                "ModelInvalid", "modified depth did not rebuild successfully"
            )
        after, _ = observe_extrusion_selection_scope_windows_with_definition(
            app=app, document=document, feature=feature
        )
        result["postflight"] = after
        if not after["ok"]:
            raise _FeatureError(after["error"]["type"], after["error"]["message"])
        actual = after["definition"]["depth_mm"]
        unchanged = dict(after["definition"], depth_mm=before["definition"]["depth_mm"])
        if (
            not math.isclose(actual, target, rel_tol=0, abs_tol=_DEPTH_TOLERANCE_MM)
            or unchanged != before["definition"]
            or any(
                after[key] != before[key]
                for key in ("feature", "controls", "profile", "body", "scope")
            )
            or after["observation"]["after"]["configuration"]
            != current["configuration"]
            or after["observation"]["after"]["editing"]
        ):
            raise _FeatureError(
                "FeatureDepthVerificationFailed",
                "depth, non-depth parameters, profile, body or configuration scope changed unexpectedly",
            )
        result.update(
            depth_changed=True,
            definition_after=after["definition"],
            measurement_after=after["measurement_after"],
            verification={
                "passed": True,
                "method": "native-blind-depth-preserved-profile-and-scope",
                "absolute_tolerance_mm": _DEPTH_TOLERANCE_MM,
            },
        )
        # Measurements are independent evidence of a valid single-solid part,
        # not an invented area*depth formula for arbitrary downstream topology.
        _stable(app, document, after["observation"]["after"], edit, foreground)
        expected_final = after["observation"]["after"]
        result["ok"] = True
    except Exception as exc:
        _failure(result, exc)
    finally:
        if before is not None and before.get("ok"):
            try:
                result["final_state"], final_edit, final_foreground = _state(
                    app, document
                )
                if result["ok"] and (
                    result["final_state"] != expected_final
                    or not _same(app, edit, final_edit)
                    or not _same(app, foreground, final_foreground)
                ):
                    raise _FeatureError(
                        "FeatureDepthVerificationFailed",
                        "native edit/configuration/foreground state changed at completion",
                    )
            except Exception as exc:
                _failure(result, exc, "feature-depth-final-state-unavailable")
                result["ok"] = False
        if "error" in result:
            result["ok"] = False
            result["modification_may_have_happened"] = result["mutation"][
                "staging_attempted"
            ]
    return result
