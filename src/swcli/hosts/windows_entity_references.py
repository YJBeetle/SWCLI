"""Internal persistent-reference binding on the owning COM STA.

A successful round trip proves live native identity only. Callers must separately
prove entity kind, document/body membership and unchanged configuration/stamp.
It is not a public serialized-reference API or a topology-survival guarantee.
"""

from __future__ import annotations

from typing import Any, Tuple

from .native_trace import native_call

MAX_REFERENCE_BYTES = 65536
_UNWRITTEN_STATUS = 2147483647


class EntityReferenceUnavailable(RuntimeError):
    """A reference, resolution state or exact native identity is unverified."""


def _reference_bytes(raw: Any) -> bytes:
    # Do not coerce arbitrary iterables, integers, strings or bools into bytes.
    # A bounded SAFEARRAY of UI1 arrives as bytes or a sequence of integers.
    if not isinstance(raw, (bytes, bytearray, tuple, list)):
        raise EntityReferenceUnavailable(
            "native persistent reference is not a byte array"
        )
    if not 0 < len(raw) <= MAX_REFERENCE_BYTES:
        raise EntityReferenceUnavailable("native persistent reference has invalid size")
    if isinstance(raw, (tuple, list)) and any(
        isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255
        for value in raw
    ):
        raise EntityReferenceUnavailable(
            "native persistent reference contains invalid bytes"
        )
    return bytes(raw)


def _resolve_native(extension: Any, reference: bytes) -> Tuple[Any, Any]:
    import pythoncom
    from win32com.client import VARIANT

    status = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, _UNWRITTEN_STATUS)
    encoded = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, reference)
    entity = native_call(
        "entity-reference",
        "IModelDocExtension.GetObjectByPersistReference3",
        lambda: extension.GetObjectByPersistReference3(encoded, status),
    )
    return entity, status.value


def resolve_verified_reference(extension: Any, reference: bytes) -> Any:
    """Require written native OK (zero), not an object with an unknown status.

    The native status is a bitmask. Deleted/suppressed/invalid, unknown and
    untouched BYREF states are never successful resolution, even with an object.
    """
    encoded = _reference_bytes(reference)
    entity, status = _resolve_native(extension, encoded)
    if isinstance(status, bool) or not isinstance(status, int) or status != 0:
        raise EntityReferenceUnavailable(
            "native persistent-reference resolution is not OK"
        )
    if entity is None:
        raise EntityReferenceUnavailable("native persistent-reference object is absent")
    return entity


def capture_verified_reference(app: Any, extension: Any, entity: Any) -> bytes:
    """Capture only after exact native identity survives an immediate round trip.

    Never substitute a nearby entity or infer identity from bytes, a face index,
    Python wrapper equality, a localized name or a geometric signature.
    """
    if entity is None:
        raise EntityReferenceUnavailable("cannot capture an absent native entity")
    raw = native_call(
        "entity-reference",
        "IModelDocExtension.GetPersistReference3",
        lambda: extension.GetPersistReference3(entity),
    )
    reference = _reference_bytes(raw)
    resolved = resolve_verified_reference(extension, reference)
    status = native_call(
        "entity-reference",
        "ISldWorks.IsSame",
        lambda: app.IsSame(entity, resolved),
    )
    if isinstance(status, bool) or not isinstance(status, int) or status != 1:
        raise EntityReferenceUnavailable(
            "persistent-reference round trip changed native identity"
        )
    return reference
