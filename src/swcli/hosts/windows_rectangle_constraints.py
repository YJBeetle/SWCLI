"""Explicit internal fixed-center intent on the owning COM STA.

Never fix a corner, whole rectangle or unverified coordinate candidate. Exact
partial relation handles on failure are evidence, not rollback or public IDs.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .native_trace import native_call
from .windows import _com_value
from .windows_dimension_discovery import _profile, _state
from .windows_dimensions import (
    _DimensionError,
    _configuration,
    _failure,
    _same,
    _variant,
)
from .windows_rectangle_center import (
    RectangleCenter,
    _FIXED,
    _integer,
    _relation,
    observe_rectangle_center,
)
from .windows_rectangle_dimensions import _verify


def _solver(sketch: Any, *, after: bool) -> int:
    status = _integer(sketch, "GetConstrainedStatus")
    if status not in (2, 3):
        raise _DimensionError(
            "ConstraintVerificationFailed" if after else "UnsupportedCenterConstraint",
            "require an observable under/fully constrained sketch with autosolve enabled",
        )
    return status


def _owned_edit(app: Any, manager: Any, sketch: Any) -> None:
    active = _com_value(manager, "ActiveSketch")
    if active is None or not _same(app, active, sketch):
        raise _DimensionError(
            "ConstraintVerificationFailed",
            "the exact owned sketch edit is no longer active",
        )


def _verify_center(
    app: Any, sketch: Any, before: RectangleCenter
) -> Tuple[RectangleCenter, Dict[str, Any]]:
    current = observe_rectangle_center(app, sketch)
    geometry = _verify(
        current.profile,
        before.profile.width_mm,
        before.profile.height_mm,
        before.profile.center_mm,
    )
    if current.point_id != before.point_id or current.diagonals != before.diagonals:
        raise _DimensionError(
            "ConstraintVerificationFailed", "native center topology changed"
        )
    if not geometry["passed"]:
        raise _DimensionError(
            "ConstraintVerificationFailed", "rectangle size or center changed"
        )
    return current, geometry


def fix_rectangle_center_windows_with_handle(
    *, app: Any, document: Any, sketch_feature: Any
) -> Tuple[Dict[str, Any], Optional[Any]]:
    """Fix the verified live center in place; no implicit size edit or retry.

    First slice: unabsorbed five-point center rectangles with exactly two native
    diagonal coincidences and optionally one existing exact FIXED relation.
    Existing fixes are a verified read-only no-op, not a second relation.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "action": "sketch.center.fix",
        "created": False,
    }
    relation = sketch = manager = None
    entered = selected = mutation_attempted = False
    try:
        if _integer(document, "GetType") != 1:
            raise _DimensionError(
                "UnsupportedDocumentType", "center constraints require a part"
            )
        state, edit = _state(document)
        manager = _com_value(document, "SketchManager")
        if edit is not None:
            raise _DimensionError(
                "SketchEditInProgress", "finish the existing sketch edit first"
            )
        feature, sketch = _profile(app, document, sketch_feature)
        if _com_value(feature, "GetOwnerFeature") is not None:
            raise _DimensionError(
                "SketchUnavailable", "center fixing requires an unabsorbed profile"
            )
        before = observe_rectangle_center(app, sketch)
        result["center_before"] = before.evidence()
        result["constraint_status_before"] = _solver(sketch, after=False)
        observed_state, observed_edit = _state(document)
        if observed_state != state or observed_edit is not None:
            raise _DimensionError(
                "ConstraintObservationUnavailable",
                "document state changed during preflight",
            )
        if before.fixed_relation is not None:
            current, verification = _verify_center(app, sketch, before)
            status = _solver(sketch, after=True)
            after, edit_after = _state(document)
            if (
                after != state
                or edit_after is not None
                or current.fixed_relation is None
            ):
                raise _DimensionError(
                    "ConstraintObservationUnavailable",
                    "native state changed during existing-fix observation",
                )
            relation = current.fixed_relation
            result.update(
                center=current.evidence(),
                geometry_verification=verification,
                constraint_status=status,
                editing=False,
                ok=True,
            )
            return result, relation

        if result["constraint_status_before"] == 3:
            raise _DimensionError(
                "UnsupportedCenterConstraint",
                "do not add a redundant fix to a fully constrained profile",
            )
        selected = True
        document.ClearSelection2(True)
        if feature.Select2(False, 0) is not True:
            raise _DimensionError(
                "SketchSelectionFailed", "could not select the exact profile"
            )
        entered = True
        native_call(
            "rectangle-center",
            "ModelDoc2.EditSketch",
            lambda: _com_value(document, "EditSketch"),
        )
        active = _com_value(manager, "ActiveSketch")
        if active is None or not _same(app, active, sketch):
            raise _DimensionError(
                "SketchUnavailable", "did not enter the exact profile edit"
            )
        current, verification = _verify_center(app, sketch, before)
        if (
            current.fixed_relation is not None
            or _configuration(document) != state["configuration"]
        ):
            raise _DimensionError(
                "ConstraintObservationUnavailable",
                "native position/configuration changed before relation creation",
            )
        _solver(sketch, after=False)
        native_manager = _com_value(sketch, "RelationManager")
        if native_manager is None:
            raise _DimensionError(
                "ConstraintObservationUnavailable",
                "native relation manager is unavailable",
            )
        entities = _variant("dispatch-array", (current.point,))
        _owned_edit(app, manager, sketch)
        mutation_attempted = True
        relation = native_call(
            "rectangle-center",
            "SketchRelationManager.AddRelation(FIXED)",
            lambda: native_manager.AddRelation(entities, _FIXED),
        )
        if relation is None:
            raise _DimensionError(
                "ConstraintCreationFailed", "native creation returned no relation"
            )
        _owned_edit(app, manager, sketch)
        if _relation(app, sketch, relation, current) != (_FIXED, None):
            raise _DimensionError(
                "ConstraintVerificationFailed",
                "creation did not return an exact fixed-center relation",
            )
        current, verification = _verify_center(app, sketch, before)
        if current.fixed_relation is None:
            raise _DimensionError(
                "ConstraintVerificationFailed",
                "created relation is absent from the center",
            )
        result["center_in_edit"] = current.evidence()
        _solver(sketch, after=True)
        if _configuration(document) != state["configuration"]:
            raise _DimensionError(
                "ConstraintVerificationFailed",
                "configuration changed during constraint creation",
            )
        _owned_edit(app, manager, sketch)
        native_call(
            "rectangle-center",
            "SketchManager.InsertSketch(exit)",
            lambda: manager.InsertSketch(True),
        )
        if _com_value(manager, "ActiveSketch") is not None:
            raise _DimensionError(
                "ConstraintVerificationFailed", "profile editing remained active"
            )
        entered = False
        current, verification = _verify_center(app, sketch, before)
        if (
            current.fixed_relation is None
            or _configuration(document) != state["configuration"]
        ):
            raise _DimensionError(
                "ConstraintVerificationFailed",
                "fixed center/configuration did not survive sketch exit",
            )
        result.update(
            center=current.evidence(),
            geometry_verification=verification,
            constraint_status=_solver(sketch, after=True),
            editing=False,
            created=True,
            ok=True,
        )
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
                result["ok"] = False
                if "error" not in result:
                    _failure(
                        result, _DimensionError("ConstraintCleanupFailed", str(exc))
                    )
                if mutation_attempted:
                    result["modification_may_have_happened"] = True

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
        if selected:
            cleanup("selection-cleanup-failed", lambda: document.ClearSelection2(True))
    return result, relation
