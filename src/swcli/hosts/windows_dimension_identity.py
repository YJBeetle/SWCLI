"""Exact live COM dimension identity, scoped to the owning worker STA.

SOLIDWORKS IsSame can return swObjectUnsupported (2) for dimensions. Only that
documented outcome permits a canonical IUnknown comparison. Exceptions, busy
hosts and unknown enum values never mean different objects. No name, Python
wrapper identity or persisted pointer is used.
"""

from __future__ import annotations

from typing import Any


class DimensionIdentityUnavailable(RuntimeError):
    """Neither the native CAD comparison nor canonical COM identity is known."""


def _query_iunknown(dimension: Any) -> Any:
    try:
        import pythoncom

        unknown = dimension._oleobj_.QueryInterface(pythoncom.IID_IUnknown)
    except (ImportError, AttributeError) as exc:
        raise DimensionIdentityUnavailable(
            "native dimension canonical COM identity is unavailable"
        ) from exc
    if unknown is None:
        raise DimensionIdentityUnavailable("canonical COM identity is absent")
    return unknown


def same_dimension(app: Any, first: Any, second: Any) -> bool:
    """Compare two live dimensions, retaining both QI references during equality.

    PyIUnknown equality itself follows COM's canonical IUnknown identity rules;
    it is not Python object's `is` or a guessed dimension-name match.
    """
    status = app.IsSame(first, second)
    if isinstance(status, bool) or not isinstance(status, int):
        raise DimensionIdentityUnavailable(
            "native dimension comparison is not an integer"
        )
    if status in (0, 1):
        return status == 1
    if status != 2:
        raise DimensionIdentityUnavailable(
            "native dimension comparison is an unknown enum"
        )
    try:
        first_unknown = _query_iunknown(first)
        second_unknown = _query_iunknown(second)
        equal = first_unknown == second_unknown
    except DimensionIdentityUnavailable:
        raise
    except Exception as exc:
        # A query/equality failure can originate from either interface. Do not
        # let a registry assume it proves that its old proxy alone is expired.
        raise DimensionIdentityUnavailable(
            f"canonical dimension COM identity could not be compared: {exc}"
        ) from exc
    if not isinstance(equal, bool):
        raise DimensionIdentityUnavailable(
            "canonical COM identity comparison is unreadable"
        )
    return equal
