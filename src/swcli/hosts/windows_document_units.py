"""Document length display units, independent of modeling's millimeter inputs."""

from typing import Any, Optional

from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _state, _verify_metadata_state, _require_writable
from .windows_feature_inspection import _same


LENGTH_UNITS = {"mm": 0, "inch": 3}
DECIMAL_PLACES_MIN = 0
DECIMAL_PLACES_MAX = 8
DECIMAL_FRACTION_BASE = 1


class DocumentUnitsConflict(RuntimeError):
    """The selected document's length display no longer matches the caller's read."""


def _read_units(document: Any) -> dict:
    values = native_call("document-units", "IModelDoc2.GetUnits",
                         lambda: _com_value(document, "GetUnits"))
    if (not isinstance(values, (tuple, list)) or len(values) != 5
            or any(type(value) is not int or not -32768 <= value <= 32767 for value in values)):
        raise RuntimeError("native document length units are unreadable")
    length_unit = next((name for name, code in LENGTH_UNITS.items() if code == values[0]), "other")
    return {
        "length_unit": length_unit,
        "decimal_places": values[3],
        "native_units": {
            "length_unit": values[0],
            "fraction_base": values[1],
            "fraction_value": values[2],
            "significant_digits": values[3],
            "round_to_fraction": values[4],
        },
    }


def _verify_edit_state(app: Any, document: Any, before: Any) -> None:
    after = _com_value(_com_value(document, "SketchManager"), "ActiveSketch")
    if not _same(app, before, after):
        raise RuntimeError("document edit state changed during length unit operation")


def read_document_units_windows(*, app: Any, document: Any) -> dict:
    result = {"ok": False, "action": "document.units"}
    try:
        state = _state(document)
        foreground = _com_value(app, "ActiveDoc")
        edit = _com_value(_com_value(document, "SketchManager"), "ActiveSketch")
        units = _read_units(document)
        _verify_edit_state(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        result.update(ok=True, units=units)
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def set_document_units_windows(
    *, app: Any, document: Any, length_unit: Optional[str], decimal_places: Optional[int],
    expected_length_unit: Optional[str] = None, expected_decimal_places: Optional[int] = None,
) -> dict:
    result = {"ok": False, "action": "document.units-set",
              "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        _require_writable(document)
        if length_unit is None and decimal_places is None:
            raise ValueError("select a length unit or decimal places")
        if length_unit is not None and length_unit not in LENGTH_UNITS:
            raise ValueError("length unit must be mm or inch")
        if (decimal_places is not None and (type(decimal_places) is not int
                or not DECIMAL_PLACES_MIN <= decimal_places <= DECIMAL_PLACES_MAX)):
            raise ValueError("decimal places must be an integer between 0 and 8")
        state = _state(document)
        foreground = _com_value(app, "ActiveDoc")
        edit = _com_value(_com_value(document, "SketchManager"), "ActiveSketch")
        before = _read_units(document)
        result["before"] = before
        if expected_length_unit is not None and before["length_unit"] != expected_length_unit:
            raise DocumentUnitsConflict("document length unit no longer matches the expected value")
        if expected_decimal_places is not None and before["decimal_places"] != expected_decimal_places:
            raise DocumentUnitsConflict("document decimal places no longer match the expected value")
        unit = before["length_unit"] if length_unit is None else length_unit
        places = before["decimal_places"] if decimal_places is None else decimal_places
        native = before["native_units"]
        if unit not in LENGTH_UNITS or not DECIMAL_PLACES_MIN <= places <= DECIMAL_PLACES_MAX:
            raise ValueError("the requested document length format is outside the supported decimal profile")
        desired = {**native, "length_unit": LENGTH_UNITS[unit], "significant_digits": places}
        _verify_edit_state(app, document, edit)
        _verify_metadata_state(app, document, state, foreground, changed=False)
        if native == desired:
            result.update(ok=True, before=before, units=before, changed=False)
            return result
        if (edit is not None or before["length_unit"] not in LENGTH_UNITS
                or native["fraction_base"] != DECIMAL_FRACTION_BASE
                or native["fraction_value"] != 8 or native["round_to_fraction"] != 0):
            raise ValueError("the current document length format is outside the supported decimal profile")
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        native_call("document-units", "IModelDoc2.SetUnits",
                    lambda: document.SetUnits(
                        desired["length_unit"], desired["fraction_base"],
                        desired["fraction_value"], desired["significant_digits"],
                        bool(desired["round_to_fraction"]),
                    ))
        post_setter_state = _state(document)
        after = _read_units(document)
        if after["native_units"] != desired:
            raise RuntimeError("native document length units did not round-trip the requested values")
        _verify_edit_state(app, document, edit)
        _verify_metadata_state(app, document, post_setter_state, foreground, changed=False)
        _verify_metadata_state(app, document, state, foreground, changed=True)
        _verify_edit_state(app, document, edit)
        result.update(ok=True, units=after, changed=True)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
