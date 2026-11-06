"""Bounded document defaults for linear dimensions, separate from model dimensions.

Preference IDs are resolved by name from the installed official swconst.tlb.
Only none/basic types and explicit decimal precision are setter candidates.
"""
from functools import lru_cache
from pathlib import Path
import os

TOLERANCE_TYPES = {"none": 0, "basic": 1, "bilateral": 2, "limit": 3,
                   "symmetric": 4, "min": 5, "max": 6, "fit": 7,
                   "fit_with_tolerance": 8, "fit_tolerance_only": 9,
                   "block": 10, "general": 11}
PRECISIONS = {str(n): n for n in range(9)}
PRECISIONS["follow_nominal"] = -3
TOLERANCE_FIELDS = {
    "linear.type": {"preference": "swDetailingToleranceStyle", "values": TOLERANCE_TYPES,
                    "writable": ("none", "basic")},
    "linear.precision": {"preference": "swDetailingLinearTolPrecision", "values": PRECISIONS,
                         "writable": tuple(str(n) for n in range(9))},
}
# Deliberately empty until recorded public native acceptance exists. Internal
# calibration uses a process-local test patch, never an environment or wire flag.
PUBLIC_WRITE_FIELDS = frozenset()


def value_schema(field, *, writable=True):
    spec = TOLERANCE_FIELDS[field]
    return {"type": "string", "enum": list(spec["writable"] if writable else spec["values"])}


def snapshot_schema():
    return {"type": "object", "additionalProperties": False,
            "required": list(TOLERANCE_FIELDS),
            "properties": {field: {"type": "object", "additionalProperties": False,
                "required": ["value", "native_value"],
                "properties": {"value": {"type": "string"}, "native_value": {"type": "integer"}}}
                for field in TOLERANCE_FIELDS}}


def validate_value(field, value):
    if field not in TOLERANCE_FIELDS or type(value) is not str or value not in TOLERANCE_FIELDS[field]["writable"]:
        raise ValueError("unsupported document tolerance field/value")


@lru_cache(maxsize=1)
def native_constants():
    """No numeric preference fallback, registry writes or application preferences."""
    import pythoncom
    path = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "SOLIDWORKS" / "swconst.tlb"
    library = pythoncom.LoadTypeLib(str(path))
    wanted = {"swDetailingLinearDimension", *(s["preference"] for s in TOLERANCE_FIELDS.values())}
    found = {}
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attributes = info.GetTypeAttr()
        if attributes.typekind != pythoncom.TKIND_ENUM:
            continue
        for offset in range(attributes.cVars):
            descriptor = info.GetVarDesc(offset)
            name = info.GetDocumentation(descriptor[0])[0]
            if name in wanted:
                if name in found or type(descriptor.value) is not int:
                    raise RuntimeError("invalid or duplicate official tolerance enum")
                found[name] = descriptor.value
    if set(found) != wanted:
        raise RuntimeError("official swconst lacks required tolerance preference enums")
    return found
