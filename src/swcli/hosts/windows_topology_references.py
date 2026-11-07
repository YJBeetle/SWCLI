"""Read-only exact census resolution on the existing owning COM worker STA.

No bytes/geometry/array-position comparison proves identity. Each old native
reference must resolve OK and map exactly once onto the entire current census.
"""

from __future__ import annotations

from typing import Any

from ..topology_references import _b64, _unb64, encode_reference
from .windows_entity_observation import _identical
from .windows_entity_references import _resolve_native


class PersistentReferenceScopeMismatch(RuntimeError):
    """The saved path or exact configuration is outside the envelope scope."""


class PersistentReferenceTopologyChanged(RuntimeError):
    """Complete current topology cannot be proven bijective to the snapshot."""


class PersistentReferenceNativeState(RuntimeError):
    """Native resolution is deleted/suppressed/invalid/unknown, never success."""

    def __init__(self, status):
        self.native_status = status if type(status) is int else None
        super().__init__("native persistent-reference state is not OK: " + repr(status))


def native_entity(binding):
    return binding.face if hasattr(binding, "face") else binding.edge


def unique_index(app, entity, bindings):
    matches = [index for index, binding in enumerate(bindings)
               if _identical(app, entity, native_entity(binding))]
    if len(matches) != 1:
        raise PersistentReferenceTopologyChanged("native entity membership is absent or ambiguous")
    return matches[0]


def make_reference(app, target, *, path, state, kind, faces, edges):
    target_index = unique_index(app, native_entity(target), faces if kind == "face" else edges)
    if not _identical(app, faces[0].body, edges[0].body):
        raise PersistentReferenceTopologyChanged("face and edge observations span different bodies")
    payload = dict(version=1, document_path=path, configuration=state["configuration"],
                   captured_update_stamp=state["update_stamp"], kind=kind,
                   target_index=target_index,
                   faces=[_b64(b.reference) for b in faces],
                   edges=[_b64(b.reference) for b in edges])
    return encode_reference(payload)


def verify_reference(app, extension, payload, *, faces, edges):
    if not _identical(app, faces[0].body, edges[0].body):
        raise PersistentReferenceTopologyChanged("face and edge observations span different bodies")
    target = None
    # Resolve the requested target first, so deletion retains its original native
    # status even if a subsequent census/count check would also fail.
    kind = payload["kind"]
    target_ref = payload[kind + "s"][payload["target_index"]]
    entity, status = _resolve_native(extension, _unb64(target_ref))
    if type(status) is not int or status != 0 or entity is None:
        raise PersistentReferenceNativeState(status)
    target = unique_index(app, entity, faces if kind == "face" else edges)
    for field, bindings in (("faces", faces), ("edges", edges)):
        if len(payload[field]) != len(bindings):
            raise PersistentReferenceTopologyChanged("complete face/edge topology counts changed")
        seen = set()
        for index, ref in enumerate(payload[field]):
            # Reuse the first target result; never retry native resolution.
            if field == kind + "s" and index == payload["target_index"]:
                match = target
            else:
                resolved, status = _resolve_native(extension, _unb64(ref))
                if type(status) is not int or status != 0 or resolved is None:
                    raise PersistentReferenceNativeState(status)
                match = unique_index(app, resolved, bindings)
            if match in seen:
                raise PersistentReferenceTopologyChanged("multiple old references map to one current entity")
            seen.add(match)
    return target
