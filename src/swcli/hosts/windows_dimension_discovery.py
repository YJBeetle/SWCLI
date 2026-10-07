"""Read-only discovery of an observable circle diameter on the worker thread.

The a5 development protocol exposes this narrow adapter; Wine is a separate
delivery gate. Native Windows
saved-model experiments show that a feature display chain can be readable, but
the official GetFirstDisplayDimension/GetNextDisplayDimension documentation has
a display prerequisite. An empty chain therefore does not prove that persisted
dimensions are absent. This adapter never changes that display preference.

Display/native-dimension identity comparisons are bounded to one profile; this
does not claim linear-time discovery of arbitrary model dimensions.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

from .windows import _com_value
from .windows_dimensions import (
    _DimensionError,
    _TOLERANCE_MM,
    _boolean,
    _circle,
    _configuration,
    _diameter_circle_verification,
    _descriptor,
    _equation_control,
    _failure,
    _integer,
    _same,
)
from .windows_sketch_inspection import _feature_id, _list_features

_DISPLAY_LIMIT = 10000


def _state(document: Any) -> Tuple[Dict[str, Any], Optional[Any]]:
    stamp = _integer(document, "GetUpdateStamp")
    configuration = _configuration(document)
    edit = _com_value(_com_value(document, "SketchManager"), "ActiveSketch")
    return {
        "update_stamp": stamp,
        "configuration": configuration,
        "editing": edit is not None,
    }, edit


def _profile(app: Any, document: Any, sketch_feature: Any) -> Tuple[Any, Any]:
    target_id = _feature_id(sketch_feature)
    # Exhaust the traversal before choosing a target. A matching first feature
    # must not hide a later cycle, duplicate-ID conflict or unreadable sibling.
    features = tuple(_list_features(app, document))
    feature = next((item for item in features if _feature_id(item) == target_id), None)
    if (
        feature is None
        or not _same(app, feature, sketch_feature)
        or _com_value(feature, "GetTypeName2") != "ProfileFeature"
    ):
        raise _DimensionError(
            "SketchUnavailable",
            "the exact target is not a live 2D profile in this part",
        )
    sketch = _com_value(feature, "GetSpecificFeature2")
    if sketch is None:
        raise _DimensionError(
            "DimensionObservationUnavailable", "the native 2D sketch is unreadable"
        )
    return feature, sketch


def _displays(app: Any, feature: Any) -> Tuple[Any, ...]:
    display = _com_value(feature, "GetFirstDisplayDimension")
    if display is None:
        raise _DimensionError(
            "DimensionObservationUnavailable",
            "the feature display chain is empty; hidden or unloaded persisted dimensions may not be exposed",
        )
    chain = []
    while display is not None:
        if len(chain) >= _DISPLAY_LIMIT:
            raise _DimensionError(
                "DimensionObservationUnavailable",
                "the feature display chain exceeded its safety limit",
            )
        if any(_same(app, previous, display) for previous in chain):
            raise _DimensionError(
                "DimensionObservationUnavailable",
                "the native feature display chain contains a cycle",
            )
        chain.append(display)
        display = feature.GetNextDisplayDimension(display)
    return tuple(chain)


def discover_circle_diameter_windows_with_handle(
    *, app: Any, document: Any, sketch_feature: Any
) -> Tuple[Dict[str, Any], Optional[Any]]:
    """Observe one exact, current-configuration diameter without native mutation.

    Existing and absorbed profiles are supported. Failures never publish a
    native handle, including incomplete traversal or a changing observation.
    """
    result: Dict[str, Any] = {"ok": False, "action": "dimension.discover"}
    before = edit_before = native = None
    try:
        if _integer(document, "GetType") != 1:
            raise _DimensionError(
                "UnsupportedDocumentType", "circle diameter discovery requires a part"
            )
        before, edit_before = _state(document)
        result["observation"] = {"before": before, "unchanged": False}
        feature, sketch = _profile(app, document, sketch_feature)
        radius, x, y = _circle(sketch)
        candidates = []
        for display in _displays(app, feature):
            if _integer(display, "Type2") != 6:
                continue
            candidate = display.GetDimension2(0)
            if candidate is None or _integer(candidate, "GetType") != 0:
                raise _DimensionError(
                    "DimensionObservationUnavailable",
                    "an observable diameter has no supported native length parameter",
                )
            owner = _com_value(candidate, "GetFeatureOwner")
            if owner is None or not _same(app, owner, feature):
                raise _DimensionError(
                    "DimensionVerificationFailed",
                    "an observable diameter does not belong to the exact target profile",
                )
            if any(_same(app, previous, candidate) for previous, _ in candidates):
                continue
            descriptor = _descriptor(document, candidate)
            configuration_matched = (
                descriptor["configuration"] == before["configuration"]
            )
            result["observation"]["configuration_matched"] = configuration_matched
            if not configuration_matched:
                raise _DimensionError(
                    "DimensionObservationUnavailable",
                    "observed dimension configuration differs from the initial current configuration",
                )
            if (
                descriptor["value"] is None
                or descriptor["value"] <= 0
                or not math.isclose(
                    descriptor["value"], radius * 2, rel_tol=0, abs_tol=_TOLERANCE_MM
                )
            ):
                raise _DimensionError(
                    "DimensionVerificationFailed",
                    "an observable native diameter does not equal twice the source circle radius",
                )
            candidates.append((candidate, descriptor))
        if not candidates:
            raise _DimensionError(
                "DimensionNotFound",
                "no supported diameter was observable in this complete display chain; hidden or unloaded persisted dimensions may not be exposed",
            )
        if len(candidates) != 1:
            raise _DimensionError(
                "DimensionAmbiguous",
                "multiple different native diameters belong to this profile",
            )
        native, descriptor = candidates[0]
        result.update(
            dimension=descriptor,
            geometry_verification=_diameter_circle_verification(
                sketch, descriptor["value"] / 2, x, y
            ),
            constraint_status=_integer(sketch, "GetConstrainedStatus"),
            editing=before["editing"],
            equation_control=_equation_control(document, descriptor["native_name"]),
            design_table_controlled=_boolean(native, "IsDesignTableDimension"),
        )
        if not result["geometry_verification"]["passed"]:
            raise _DimensionError(
                "DimensionVerificationFailed",
                "source circle geometry changed during discovery",
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
        return result, None
    result["ok"] = True
    return result, native
