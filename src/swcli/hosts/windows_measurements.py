"""Kernel-derived part geometry without selection, rebuilding or material edits."""

from __future__ import annotations

import math
from typing import Any, Dict

from .windows import _com_value, _error


def measure_part_windows(*, document: Any, max_bodies: int = 1000) -> Dict[str, Any]:
    """Sum all solid bodies, including hidden bodies; do not imply a geometric union."""
    result: Dict[str, Any] = {"ok": False, "action": "document.measure"}
    if (
        isinstance(max_bodies, bool)
        or not isinstance(max_bodies, int)
        or max_bodies < 1
    ):
        result["error"] = {
            "type": "InvalidArgument",
            "message": "max_bodies must be a positive integer",
        }
        return result
    try:
        if int(_com_value(document, "GetType")) != 1:
            result["error"] = {
                "type": "UnsupportedDocumentType",
                "message": "geometry measurement currently requires a part document",
            }
            return result
        bodies = tuple(document.GetBodies2(0, False) or ())
        if not bodies:
            result["error"] = {
                "type": "NoSolidBodies",
                "message": "the selected part has no solid bodies to measure",
            }
            return result
        if len(bodies) > max_bodies:
            result["error"] = {
                "type": "MeasurementLimitExceeded",
                "message": f"part has {len(bodies)} solid bodies; max_bodies is {max_bodies}",
            }
            return result
        items = []
        for index, body in enumerate(bodies):
            # Density is a calculation input, not a material mutation. Ignore
            # synthetic mass/inertia: only geometric volume, area and centroid
            # are reported. Native values are m, m^3 and m^2 respectively.
            properties = tuple(float(v) for v in (body.GetMassProperties(1.0) or ()))
            if (
                len(properties) != 12
                or not all(math.isfinite(v) for v in properties[:5])
                or properties[3] <= 0
                or properties[4] <= 0
            ):
                result["error"] = {
                    "type": "MeasurementUnavailable",
                    "message": f"solid body {index} returned missing or invalid native geometry properties",
                }
                return result
            item = {
                "index": index,
                "volume_mm3": properties[3] * 1e9,
                "surface_area_mm2": properties[4] * 1e6,
                "centroid_mm": dict(
                    zip(("x", "y", "z"), (v * 1000 for v in properties[:3]))
                ),
            }
            if not all(
                math.isfinite(v)
                for v in (
                    item["volume_mm3"],
                    item["surface_area_mm2"],
                    *item["centroid_mm"].values(),
                )
            ):
                result["error"] = {
                    "type": "MeasurementUnavailable",
                    "message": f"solid body {index} geometry exceeds representable millimeter units",
                }
                return result
            items.append(item)
        volume = math.fsum(item["volume_mm3"] for item in items)
        area = math.fsum(item["surface_area_mm2"] for item in items)
        center = {
            axis: math.fsum(
                item["centroid_mm"][axis] * (item["volume_mm3"] / volume)
                for item in items
            )
            for axis in ("x", "y", "z")
        }
        if not all(math.isfinite(v) for v in (volume, area, *center.values())):
            raise ValueError("total geometry exceeds representable millimeter units")
        result.update(
            {
                "ok": True,
                "scope": "sum-of-solid-bodies",
                "coordinate_system": "part-model",
                "method": "native-body-mass-properties",
                "metrics": {
                    "solid_body_count": len(items),
                    "volume_mm3": volume,
                    "surface_area_mm2": area,
                    "centroid_mm": center,
                },
                "bodies": items,
            }
        )
        return result
    except Exception as exc:
        result["error"] = _error(exc)
        return result
