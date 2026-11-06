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
