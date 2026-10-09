"""Nonmutating profile/body guard, not complete extrusion edit authority.

Selected contours, direction references and rollback-state body selections need
separate native proof. A final one-body model does not identify those selections.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

from .windows import _com_value
from .windows_dimensions import _DimensionError, _circle_geometry
from .windows_feature_depth import prepare_extrusion_depth_edit_windows_with_definition
from .windows_feature_inspection import (
    _FeatureError,
    _boolean,
    _integer,
    _observe,
    _same,
)
from .windows_rectangle_profiles import (
    RectangleObservationError,
    observe_rectangle_profile,
)
from .windows_sketch_inspection import _feature_id, _list_features


def _array(value: Any, name: str, limit: int) -> tuple:
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= limit:
        raise _FeatureError(
            "FeatureObservationUnavailable",
            f"native {name} is unreadable or incomplete",
        )
    if any(item is None for item in value):
        raise _FeatureError(
            "FeatureObservationUnavailable", f"native {name} contains a null object"
        )
    return tuple(value)


def _profile(app: Any, document: Any, feature: Any) -> Dict[str, Any]:
    live = {_feature_id(item): item for item in _list_features(app, document)}
    parents = _array(_com_value(feature, "GetParents"), "feature parents", 1000)
    identities, profiles = [], []
    for parent in parents:
        identity = _feature_id(parent)
        if (
            identity in identities
            or identity not in live
            or not _same(app, parent, live[identity])
        ):
            raise _FeatureError(
                "FeatureProfileUnavailable",
                "a parent is duplicate or not live in this part",
            )
        identities.append(identity)
        if _com_value(parent, "GetTypeName2") == "ProfileFeature":
            profiles.append(parent)
    if len(profiles) != 1:
        raise _FeatureError(
            "UnsupportedDepthProfile", "require exactly one direct 2D profile parent"
        )
    profile = profiles[0]
    if not _same(app, _com_value(profile, "GetOwnerFeature"), feature):
        raise _FeatureError(
            "FeatureProfileUnavailable",
            "the exact profile is not absorbed by this feature",
        )
    sketch = _com_value(profile, "GetSpecificFeature2")
    if sketch is None:
        raise _FeatureError(
            "FeatureProfileUnavailable", "native profile sketch is unavailable"
        )
    segments = _array(_com_value(sketch, "GetSketchSegments"), "profile segments", 64)
    try:
        if len(segments) == 1:
            _, radius, x, y, z = _circle_geometry(sketch)
            geometry = {
                "kind": "circle",
                "radius_mm": radius,
                "center_mm": {"x": x, "y": y, "z": z},
                "area_mm2": math.pi * radius * radius,
                "construction_segment_count": 0,
            }
        else:
            rectangle = observe_rectangle_profile(sketch)
            geometry = {
                "kind": "rectangle",
                "width_mm": rectangle.width_mm,
                "height_mm": rectangle.height_mm,
                "center_mm": {
                    "x": rectangle.center_mm[0],
                    "y": rectangle.center_mm[1],
                    "z": 0,
                },
                "bounds_mm": list(rectangle.bounds_mm),
                "area_mm2": rectangle.width_mm * rectangle.height_mm,
                "construction_segment_count": rectangle.construction_segment_count,
            }
    except (_DimensionError, RectangleObservationError) as exc:
        code = (
            "UnsupportedDepthProfile"
            if exc.code == "UnsupportedDimensionProfile"
            else "FeatureObservationUnavailable"
        )
        raise _FeatureError(code, str(exc)) from exc
    if not math.isfinite(geometry["area_mm2"]) or geometry["area_mm2"] <= 0:
        raise _FeatureError(
            "FeatureObservationUnavailable", "native profile area is unrepresentable"
        )
    raw = _com_value(_com_value(sketch, "ModelToSketchTransform"), "ArrayData")
    if (
        not isinstance(raw, (tuple, list))
        or len(raw) != 16
        or any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in raw
        )
    ):
        raise _FeatureError(
            "FeatureObservationUnavailable", "native profile transform is unreadable"
        )
    transform = [float(value) for value in raw]
    if not all(math.isfinite(value) for value in transform):
        raise _FeatureError(
            "FeatureObservationUnavailable", "native profile transform is nonfinite"
        )
    # This is a current native identity fingerprint, never a persistent/public ID.
    return {
        "native_profile_id": _feature_id(profile),
        "native_parent_ids": sorted(identities),
        "geometry": geometry,
        "segment_count": len(segments),
        "model_to_sketch_transform": transform,
    }


def _body(document: Any) -> Dict[str, Any]:
    # All bodies, including hidden ones: a solid plus a surface is not this slice.
    bodies = _array(document.GetBodies2(-1, False), "part bodies", 1000)
    if len(bodies) != 1 or _integer(_com_value(bodies[0], "GetType"), "body type") != 0:
        raise _FeatureError(
            "UnsupportedDepthBodyScope",
            "require exactly one final solid body and no surface bodies",
        )
    if _boolean(_com_value(bodies[0], "IsSheetMetal"), "IsSheetMetal"):
        raise _FeatureError(
            "UnsupportedDepthBodyScope", "sheet metal is outside the first depth slice"
        )
    return {"scope": "final-part-bodies", "solid_body_count": 1, "sheet_metal": False}


def prepare_profiled_extrusion_depth_edit_windows_with_definition(
    *, app: Any, document: Any, feature: Any
) -> Tuple[Dict[str, Any], Optional[Any]]:
    """Add stable exact-profile/final-body proof to preliminary controls.

    Does not access selections, activate, rebuild or modify the model. This is
    still not a setter: final bodies and profile area do not prove feature scope,
    extrusion direction or a downstream model's expected volume response.
    """

    def read():
        first, definition = prepare_extrusion_depth_edit_windows_with_definition(
            app=app, document=document, feature=feature
        )
        if not first["ok"]:
            raise _FeatureError(first["error"]["type"], first["error"]["message"])
        profile, body = _profile(app, document, feature), _body(document)
        repeated_profile, repeated_body = _profile(app, document, feature), _body(
            document
        )
        repeated, _ = prepare_extrusion_depth_edit_windows_with_definition(
            app=app, document=document, feature=feature
        )
        if not repeated["ok"]:
            raise _FeatureError(repeated["error"]["type"], repeated["error"]["message"])
        keys = ("feature", "definition", "controls")
        if (
            profile != repeated_profile
            or body != repeated_body
            or any(first[key] != repeated[key] for key in keys)
        ):
            raise _FeatureError(
                "FeatureObservationUnavailable",
                "profile, body, definition or controls changed during preflight",
            )
        return dict({key: first[key] for key in keys}, profile=profile, body=body), [
            definition
        ]

    result, handles = _observe(
        action="feature.profile-depth-preflight", app=app, document=document, read=read
    )
    return result, handles[0] if handles else None
