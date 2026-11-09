"""Table-only geometry rule approved by the user on 2026-11-08."""

import math

CENTROID_ABSOLUTE_TOLERANCE_MM = 1e-12
METRIC_FIELDS = {'solid_body_count', 'volume_mm3', 'surface_area_mm2', 'centroid_mm'}
AXES = ('x', 'y', 'z')


def compare_table_geometry(before, after):
    """Keep originals intact; only centroid xyz has an absolute difference bound."""
    result = dict(passed=False, exact_equal=before == after, finite=False,
                  non_centroid_equal=False, centroid_absolute_tolerance_mm=CENTROID_ABSOLUTE_TOLERANCE_MM,
                  centroid_delta_mm={}, centroid_delta_hex={}, before_hex={}, after_hex={})
    if not isinstance(before, dict) or not isinstance(after, dict) or set(before) != METRIC_FIELDS or set(after) != METRIC_FIELDS:
        return result
    for metrics in (before, after):
        if type(metrics['solid_body_count']) is not int or metrics['solid_body_count'] < 1:
            return result
        center = metrics['centroid_mm']
        if not isinstance(center, dict) or set(center) != set(AXES):
            return result
        values = [metrics['volume_mm3'], metrics['surface_area_mm2'], *center.values()]
        if any(type(value) not in (int, float) for value in values):
            return result
        try:
            if not all(math.isfinite(value) for value in values):
                return result
        except OverflowError:
            return result
        if metrics['volume_mm3'] <= 0 or metrics['surface_area_mm2'] <= 0:
            return result
    result['finite'] = True
    result['non_centroid_equal'] = all(before[key] == after[key] for key in METRIC_FIELDS - {'centroid_mm'})
    for label, metrics in (('before_hex', before), ('after_hex', after)):
        result[label] = {key: float(metrics[key]).hex() for key in ('volume_mm3', 'surface_area_mm2')}
        result[label].update({'centroid_mm.' + axis: float(metrics['centroid_mm'][axis]).hex() for axis in AXES})
    delta = {axis: after['centroid_mm'][axis] - before['centroid_mm'][axis] for axis in AXES}
    try:
        finite_delta = all(math.isfinite(value) for value in delta.values())
        result['centroid_delta_hex'] = {axis: float(value).hex() for axis, value in delta.items()}
    except OverflowError:
        return result
    result['centroid_delta_mm'] = {axis: value if math.isfinite(value) else None for axis, value in delta.items()}
    result['finite'] = finite_delta
    result['passed'] = finite_delta and result['non_centroid_equal'] and all(
        abs(value) <= CENTROID_ABSOLUTE_TOLERANCE_MM for value in delta.values())
    return result
