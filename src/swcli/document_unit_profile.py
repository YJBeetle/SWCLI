"""Bounded document-unit profile; changed public writes await CI calibration."""
from copy import deepcopy
import hashlib
import json

PROFILE = "document-units-v1"
SYSTEMS = {"cgs": 1, "mks": 2, "ips": 3, "custom": 4, "mmgs": 5}
LENGTHS = {"mm": 0, "cm": 1, "m": 2, "inch": 3, "feet": 4, "feet_inches": 5,
           "angstrom": 6, "nm": 7, "micron": 8, "mil": 9, "microinch": 10}
ANGLES = {"degrees": 0, "degrees_minutes": 1, "degrees_minutes_seconds": 2, "radians": 3}
MASSES = {"mg": 1, "g": 2, "kg": 3, "lb": 4}
VOLUMES = dict(zip(("angstrom3", "nm3", "micron3", "mm3", "cm3", "m3", "microinch3", "mil3", "inch3", "feet3", "microliter", "milliliter", "centiliter", "deciliter", "liter", "hectoliter", "us_fluid_ounce", "us_pint", "us_gallon", "imperial_gallon", "imperial_yard3"), range(1, 22)))
# IDs were exported from an installed SOLIDWORKS 2025 swconst.tlb. A native
# calibration re-exports every required symbol; presence is not write evidence.
FIELDS = {
    "system": {"symbol": "swUnitSystem", "id": 263, "enum": SYSTEMS, "targets": tuple(SYSTEMS)},
    "linear.unit": {"symbol": "swUnitsLinear", "id": 47, "enum": LENGTHS, "targets": ("mm", "inch")},
    "linear.precision": {"symbol": "swUnitsLinearDecimalPlaces", "id": 49},
    "angular.unit": {"symbol": "swUnitsAngular", "id": 51, "enum": ANGLES, "targets": ("degrees", "radians")},
    "angular.precision": {"symbol": "swUnitsAngularDecimalPlaces", "id": 52},
    "mass_properties.length_unit": {"symbol": "swUnitsMassPropLength", "id": 258, "enum": LENGTHS, "targets": ("mm", "m"), "custom_only": True},
    "mass_properties.mass_unit": {"symbol": "swUnitsMassPropMass", "id": 259, "enum": MASSES, "targets": ("g", "kg"), "custom_only": True},
    "mass_properties.volume_unit": {"symbol": "swUnitsMassPropVolume", "id": 260, "enum": VOLUMES, "targets": ("mm3", "m3"), "custom_only": True},
    "mass_properties.precision": {"symbol": "swUnitsMassPropDecimalPlaces", "id": 261},
}
# Read-only finite linkage manifest. This is not every Document Properties page.
LINKAGE = {
    "swUnitsLinearDecimalDisplay": ("Integer", 48), "swUnitsLinearFractionDenominator": ("Integer", 50),
    "swUnitsLinearRoundToNearestFraction": ("Toggle", 62), "swUnitsLinearFeetAndInchesFormat": ("Toggle", 63),
    "swUnitsDualLinear": ("Integer", 254), "swUnitsDualLinearDecimalDisplay": ("Integer", 255),
    "swUnitsDualLinearDecimalPlaces": ("Integer", 256), "swUnitsDualLinearFractionDenominator": ("Integer", 257),
    "swUnitsDualLinearRoundToNearestFraction": ("Toggle", 252), "swUnitsDualLinearFeetAndInchesFormat": ("Toggle", 253),
    "swUnitsForce": ("Integer", 262), "swUnitsForceDecimalPlaces": ("Integer", 332),
    "swUnitsEnergyUnits": ("Integer", 333), "swUnitsEnergyDecimalPlaces": ("Integer", 334),
    "swUnitsPowerUnits": ("Integer", 335), "swUnitsPowerDecimalPlaces": ("Integer", 336),
    "swUnitsTimeUnits": ("Integer", 337), "swUnitsTimeDecimalPlaces": ("Integer", 338),
    "swUnitsDecimalRounding": ("Integer", 522),
}
NATIVE_UNITS = ("length_unit", "fraction_base", "fraction_value", "significant_digits", "round_to_fraction")
# Exact (document_type, source_snapshot_sha256, field, native_target). Never
# populate from synthetic tests or automatically enable after a probe succeeds.
CALIBRATED_UNIT_WRITES = ()


def typed_key(value):
    if type(value) is dict: return (dict, tuple(sorted((k, typed_key(v)) for k, v in value.items())))
    if type(value) is list: return (list, tuple(typed_key(v) for v in value))
    return (type(value), value)


def int32(value):
    if type(value) is not int or not -2147483648 <= value <= 2147483647:
        raise ValueError("native unit preference is not an Int32")
    return value


def observe(field, native):
    int32(native)
    enum = FIELDS[field].get("enum")
    value = next((name for name, code in enum.items() if code == native), "other") if enum else native if 0 <= native <= 8 else "other"
    return {"value": value, "native_value": native}


def snapshot(kind, raw, units, linkage):
    if type(kind) is not int or kind not in (1, 2, 3) or type(raw) is not dict or set(raw) != set(FIELDS):
        raise ValueError("exact nine-field document unit profile required")
    if type(units) not in (tuple, list) or len(units) != 5 or any(type(v) is not int or not -32768 <= v <= 32767 for v in units):
        raise ValueError("GetUnits must return five exact shorts")
    if type(linkage) is not dict or set(linkage) != set(LINKAGE):
        raise ValueError("complete finite unit linkage observations required")
    for name, (family, _) in LINKAGE.items():
        if family == "Toggle":
            if type(linkage[name]) is not bool: raise ValueError("native linkage toggle is unreadable: " + name)
        else: int32(linkage[name])
    return {"profile": PROFILE, "document_type": kind, "values": {f: observe(f, raw[f]) for f in FIELDS},
            "native_units": dict(zip(NATIVE_UNITS, units)), "linkage": dict(linkage)}


def validate_snapshot(value):
    try:
        if type(value) is not dict or set(value) != {"profile", "document_type", "values", "native_units", "linkage"}:
            raise ValueError("complete expected unit profile required")
        rebuilt = snapshot(value["document_type"], {f: value["values"][f]["native_value"] for f in FIELDS},
                           [value["native_units"][k] for k in NATIVE_UNITS], value["linkage"])
        if typed_key(value) != typed_key(rebuilt): raise ValueError("expected unit profile is not exact/canonical")
    except (KeyError, TypeError) as error:
        raise ValueError("complete expected unit profile required") from error
    return deepcopy(value)


def target(field, value):
    if type(field) is not str or field not in FIELDS: raise ValueError("unsupported unit profile field")
    spec = FIELDS[field]
    if "enum" in spec:
        if type(value) is not str or value not in spec["targets"]: raise ValueError("unsupported candidate unit target")
        return spec["enum"][value]
    if type(value) is not int or not 0 <= value <= 8: raise ValueError("precision must be an integer from 0 to 8")
    return value


def fingerprint(value):
    validate_snapshot(value)
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def require_scalar_source(before, field):
    values, units = before["values"], before["native_units"]
    if field == "system": raise ValueError("system switching requires separately calibrated linkage evidence")
    if values["system"]["native_value"] != 4: raise ValueError("first unit scalar profile requires existing Custom; no automatic system switch")
    if any(v["value"] == "other" for v in values.values()): raise ValueError("unknown unit source profile is read-only")
    if (units["fraction_base"] != 1 or units["fraction_value"] not in (0, 8) or units["round_to_fraction"] != 0
            or units["length_unit"] != values["linear.unit"]["native_value"]
            or units["significant_digits"] != values["linear.precision"]["native_value"]):
        raise ValueError("changed unit profile requires consistent observed decimal source")


def verify_scalar_after(before, after, field, native_target):
    if after["values"][field]["native_value"] != native_target: raise RuntimeError("native unit target did not round-trip")
    if any(typed_key(after["values"][f]) != typed_key(before["values"][f]) for f in FIELDS if f != field):
        raise RuntimeError("native unit setter changed an unrequested preference")
    allowed = "length_unit" if field == "linear.unit" else "significant_digits" if field == "linear.precision" else None
    if any(after["native_units"][k] != before["native_units"][k] for k in NATIVE_UNITS if k != allowed):
        raise RuntimeError("native unit setter changed an unrelated GetUnits member")
    if typed_key(after["linkage"]) != typed_key(before["linkage"]): raise RuntimeError("native unit setter changed linkage observations")
