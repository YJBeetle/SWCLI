"""Bounded STL-specific request contract; native calibration is separate."""
STL_OPTIONS_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["encoding", "unit", "deviation_mm", "angle_degrees"],
    "properties": {
        "encoding": {"type": "string", "enum": ["binary", "ascii"]},
        "unit": {"type": "string", "enum": ["mm", "cm", "m", "inch", "foot"]},
        # Conservative SWCLI product bounds, not claimed universal SW limits.
        "deviation_mm": {"type": "number", "minimum": 0.01, "maximum": 1.0},
        "angle_degrees": {"type": "number", "minimum": 0.5, "maximum": 30.0},
    },
}

# Discovery advertises conditional exact tuples, not a continuous native range.
from .stl_calibrated_profiles import QUALIFICATION, PROFILES
STL_OPTIONS_SCHEMA["description"] = (
    "STL-specific options. Public writes require an explicitly isolated owned hidden "
    "GitHub Windows worker, native 33.5.0 and an exact calibrated profile; ordinary "
    "or shared hosts and other tuples fail closed. Schema numeric bounds are candidate bounds."
)
STL_OPTIONS_SCHEMA["x-swcli-qualified-stl"] = {
    "qualification": QUALIFICATION,
    "profiles": PROFILES,
    "document_kind": "part",
    "requires_explicit_exclusive_runner": True,
}
