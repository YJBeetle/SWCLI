"""Internal complete edge observation; no public edge handles are issued.

Single-solid ownership, exact native identity and unchanged state are mandatory.
Geometry evidence does not grant edit authority or topology-survival guarantees.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .windows import _com_value, _error
from .windows_edge_geometry import observe_edge_geometry
from .windows_entity_observation import (
    EntityObservationUnavailable, _identical, _integer, _sequence, _single_body,
)
from .windows_entity_references import capture_verified_reference
from .windows_feature_inspection import _same, _state

MAX_EDGES = 64


@dataclass(frozen=True)
class EdgeBinding:
    edge: Any
    body: Any
    reference: bytes


def observe_part_edges_with_handles(
    app: Any, document: Any, *, max_edges: int = MAX_EDGES
) -> Tuple[Dict[str, Any], List[EdgeBinding]]:
    """Publish the complete bounded set only after final identity/state checks.

    Final traversal may reorder wrappers: compare exact native membership, not
    array positions, bytes or geometric signatures. Unsupported curves remain
    explicit; a failed supported geometry read discards all records/bindings.
    """
    result: Dict[str, Any] = {"ok": False, "action": "entity.observe-edges"}
    before = None
    bindings: List[EdgeBinding] = []
    records: List[Dict[str, Any]] = []
    try:
        if isinstance(max_edges, bool) or not isinstance(max_edges, int) or not 1 <= max_edges <= MAX_EDGES:
            raise EntityObservationUnavailable("edge limit must be an integer from 1 to 64")
        if _integer(_com_value(document, "GetType"), "GetType") != 1:
            raise EntityObservationUnavailable("edge observation requires a part")
        before, edit_before, foreground_before = _state(app, document)
        result["observation"] = {"before": before, "unchanged": False}
        body = _single_body(document)
        count = _integer(_com_value(body, "GetEdgeCount"), "GetEdgeCount")
        if not 0 < count <= max_edges:
            raise EntityObservationUnavailable("native edge count is empty or exceeds the observation limit")
        edges = _sequence(_com_value(body, "GetEdges"), "GetEdges")
        if len(edges) != count:
            raise EntityObservationUnavailable("native edge array does not match the complete edge count")
        extension = _com_value(document, "Extension")
        for edge in edges:
            if not _identical(app, body, _com_value(edge, "GetBody")):
                raise EntityObservationUnavailable("native edge belongs to another body")
            if any(_identical(app, edge, previous.edge) for previous in bindings):
                raise EntityObservationUnavailable("native edge traversal repeats an entity")
            geometry = observe_edge_geometry(edge)
            reference = capture_verified_reference(app, extension, edge)
            if any(reference == previous.reference for previous in bindings):
                raise EntityObservationUnavailable("distinct native edges share an ambiguous reference")
            records.append(geometry)
            bindings.append(EdgeBinding(edge, body, reference))

        if (_integer(_com_value(body, "GetEdgeCount"), "GetEdgeCount") != count
                or not _identical(app, body, _single_body(document))):
            raise EntityObservationUnavailable("native body or edge count changed during observation")
        final_edges = _sequence(_com_value(body, "GetEdges"), "GetEdges")
        if len(final_edges) != count:
            raise EntityObservationUnavailable("native final edge array is incomplete")
        matched = set()
        for edge in final_edges:
            if not _identical(app, body, _com_value(edge, "GetBody")):
                raise EntityObservationUnavailable("native final edge belongs to another body")
            matches = [index for index, binding in enumerate(bindings)
                       if _identical(app, edge, binding.edge)]
            if len(matches) != 1 or matches[0] in matched:
                raise EntityObservationUnavailable("native complete edge set changed during observation")
            matched.add(matches[0])
    except Exception as exc:
        result["error"] = _error(exc)
    finally:
        if before is not None:
            try:
                after, edit_after, foreground_after = _state(app, document)
                result["observation"]["after"] = after
                unchanged = (before == after and _same(app, edit_before, edit_after)
                             and _same(app, foreground_before, foreground_after))
                result["observation"]["unchanged"] = unchanged
                if not unchanged:
                    raise EntityObservationUnavailable(
                        "configuration, stamp, modified flag, edit or foreground changed during observation"
                    )
            except Exception as exc:
                if "error" in result:
                    result.setdefault("warnings", []).append({
                        "code": "entity-observation-state-check-failed", "message": str(exc)
                    })
                else:
                    result["error"] = _error(exc)
    if "error" in result:
        return result, []
    result.update(ok=True, body_count=1, edge_count=len(records), edges=records)
    return result, bindings
