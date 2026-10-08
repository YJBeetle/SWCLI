"""Strict read-only center attachment, not arbitrary constraint discovery.

GetID pairs identify points/lines only within this exact sketch and entity kind.
They are snapshot keys, not persistent references or public handles. IsSame on
point wrappers is not used: native SW2025 can return zero for the same point.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Optional, Tuple

from .windows import _com_value
from .windows_dimension_discovery import _profile, _state
from .windows_dimensions import _DimensionError, _failure, _same
from .windows_rectangle_dimensions import _geometry
from .windows_rectangle_profiles import (
    RectangleObservationError,
    RectangleProfile,
    _point_mm,
    observe_rectangle_profile,
)

_TOLERANCE_MM = 1e-6
_LIMIT = 64
_COINCIDENT = 9
_FIXED = 17
NativeKey = Tuple[int, int]


def _unavailable(message: str) -> _DimensionError:
    return _DimensionError("ConstraintObservationUnavailable", message)


def _unsupported(message: str) -> _DimensionError:
    return _DimensionError("UnsupportedCenterConstraint", message)


def _integer(obj: Any, member: str) -> int:
    value = _com_value(obj, member)
    if type(value) is not int:
        raise _unavailable(f"native {member} is not an integer")
    return value


def _collection(obj: Any, member: str) -> Tuple[Any, ...]:
    value = _com_value(obj, member)
    if not isinstance(value, (tuple, list)) or len(value) > _LIMIT:
        raise _unavailable(f"native {member} is unreadable or exceeds its limit")
    if any(item is None for item in value):
        raise _unavailable(f"native {member} contains an unavailable entity")
    return tuple(value)


def _key(app: Any, sketch: Any, entity: Any) -> NativeKey:
    if entity is None:
        raise _unavailable("native sketch entity is unavailable")
    owner = _com_value(entity, "GetSketch")
    if owner is None or not _same(app, owner, sketch):
        raise _unavailable("native entity has a different or unreadable owning sketch")
    pair = _com_value(entity, "GetID")
    if (
        not isinstance(pair, (tuple, list))
        or len(pair) != 2
        or any(
            type(value) is not int or not -(2**31) <= value < 2**31 for value in pair
        )
    ):
        raise _unavailable("native sketch-local ID is not a pair of 32-bit integers")
    return tuple(pair)


def _point(app: Any, sketch: Any, point: Any) -> Tuple[NativeKey, Tuple[float, ...]]:
    key = _key(app, sketch, point)
    if _integer(point, "Type") not in (0, 1):
        raise _unsupported(
            "only internal/user points in this exact sketch are supported"
        )
    return key, _point_mm(point)


def _matches(first: Tuple[float, ...], second: Tuple[float, ...]) -> bool:
    return all(
        math.isclose(a, b, rel_tol=0, abs_tol=_TOLERANCE_MM)
        for a, b in zip(first, second)
    )


def _line(app: Any, sketch: Any, line: Any) -> Tuple[Any, ...]:
    key = _key(app, sketch, line)
    if _integer(line, "GetType") != 0:
        raise _unsupported("center attachment requires exact native straight lines")
    construction = _com_value(line, "ConstructionGeometry")
    if type(construction) is not bool:
        raise _unavailable("native construction flag is not a boolean")
    ends = tuple(
        _point(app, sketch, _com_value(line, member))
        for member in ("GetStartPoint2", "GetEndPoint2")
    )
    return key, construction, tuple(sorted(ends))


@dataclass(frozen=True)
class RectangleCenter:
    profile: RectangleProfile
    point: Any
    point_id: NativeKey
    diagonals: Dict[NativeKey, Tuple[Any, ...]]
    fixed_relation: Optional[Any]

    def evidence(self) -> Dict[str, Any]:
        return {
            "method": "sketch-local-center-relations",
            "attached_to_both_diagonals": True,
            "fixed": self.fixed_relation is not None,
            "native_point_id": list(self.point_id),
            "native_diagonal_ids": [list(key) for key in sorted(self.diagonals)],
            "identity_scope": "exact-sketch-and-entity-kind-snapshot",
            "geometry": _geometry(self.profile),
        }


def _relation(
    app: Any, sketch: Any, relation: Any, center: RectangleCenter
) -> Tuple[int, Optional[NativeKey]]:
    kind = _integer(relation, "GetRelationType")
    suppressed = _com_value(relation, "Suppressed")
    if type(suppressed) is not bool:
        raise _unavailable("native relation suppression is not a boolean")
    if suppressed:
        raise _unsupported("do not infer or override suppressed center relations")
    if kind not in (_COINCIDENT, _FIXED):
        raise _unsupported(
            "the center has additional unsupported positioning relations"
        )
    count = _integer(relation, "GetEntitiesCount")
    types = _collection(relation, "GetEntitiesType")
    entities = _collection(relation, "GetEntities")
    definitions = _collection(relation, "GetDefinitionEntities2")
    if count != len(types) or count != len(entities) or count != len(definitions):
        raise _unavailable("native relation arrays disagree with the entity count")
    if any(type(value) is not int for value in types):
        raise _unavailable("native relation entity types are not integers")
    expected = [2] if kind == _FIXED else [2, 3]
    if sorted(types) != expected:
        raise _unsupported(
            "center relations must bind one point to each diagonal or fix only that point"
        )
    diagonal_key = None
    for group in (entities, definitions):
        for entity, entity_type in zip(group, types):
            if entity_type == 2:
                key, coordinates = _point(app, sketch, entity)
                if key != center.point_id or not _matches(
                    coordinates, (*center.profile.center_mm, 0)
                ):
                    raise _unsupported(
                        "native relation is not attached to the exact center point"
                    )
            else:
                line = _line(app, sketch, entity)
                if center.diagonals.get(line[0]) != line:
                    raise _unsupported(
                        "native relation is not attached to an exact profile diagonal"
                    )
                if diagonal_key is not None and diagonal_key != line[0]:
                    raise _unsupported(
                        "relation definition and internal diagonal disagree"
                    )
                diagonal_key = line[0]
    return kind, diagonal_key


def observe_rectangle_center(app: Any, sketch: Any) -> RectangleCenter:
    """Prove a five-point center rectangle with two live diagonal relations.

    Additional/external/origin constraints are deliberately outside this slice;
    never select a loose point merely because its coordinates match the center.
    """
    try:
        profile = observe_rectangle_profile(sketch)
        segments = _collection(sketch, "GetSketchSegments")
        if len(segments) != 6 or profile.construction_segment_count != 2:
            raise _unsupported(
                "require four profile sides and two construction diagonals"
            )
        lines = [_line(app, sketch, segment) for segment in segments]
        if len({line[0] for line in lines}) != len(lines):
            raise _unavailable("native straight-line IDs are duplicated")
        min_x, min_y, max_x, max_y = profile.bounds_mm
        corners = (
            (min_x, min_y, 0),
            (max_x, min_y, 0),
            (max_x, max_y, 0),
            (min_x, max_y, 0),
        )
        corner_keys = {}
        for _, construction, ends in lines:
            if construction:
                continue
            for key, coordinates in ends:
                matches = [
                    i
                    for i, corner in enumerate(corners)
                    if _matches(coordinates, corner)
                ]
                if len(matches) != 1:
                    raise _unsupported(
                        "native endpoint is not one exact profile corner"
                    )
                index = matches[0]
                if corner_keys.setdefault(index, key) != key:
                    raise _unsupported(
                        "coincident coordinates do not prove connected native corners"
                    )
        if len(corner_keys) != 4 or len(set(corner_keys.values())) != 4:
            raise _unavailable("native rectangle corner IDs are ambiguous")
        diagonals = {line[0]: line for line in lines if line[1]}
        opposite_pairs = set()
        for _, _, ends in diagonals.values():
            indices = []
            for key, coordinates in ends:
                matches = [
                    i
                    for i, native in corner_keys.items()
                    if native == key and _matches(coordinates, corners[i])
                ]
                if len(matches) != 1:
                    raise _unsupported(
                        "construction endpoints are not exact profile corners"
                    )
                indices.append(matches[0])
            opposite_pairs.add(tuple(sorted(indices)))
        if opposite_pairs != {(0, 2), (1, 3)}:
            raise _unsupported(
                "construction lines do not join both pairs of opposite corners"
            )
        points = _collection(sketch, "GetSketchPoints2")
        observed = [(point, *_point(app, sketch, point)) for point in points]
        if len(observed) != 5 or len({key for _, key, _ in observed}) != 5:
            raise _unsupported("require four exact corner points and one unique center")
        candidates = [
            (point, key)
            for point, key, coordinates in observed
            if _matches(coordinates, (*profile.center_mm, 0))
        ]
        if len(candidates) != 1:
            raise _unsupported("the center point is missing or ambiguous")
        point, point_id = candidates[0]
        if _integer(point, "Type") != 1 or {key for _, key, _ in observed} != {
            point_id,
            *corner_keys.values(),
        }:
            raise _unsupported(
                "the point collection is not this exact center rectangle"
            )
        for _, key, coordinates in observed:
            if key != point_id and not any(
                key == native and _matches(coordinates, corners[index])
                for index, native in corner_keys.items()
            ):
                raise _unsupported("native point and profile corner geometry disagree")
        center = RectangleCenter(profile, point, point_id, diagonals, None)
        count = _integer(point, "GetRelationsCount")
        relations = _collection(point, "GetRelations")
        if count != len(relations):
            raise _unavailable("native center relation count and collection disagree")
        attached = []
        fixed = []
        for relation in relations:
            kind, diagonal = _relation(app, sketch, relation, center)
            if kind == _FIXED:
                fixed.append(relation)
            else:
                attached.append(diagonal)
        if len(attached) != 2 or set(attached) != set(diagonals) or len(fixed) > 1:
            raise _unsupported(
                "the center does not have exactly two diagonal relations and at most one fix"
            )
        return RectangleCenter(
            profile, point, point_id, diagonals, fixed[0] if fixed else None
        )
    except RectangleObservationError as exc:
        raise _DimensionError(exc.code, str(exc)) from exc


def inspect_rectangle_center_windows(
    *, app: Any, document: Any, sketch_feature: Any
) -> Dict[str, Any]:
    """Internal read: no activation, edit, selection, rebuild or public handle."""
    result: Dict[str, Any] = {"ok": False, "action": "sketch.center.inspect"}
    before = edit_before = None
    try:
        if _integer(document, "GetType") != 1:
            raise _DimensionError(
                "UnsupportedDocumentType", "center relations require a part"
            )
        before, edit_before = _state(document)
        result["observation"] = {"before": before, "unchanged": False}
        _, sketch = _profile(app, document, sketch_feature)
        result["center"] = observe_rectangle_center(app, sketch).evidence()
        result["ok"] = True
    except Exception as exc:
        _failure(result, exc)
    finally:
        if before is not None:
            try:
                after, edit_after = _state(document)
                unchanged = before == after and (
                    edit_before is None
                    and edit_after is None
                    or edit_before is not None
                    and edit_after is not None
                    and _same(app, edit_before, edit_after)
                )
                result["observation"].update(after=after, unchanged=unchanged)
                if not unchanged:
                    raise _unavailable(
                        "native document state changed during center observation"
                    )
            except Exception as exc:
                result["ok"] = False
                if "error" not in result:
                    _failure(result, exc)
                else:
                    result.setdefault("warnings", []).append(
                        {"code": "center-state-observation-failed", "message": str(exc)}
                    )
    return result
