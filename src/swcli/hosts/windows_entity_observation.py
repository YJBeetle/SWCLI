"""Internal complete, read-only face observation of a small single-solid part.

No public handles are assigned here. The bounded first slice deliberately fails
on multi/surface bodies and over-limit enumeration instead of dropping geometry.
Native references remain private, and approximate areas are labelled as such.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, List, Tuple

from .native_trace import native_call
from .windows import _com_value, _error
from .windows_entity_references import capture_verified_reference
from .windows_entity_geometry import observe_surface_geometry
from .windows_feature_inspection import _state, _same

MAX_FACES = 64


class EntityObservationUnavailable(RuntimeError):
    """Complete entity ownership, geometry or unchanged state is unverified."""


@dataclass(frozen=True)
class FaceBinding:
    face: Any
    body: Any
    reference: bytes


def _integer(value: Any, member: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EntityObservationUnavailable(f"native {member} is not an integer")
    return value


def _sequence(value: Any, member: str) -> Tuple[Any, ...]:
    if value is None:
        return ()
    if not isinstance(value, (tuple, list)) or any(item is None for item in value):
        raise EntityObservationUnavailable(f"native {member} is not an object array")
    return tuple(value)


def _single_body(document: Any) -> Any:
    solids = _sequence(
        native_call(
            "entity-observation",
            "IModelDoc2.GetBodies2(solids)",
            lambda: document.GetBodies2(0, False),
        ),
        "GetBodies2 solids",
    )
    surfaces = _sequence(
        native_call(
            "entity-observation",
            "IModelDoc2.GetBodies2(surfaces)",
            lambda: document.GetBodies2(1, False),
        ),
        "GetBodies2 surfaces",
    )
    if len(solids) != 1 or surfaces:
        raise EntityObservationUnavailable(
            "face observation requires one solid and no surface bodies"
        )
    return solids[0]


def _identical(app: Any, first: Any, second: Any) -> bool:
    if first is None or second is None:
        raise EntityObservationUnavailable("native ownership object is absent")
    status = _integer(
        native_call(
            "entity-observation", "ISldWorks.IsSame", lambda: app.IsSame(first, second)
        ),
        "IsSame",
    )
    if status not in (0, 1):
        raise EntityObservationUnavailable(
            "native entity identity is unsupported or unknown"
        )
    return status == 1


def _geometry(face: Any) -> Dict[str, Any]:
    surface = _com_value(face, "GetSurface")
    if surface is None:
        raise EntityObservationUnavailable("native face surface is absent")
    plane = _com_value(surface, "IsPlane")
    cylinder = _com_value(surface, "IsCylinder")
    if (
        not isinstance(plane, bool)
        or not isinstance(cylinder, bool)
        or (plane and cylinder)
    ):
        raise EntityObservationUnavailable(
            "native surface classification is unreadable"
        )
    area = _com_value(face, "GetArea")
    if (
        isinstance(area, bool)
        or not isinstance(area, (int, float))
        or not math.isfinite(area)
        or area <= 0
    ):
        raise EntityObservationUnavailable("native face area is unavailable")
    area_mm2 = area * 1e6
    if not math.isfinite(area_mm2):
        raise EntityObservationUnavailable("native face area conversion overflowed")
    kind = "plane" if plane else "cylinder" if cylinder else "unclassified"
    return {
        "kind": "face",
        "surface_kind": kind,
        "area_mm2": area_mm2,
        "area_accuracy": "approximate",
        "surface_geometry": observe_surface_geometry(face, surface, kind),
    }


def observe_part_faces_with_handles(
    app: Any, document: Any, *, max_faces: int = MAX_FACES
) -> Tuple[Dict[str, Any], List[FaceBinding]]:
    """Return private bindings only after the entire read and state check pass.

    The 64-face limit bounds exact pairwise duplicate verification in this first
    slice and its public catalog. This is not a scalable topology API.
    """
    result: Dict[str, Any] = {"ok": False, "action": "entity.observe-faces"}
    before = None
    records: List[Dict[str, Any]] = []
    bindings: List[FaceBinding] = []
    try:
        if (
            isinstance(max_faces, bool)
            or not isinstance(max_faces, int)
            or not 1 <= max_faces <= MAX_FACES
        ):
            raise EntityObservationUnavailable(
                "face limit must be an integer from 1 to 64"
            )
        if _integer(_com_value(document, "GetType"), "GetType") != 1:
            raise EntityObservationUnavailable("face observation requires a part")
        before, edit_before, foreground_before = _state(app, document)
        result["observation"] = {"before": before, "unchanged": False}
        body = _single_body(document)
        count = _integer(_com_value(body, "GetFaceCount"), "GetFaceCount")
        if not 0 < count <= max_faces:
            raise EntityObservationUnavailable(
                "native face count is empty or exceeds the observation limit"
            )
        faces = _sequence(_com_value(body, "GetFaces"), "GetFaces")
        if len(faces) != count:
            raise EntityObservationUnavailable(
                "native face array does not match the complete face count"
            )
        extension = _com_value(document, "Extension")
        for face in faces:
            if not _identical(app, body, _com_value(face, "GetBody")):
                raise EntityObservationUnavailable(
                    "native face belongs to another body"
                )
            # Byte equality alone is not entity identity. Check every earlier
            # exact face before publishing the complete bounded observation.
            if any(_identical(app, face, previous.face) for previous in bindings):
                raise EntityObservationUnavailable(
                    "native face traversal repeats an entity"
                )
            geometry = _geometry(face)
            reference = capture_verified_reference(app, extension, face)
            if any(reference == previous.reference for previous in bindings):
                raise EntityObservationUnavailable(
                    "distinct native faces share an ambiguous reference"
                )
            records.append(geometry)
            bindings.append(FaceBinding(face, body, reference))
        if _integer(
            _com_value(body, "GetFaceCount"), "GetFaceCount"
        ) != count or not _identical(app, body, _single_body(document)):
            raise EntityObservationUnavailable(
                "native body or face count changed during observation"
            )
    except Exception as exc:
        result["error"] = _error(exc)
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
                    raise EntityObservationUnavailable(
                        "configuration, stamp, modified flag, edit or foreground changed during observation"
                    )
            except Exception as exc:
                if "error" in result:
                    result.setdefault("warnings", []).append(
                        {
                            "code": "entity-observation-state-check-failed",
                            "message": str(exc),
                        }
                    )
                else:
                    result["error"] = _error(exc)
    if "error" in result:
        return result, []
    result.update(ok=True, body_count=1, face_count=len(records), faces=records)
    return result, bindings
