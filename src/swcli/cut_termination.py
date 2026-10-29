"""Prepared cut termination contract; not advertised until native proof.

Pure request handling, without CAD, file access or capability registration.
The existing public blind-only schema and adapter remain authoritative.
"""

from dataclasses import dataclass
import math
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class CutTermination:
    end_condition: str
    depth_mm: Optional[float]


def cut_termination_fields() -> Dict[str, Any]:
    """Fresh schema fields for integration after native behavior is proved."""
    return {
        "end_condition": {"type": "string", "enum": ["blind", "through-all"]},
        "depth_mm": {"type": "number", "exclusiveMinimum": 0},
    }


def cut_termination_conditions():
    """Missing termination means blind; presence of depth conflicts with through-all."""
    return [{
        "if": {
            "required": ["end_condition"],
            "properties": {"end_condition": {"const": "through-all"}},
        },
        "then": {"not": {"required": ["depth_mm"]}},
        "else": {"required": ["depth_mm"]},
    }]


def resolve_cut_termination(values: Dict[str, Any]) -> CutTermination:
    """Validate without defaults that could turn an ambiguous cut into a write."""
    end_condition = values.get("end_condition", "blind")
    if not isinstance(end_condition, str) or end_condition not in ("blind", "through-all"):
        raise ValueError("end_condition must be blind or through-all")
    if end_condition == "through-all":
        if "depth_mm" in values:
            raise ValueError("through-all does not accept depth_mm")
        return CutTermination(end_condition="through-all", depth_mm=None)
    if "depth_mm" not in values:
        raise ValueError("blind requires depth_mm")
    depth = values["depth_mm"]
    if isinstance(depth, bool) or not isinstance(depth, (int, float)):
        raise ValueError("depth_mm must be a positive finite representable length")
    try:
        depth = float(depth)
    except (OverflowError, ValueError):
        raise ValueError("depth_mm must be a positive finite representable length") from None
    if not math.isfinite(depth) or depth <= 0 or depth / 1000 <= 0:
        raise ValueError("depth_mm must be a positive finite representable length")
    return CutTermination(end_condition="blind", depth_mm=depth)
