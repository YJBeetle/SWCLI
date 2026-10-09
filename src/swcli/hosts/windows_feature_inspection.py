"""Read-only observations of exact part extrusion features.

No selection access, rollback, activation, rebuild or native edit occurs here.
The worker assigns public handles only after validating complete observations.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Tuple

from .native_trace import native_call
from .windows import _com_value, _error
from .windows_sketch_inspection import (
    SketchFeatureIdConflict,
    SketchTraversalCycle,
    SketchTraversalLimitExceeded,
    _feature_id,
    _list_features,
)

_KINDS = {
    "Boss": "boss-extrude",
    "Extrusion": "boss-extrude",
    "BaseBody": "boss-extrude",
    "Cut": "cut-extrude",
}


class _FeatureError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _boolean(value: Any, member: str) -> bool:
    if not isinstance(value, bool):
        raise _FeatureError(
            "FeatureObservationUnavailable", f"native {member} is not a boolean"
        )
    return value


def _integer(value: Any, member: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _FeatureError(
            "FeatureObservationUnavailable", f"native {member} is not an integer"
        )
    return value


def _string(value: Any, member: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _FeatureError(
            "FeatureObservationUnavailable", f"native {member} is unreadable"
        )
    return value


def _same(app: Any, first: Any, second: Any) -> bool:
    if first is None or second is None:
        return first is None and second is None
    status = _integer(app.IsSame(first, second), "IsSame")
    if status not in (0, 1):
        raise _FeatureError(
            "FeatureObservationUnavailable", "native identity is unreadable"
        )
    return status == 1


def _state(app: Any, document: Any) -> Tuple[Dict[str, Any], Any, Any]:
    configuration = _com_value(
        _com_value(_com_value(document, "ConfigurationManager"), "ActiveConfiguration"),
        "Name",
    )
    edit = _com_value(_com_value(document, "SketchManager"), "ActiveSketch")
    foreground = _com_value(app, "ActiveDoc")
    return (
        {
            "configuration": _string(configuration, "configuration"),
            "update_stamp": _integer(
                _com_value(document, "GetUpdateStamp"), "GetUpdateStamp"
            ),
            "modified": _boolean(_com_value(document, "GetSaveFlag"), "GetSaveFlag"),
            "editing": edit is not None,
            "foreground_present": foreground is not None,
        },
        edit,
        foreground,
    )


def _failure(result: Dict[str, Any], exc: Exception) -> None:
    code = {
        SketchFeatureIdConflict: "FeatureIdConflict",
        SketchTraversalCycle: "FeatureTraversalCycle",
        SketchTraversalLimitExceeded: "FeatureTraversalLimitExceeded",
    }.get(type(exc))
    result["error"] = (
        {"type": getattr(exc, "code", code), "message": str(exc)}
        if isinstance(exc, _FeatureError) or code is not None
        else _error(exc)
    )


def _observe(
    *,
    action: str,
    app: Any,
    document: Any,
    read: Callable[[], Tuple[Dict[str, Any], List[Any]]],
) -> Tuple[Dict[str, Any], List[Any]]:
    result: Dict[str, Any] = {"ok": False, "action": action}
    before = None
    handles: List[Any] = []
    payload: Dict[str, Any] = {}
    try:
        if _integer(_com_value(document, "GetType"), "GetType") != 1:
            raise _FeatureError(
                "UnsupportedDocumentType", "feature observation requires a part"
            )
        before, edit_before, foreground_before = _state(app, document)
        result["observation"] = {"before": before, "unchanged": False}
        payload, handles = read()
    except Exception as exc:
        _failure(result, exc)
    finally:
        if before is not None:
            try:
                after, edit_after, foreground_after = _state(app, document)
                result["observation"]["after"] = after
                unchanged = (
                    before == after
                    and _same(app, edit_before, edit_after)
                    and _same(app, foreground_before, foreground_after)
                )
                result["observation"]["unchanged"] = unchanged
                if not unchanged:
                    raise _FeatureError(
                        "FeatureObservationUnavailable",
                        "configuration, stamp, modified flag, edit or foreground changed during observation",
                    )
            except Exception as exc:
                if "error" in result:
                    result.setdefault("warnings", []).append(
                        {
                            "code": "feature-observation-state-check-failed",
                            "message": str(exc),
                        }
                    )
                else:
                    _failure(result, exc)
    if "error" in result:
        return result, []
    result.update(payload, ok=True)
    return result, handles


def _types(feature: Any) -> Tuple[str, str]:
    displayed = _string(_com_value(feature, "GetTypeName2"), "GetTypeName2")
    underlying = (
        _string(_com_value(feature, "GetTypeName"), "GetTypeName")
        if displayed == "ICE"
        else displayed
    )
    return displayed, underlying


def _descriptor(feature: Any, displayed: str, underlying: str) -> Dict[str, Any]:
    return {
        "name": _string(_com_value(feature, "Name"), "feature name"),
        "type": displayed,
        "native_type": underlying,
        "kind": _KINDS[underlying],
    }


def list_extrusion_features_windows_with_handles(
    *,
    app: Any,
    document: Any,
    max_features: int = 1000,
) -> Tuple[Dict[str, Any], List[Any]]:
    """Observe a complete bounded extrusion list, not an arbitrary feature tree."""
    if (
        isinstance(max_features, bool)
        or not isinstance(max_features, int)
        or max_features < 1
    ):
        return {
            "ok": False,
            "action": "feature.list",
            "error": {
                "type": "InvalidArgument",
                "message": "max_features must be a positive integer",
            },
        }, []

    def read():
        descriptors, handles = [], []
        for feature in _list_features(app, document):
            displayed, underlying = _types(feature)
            if underlying not in _KINDS:
                continue
            if len(handles) >= max_features:
                raise _FeatureError(
                    "FeatureListLimitExceeded",
                    "increase max_features to observe this part's complete extrusion list",
                )
            descriptors.append(_descriptor(feature, displayed, underlying))
            handles.append(feature)
        return {
            "scope": "part-extrusions",
            "features": descriptors,
            "count": len(handles),
        }, handles

    return _observe(action="feature.list", app=app, document=document, read=read)


def _read_exact_extrusion(app: Any, document: Any, feature: Any):
    """Return read evidence and its exact definition, without selection access."""
    target_id = _feature_id(feature)
    # Exhaust first: an early match must not hide a later malformed chain.
    features = tuple(_list_features(app, document))
    live = next((item for item in features if _feature_id(item) == target_id), None)
    if live is None or not _same(app, live, feature):
        raise _FeatureError(
            "FeatureUnavailable", "the exact feature is not live in this part"
        )
    displayed, underlying = _types(live)
    if underlying not in _KINDS:
        raise _FeatureError(
            "UnsupportedFeatureType",
            "only part boss/cut extrusion definitions are observed",
        )
    definition = _com_value(live, "GetDefinition")
    if definition is None:
        raise _FeatureError(
            "FeatureObservationUnavailable",
            "native extrusion definition is unavailable",
        )

    depth = native_call(
        "feature-observe",
        "ExtrudeFeatureData.GetDepth",
        lambda: definition.GetDepth(True),
    )
    if (
        isinstance(depth, bool)
        or not isinstance(depth, (int, float))
        or not math.isfinite(depth)
        or depth < 0
        or not math.isfinite(depth * 1000)
    ):
        raise _FeatureError(
            "FeatureObservationUnavailable", "native forward depth is invalid"
        )
    snapshot = {
        "depth_mm": depth * 1000,
        "end_condition": _integer(
            native_call(
                "feature-observe",
                "ExtrudeFeatureData.GetEndCondition",
                lambda: definition.GetEndCondition(True),
            ),
            "GetEndCondition",
        ),
        "reverse_direction": _boolean(
            _com_value(definition, "ReverseDirection"), "ReverseDirection"
        ),
        "both_directions": _boolean(
            _com_value(definition, "BothDirections"), "BothDirections"
        ),
        "thin": _boolean(_com_value(definition, "IsThinFeature"), "IsThinFeature"),
        "from_type": _integer(_com_value(definition, "FromType"), "FromType"),
        "forward_draft": _boolean(
            native_call(
                "feature-observe",
                "ExtrudeFeatureData.GetDraftWhileExtruding",
                lambda: definition.GetDraftWhileExtruding(True),
            ),
            "GetDraftWhileExtruding",
        ),
        "reverse_draft": _boolean(
            native_call(
                "feature-observe",
                "ExtrudeFeatureData.GetDraftWhileExtruding",
                lambda: definition.GetDraftWhileExtruding(False),
            ),
            "GetDraftWhileExtruding",
        ),
    }
    if underlying != "Cut":
        snapshot["merge"] = _boolean(_com_value(definition, "Merge"), "Merge")
    else:
        snapshot["feature_scope"] = _boolean(
            _com_value(definition, "FeatureScope"), "FeatureScope"
        )
    return {
        "feature": _descriptor(live, displayed, underlying),
        "definition": snapshot,
    }, definition


def inspect_extrusion_feature_windows(
    *,
    app: Any,
    document: Any,
    feature: Any,
) -> Dict[str, Any]:
    """Observe the exact live definition, without asserting edit eligibility."""

    def read():
        payload, _ = _read_exact_extrusion(app, document, feature)
        return payload, []

    result, _ = _observe(
        action="feature.inspect", app=app, document=document, read=read
    )
    return result
