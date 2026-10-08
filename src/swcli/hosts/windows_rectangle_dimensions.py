"""Internal rectangle-size creation on the owning COM STA, not a public API.

Two native dimensions are not a transaction. Return exact partial handles on
failure and never add a positioning constraint implicitly. A caller must not
publish a failed, unverified handle as a verified width/height binding.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Tuple

from .native_trace import native_call
from .windows import _com_value
from .windows_dimension_discovery import _profile
from .windows_dimensions import (
    _CURRENT_CONFIGURATION,
    _INPUT_VALUE_ON_CREATE,
    _TOLERANCE_MM,
    _DimensionError,
    _annotation_location,
    _boolean,
    _configuration,
    _descriptor,
    _equation_control,
    _failure,
    _integer,
    _owned_dimension,
    _positive_length,
    _require_writable,
    _same,
    _same_dimension,
    _variant,
)
from .windows_rectangle_profiles import (
    RectangleObservationError,
    RectangleProfile,
    observe_rectangle_profile,
)


def _observe(sketch: Any) -> RectangleProfile:
    try:
        return observe_rectangle_profile(sketch)
    except RectangleObservationError as exc:
        raise _DimensionError(exc.code, str(exc)) from exc


def _geometry(profile: RectangleProfile) -> Dict[str, Any]:
    return {
        "width_mm": profile.width_mm,
        "height_mm": profile.height_mm,
        "center_mm": {"x": profile.center_mm[0], "y": profile.center_mm[1], "z": 0},
        "bounds_mm": list(profile.bounds_mm),
        "profile_segment_count": 4,
        "construction_segment_count": profile.construction_segment_count,
        "max_abs_z_mm": profile.max_abs_z_mm,
    }


def _verify(
    profile: RectangleProfile,
    width: float,
    height: float,
    center: Tuple[float, float],
) -> Dict[str, Any]:
    size_matched = all(
        math.isclose(a, b, rel_tol=0, abs_tol=_TOLERANCE_MM)
        for a, b in ((profile.width_mm, width), (profile.height_mm, height))
    )
    center_preserved = all(
        math.isclose(a, b, rel_tol=0, abs_tol=_TOLERANCE_MM)
        for a, b in zip(profile.center_mm, center)
    )
    return {
        "method": "sketch-local-rectangle",
        "passed": size_matched and center_preserved,
        "size_matched": size_matched,
        "center_preserved": center_preserved,
        "expected_width_mm": width,
        "expected_height_mm": height,
        "expected_center_mm": {"x": center[0], "y": center[1], "z": 0},
        "actual": _geometry(profile),
        "absolute_tolerance_mm": _TOLERANCE_MM,
    }


def _prompt(app: Any) -> bool:
    value = app.GetUserPreferenceToggle(_INPUT_VALUE_ON_CREATE)
    if not isinstance(value, bool):
        raise _DimensionError(
            "DimensionObservationUnavailable",
            "native dimension prompt is not a boolean",
        )
    return value


def _linear_descriptor(
    app: Any,
    document: Any,
    feature: Any,
    display: Any,
    dimension: Any,
    kind: str,
    configuration: str,
    *,
    post_mutation: bool,
) -> Dict[str, Any]:
    if _integer(display, "Type2") != {"width": 11, "height": 12}[kind]:
        raise _DimensionError(
            "DimensionVerificationFailed", f"native display is not a {kind} dimension"
        )
    if _integer(dimension, "GetType") != 0:
        raise _DimensionError(
            "DimensionVerificationFailed", "native rectangle parameter is not a length"
        )
    owner = _com_value(dimension, "GetFeatureOwner")
    if owner is None or not _same(app, owner, feature):
        raise _DimensionError(
            "DimensionVerificationFailed",
            "native dimension has a different owning sketch",
        )
    descriptor = _descriptor(document, dimension, kind=kind)
    if descriptor["configuration"] != configuration:
        raise _DimensionError(
            "DimensionObservationUnavailable",
            "native configuration changed during creation",
        )
    _require_writable(
        descriptor,
        _equation_control(document, descriptor["native_name"]),
        _boolean(dimension, "IsDesignTableDimension"),
        post_mutation=post_mutation,
    )
    return descriptor


def create_rectangle_dimensions_windows_with_handles(
    *,
    app: Any,
    document: Any,
    sketch_feature: Any,
    width_mm: float,
    height_mm: float,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Create exact width/height dimensions; refuse any unintended center drift.

    Existing positioning relations are honored, never created or inferred.
    The first slice accepts a live unabsorbed axis-aligned profile with an empty
    observable display chain, not arbitrary saved/hidden dimension discovery.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "action": "sketch.dimension-rectangle",
        "dimensions": {},
        "native_status": {},
    }
    handles: Dict[str, Any] = {}
    displays: Dict[str, Any] = {}
    sketch = manager = None
    entered = selected = preference_changed = mutation_attempted = False
    preference = None
    try:
        for kind, value in (("width", width_mm), ("height", height_mm)):
            if (
                not _positive_length(value)
                or value <= 2 * _TOLERANCE_MM
                or math.ulp(value) > _TOLERANCE_MM
            ):
                raise _DimensionError(
                    "InvalidArgument",
                    f"{kind}_mm must resolve a positive rectangle size",
                )
        if _integer(document, "GetType") != 1:
            raise _DimensionError(
                "UnsupportedDocumentType", "rectangle dimensions require a part"
            )
        manager = _com_value(document, "SketchManager")
        if _com_value(manager, "ActiveSketch") is not None:
            raise _DimensionError(
                "SketchEditInProgress", "finish the existing sketch edit first"
            )
        feature, sketch = _profile(app, document, sketch_feature)
        if _com_value(feature, "GetOwnerFeature") is not None:
            raise _DimensionError(
                "SketchUnavailable", "creation requires an unabsorbed profile"
            )
        before = _observe(sketch)
        result["geometry_before"] = _geometry(before)
        if _com_value(feature, "GetFirstDisplayDimension") is not None:
            raise _DimensionError(
                "SketchAlreadyDimensioned", "do not add duplicate profile dimensions"
            )
        configuration = _configuration(document)
        preference = _prompt(app)
        document.ClearSelection2(True)
        selected = True
        if feature.Select2(False, 0) is not True:
            raise _DimensionError(
                "SketchSelectionFailed", "could not select the exact profile"
            )
        entered = True
        native_call(
            "rectangle-dimension",
            "ModelDoc2.EditSketch",
            lambda: _com_value(document, "EditSketch"),
        )
        active = _com_value(manager, "ActiveSketch")
        if active is None or not _same(app, active, sketch):
            raise _DimensionError(
                "SketchUnavailable", "did not enter the exact profile edit"
            )
        preference_changed = True
        app.SetUserPreferenceToggle(_INPUT_VALUE_ON_CREATE, False)
        if _prompt(app):
            raise _DimensionError(
                "DimensionCreationFailed", "could not suppress the value-entry dialog"
            )

        for kind, value, method in (
            ("width", width_mm, "AddHorizontalDimension2"),
            ("height", height_mm, "AddVerticalDimension2"),
        ):
            current = _observe(sketch)
            edge = current.bottom_edge if kind == "width" else current.left_edge
            document.ClearSelection2(True)
            if edge.Select4(False, _variant("dispatch", None)) is not True:
                raise _DimensionError(
                    "SketchSelectionFailed", f"could not select the exact {kind} edge"
                )
            # The native method expects a model-space annotation point in meters.
            x = (
                current.center_mm[0]
                if kind == "width"
                else current.bounds_mm[0] - max(1, current.width_mm / 5)
            )
            y = (
                current.bounds_mm[1] - max(1, current.height_mm / 5)
                if kind == "width"
                else current.center_mm[1]
            )
            location = _annotation_location(app, sketch, x / 1000, y / 1000)
            mutation_attempted = True
            display = native_call(
                "rectangle-dimension",
                f"ModelDoc2.{method}",
                lambda: getattr(document, method)(*location),
            )
            if display is None:
                raise _DimensionError(
                    "DimensionCreationFailed", f"did not create the {kind} dimension"
                )
            displays[kind] = display
            dimension = display.GetDimension2(0)
            if dimension is None:
                raise _DimensionError(
                    "DimensionObservationUnavailable",
                    "created display has no native parameter",
                )
            handles[kind] = dimension
            if any(
                _same_dimension(app, previous, dimension)
                for axis, previous in handles.items()
                if axis != kind
            ):
                raise _DimensionError(
                    "DimensionVerificationFailed",
                    "width and height returned the same parameter",
                )
            result["dimensions"][kind] = _linear_descriptor(
                app,
                document,
                feature,
                display,
                dimension,
                kind,
                configuration,
                post_mutation=False,
            )
            status = native_call(
                "rectangle-dimension",
                f"Dimension.SetSystemValue3({kind})",
                lambda: dimension.SetSystemValue3(
                    value / 1000, _CURRENT_CONFIGURATION, _variant("empty", None)
                ),
            )
            if isinstance(status, bool) or not isinstance(status, int):
                raise _DimensionError(
                    "DimensionObservationUnavailable",
                    "native setter status is not an integer",
                )
            result["native_status"][kind] = status
            if status != 0:
                raise _DimensionError(
                    "DimensionSetFailed", f"SOLIDWORKS rejected the {kind} value"
                )
            descriptor = _linear_descriptor(
                app,
                document,
                feature,
                display,
                dimension,
                kind,
                configuration,
                post_mutation=True,
            )
            result["dimensions"][kind] = descriptor
            verification = _verify(
                _observe(sketch),
                width_mm,
                before.height_mm if kind == "width" else height_mm,
                before.center_mm,
            )
            result.setdefault("steps", {})[kind] = verification
            if (
                not math.isclose(
                    descriptor["value"], value, rel_tol=0, abs_tol=_TOLERANCE_MM
                )
                or not verification["passed"]
            ):
                raise _DimensionError(
                    "DimensionVerificationFailed",
                    f"{kind} value, rectangle size or center did not match",
                )

        native_call(
            "rectangle-dimension",
            "SketchManager.InsertSketch(exit)",
            lambda: manager.InsertSketch(True),
        )
        if _com_value(manager, "ActiveSketch") is not None:
            raise _DimensionError(
                "DimensionVerificationFailed", "profile editing remained active"
            )
        entered = False
        for kind, dimension in handles.items():
            _owned_dimension(app, document, feature, dimension)
            result["dimensions"][kind] = _linear_descriptor(
                app,
                document,
                feature,
                displays[kind],
                dimension,
                kind,
                configuration,
                post_mutation=True,
            )
        verification = _verify(_observe(sketch), width_mm, height_mm, before.center_mm)
        result.update(
            geometry_verification=verification,
            constraint_status=_integer(sketch, "GetConstrainedStatus"),
            editing=False,
        )
        if not verification["passed"] or any(
            not math.isclose(
                result["dimensions"][kind]["value"],
                expected,
                rel_tol=0,
                abs_tol=_TOLERANCE_MM,
            )
            for kind, expected in (("width", width_mm), ("height", height_mm))
        ):
            raise _DimensionError(
                "DimensionVerificationFailed",
                "final values, geometry or center did not match",
            )
        result["ok"] = True
    except Exception as exc:
        _failure(result, exc)
        if mutation_attempted:
            result["modification_may_have_happened"] = True
    finally:

        def cleanup(code, action):
            try:
                action()
            except Exception as exc:
                result.setdefault("warnings", []).append(
                    {"code": code, "message": str(exc)}
                )
                if "error" not in result:
                    _failure(
                        result, _DimensionError("DimensionCleanupFailed", str(exc))
                    )
                    if mutation_attempted:
                        result["modification_may_have_happened"] = True
                result["ok"] = False

        if entered and sketch is not None:

            def exit_owned_edit():
                active = _com_value(manager, "ActiveSketch")
                result["editing"] = active is not None
                if active is None:
                    return
                if not _same(app, active, sketch):
                    raise RuntimeError(
                        "another sketch became active; refusing to close it"
                    )
                manager.InsertSketch(True)
                result["editing"] = _com_value(manager, "ActiveSketch") is not None
                if result["editing"]:
                    raise RuntimeError(
                        "owned sketch editing remained active after cleanup"
                    )

            cleanup("sketch-edit-cleanup-failed", exit_owned_edit)
        if preference_changed:

            def restore_prompt():
                app.SetUserPreferenceToggle(_INPUT_VALUE_ON_CREATE, preference)
                if _prompt(app) != preference:
                    raise RuntimeError("dimension-value preference was not restored")

            cleanup("dimension-preference-restore-failed", restore_prompt)
        if selected:
            cleanup("selection-cleanup-failed", lambda: document.ClearSelection2(True))
    return result, handles
