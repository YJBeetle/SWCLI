"""Read-only recovery of one observable rectangle width/height pair.

This is not general length discovery. Native horizontal/vertical display types,
exact profile ownership and independent rectangle geometry must all agree.
An empty display chain is unavailable evidence, not proof of absent dimensions;
the adapter never changes display preferences or activates/edits the document.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from .windows import _com_value
from .windows_dimension_discovery import _displays, _profile, _state
from .windows_dimensions import (
    _DimensionError,
    _failure,
    _integer,
    _same,
    _same_dimension,
)
from .windows_linear_dimensions import inspect_rectangle_dimension_windows
from .windows_rectangle_dimensions import _observe, _verify


def _pair(app: Any, feature: Any) -> Dict[str, Any]:
    candidates: Dict[str, list[Any]] = {"width": [], "height": []}
    for display in _displays(app, feature):
        kind = {11: "width", 12: "height"}.get(_integer(display, "Type2"))
        if kind is None:
            continue
        native = display.GetDimension2(0)
        if native is None:
            raise _DimensionError(
                "DimensionObservationUnavailable",
                "an observable linear display has no readable native parameter",
            )
        if _integer(native, "GetType") != 0:
            raise _DimensionError(
                "DimensionVerificationFailed",
                "native rectangle parameter is not a length",
            )
        owner = _com_value(native, "GetFeatureOwner")
        if owner is None or not _same(app, owner, feature):
            raise _DimensionError(
                "DimensionVerificationFailed",
                "an observable linear dimension belongs to a different profile",
            )
        if not any(
            _same_dimension(app, previous, native) for previous in candidates[kind]
        ):
            candidates[kind].append(native)
    if any(not items for items in candidates.values()):
        raise _DimensionError(
            "DimensionNotFound",
            "a complete width/height pair was not observable; hidden or unloaded persisted dimensions may not be exposed",
        )
    if any(len(items) != 1 for items in candidates.values()):
        raise _DimensionError(
            "DimensionAmbiguous",
            "multiple different native linear dimensions share a role",
        )
    pair = {kind: items[0] for kind, items in candidates.items()}
    if _same_dimension(app, pair["width"], pair["height"]):
        raise _DimensionError(
            "DimensionVerificationFailed",
            "the same native dimension claims both linear roles",
        )
    return pair


def discover_rectangle_dimensions_windows_with_handles(
    *, app: Any, document: Any, sketch_feature: Any
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Recover both exact handles only after complete, unchanged native reads.

    Controls (driven/read-only/equation/design-table) are observed, not removed.
    A failed read retains partial diagnostic evidence but publishes no handles.
    Existing and absorbed axis-aligned profiles are supported.
    """
    result: Dict[str, Any] = {"ok": False, "action": "dimension.discover"}
    before = edit_before = None
    pair: Dict[str, Any] = {}
    try:
        if _integer(document, "GetType") != 1:
            raise _DimensionError(
                "UnsupportedDocumentType",
                "rectangle dimension discovery requires a part",
            )
        before, edit_before = _state(document)
        result["observation"] = {"before": before, "unchanged": False}
        feature, sketch = _profile(app, document, sketch_feature)
        original = _observe(sketch)
        pair = _pair(app, feature)
        result.update(dimensions={}, inspections={})
        for kind, native in pair.items():
            inspected = inspect_rectangle_dimension_windows(
                app=app,
                document=document,
                sketch_feature=feature,
                dimension=native,
                kind=kind,
            )
            result["inspections"][kind] = inspected
            if not inspected["ok"]:
                result["error"] = inspected["error"]
                break
            result["dimensions"][kind] = inspected["dimension"]
            matched = inspected["observation"]["before"] == before
            result["observation"]["configuration_matched"] = matched
            if not matched:
                raise _DimensionError(
                    "DimensionObservationUnavailable",
                    "native state changed between dimension reads",
                )
            if not inspected["geometry_verification"]["passed"]:
                raise _DimensionError(
                    "DimensionVerificationFailed",
                    "native linear value and rectangle geometry disagree",
                )
        if "error" not in result:
            result.update(
                geometry_verification=_verify(
                    _observe(sketch),
                    original.width_mm,
                    original.height_mm,
                    original.center_mm,
                ),
                constraint_status=_integer(sketch, "GetConstrainedStatus"),
                editing=before["editing"],
            )
            if not result["geometry_verification"]["passed"]:
                raise _DimensionError(
                    "DimensionObservationUnavailable",
                    "rectangle geometry changed during discovery",
                )
    except Exception as exc:
        _failure(result, exc)
    finally:
        if before is not None:
            try:
                after, edit_after = _state(document)
                result["observation"]["after"] = after
                unchanged = (
                    before == after
                    and result["observation"].get("configuration_matched", True)
                    and (edit_before is None or _same(app, edit_before, edit_after))
                )
                result["observation"]["unchanged"] = unchanged
                if not unchanged:
                    raise _DimensionError(
                        "DimensionObservationUnavailable",
                        "native update stamp, configuration or sketch edit changed during discovery",
                    )
            except Exception as exc:
                if "error" in result:
                    result.setdefault("warnings", []).append(
                        {
                            "code": "dimension-discovery-state-check-failed",
                            "message": str(exc),
                        }
                    )
                else:
                    _failure(result, exc)
    if "error" in result:
        return result, {}
    result["ok"] = True
    return result, pair
