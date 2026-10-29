"""Exact simple polygon creation and native closed-cycle readback."""

import math

from ..polygon_geometry import TOLERANCE_MM, validate_polygon
from .windows import _com_value
from .windows_sketches import (
    STANDARD_PLANES, _create_profile_sketch_windows_with_handle,
    _create_without_inference,
)


def observe_polygon_sketch(sketch, expected):
    segments = _com_value(sketch, "GetSketchSegments")
    if not isinstance(segments, (list, tuple)) or len(segments) != len(expected.vertices_mm):
        raise ValueError("polygon segment readback is incomplete or has extra geometry")
    vertices, edges = {}, set()
    for segment in segments:
        if _com_value(segment, "ConstructionGeometry") is not False or type(_com_value(segment, "GetType")) is not int or _com_value(segment, "GetType") != 0:
            raise ValueError("polygon requires only nonconstruction native lines")
        indices = []
        for member in ("GetStartPoint2", "GetEndPoint2"):
            p = _com_value(segment, member)
            raw = [_com_value(p, axis) for axis in "XYZ"]
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in raw):
                raise ValueError("polygon endpoint is unreadable")
            actual = tuple(float(v) * 1000 for v in raw)
            if not all(math.isfinite(v) for v in actual) or abs(actual[2]) > TOLERANCE_MM:
                raise ValueError("polygon endpoint is nonfinite or outside sketch XY")
            matches = [i for i, vertex in enumerate(expected.vertices_mm)
                       if math.dist(actual[:2], vertex) <= TOLERANCE_MM]
            if len(matches) != 1:
                raise ValueError("polygon endpoint does not match one expected vertex")
            index = matches[0]
            if index in vertices and math.dist(vertices[index], actual[:2]) > TOLERANCE_MM:
                raise ValueError("polygon endpoints disagree about a shared vertex")
            vertices[index] = actual[:2]
            indices.append(index)
        edge = tuple(sorted(indices))
        if edge in edges:
            raise ValueError("polygon contains a duplicate native edge")
        edges.add(edge)
    count = len(expected.vertices_mm)
    if len(vertices) != count or edges != {tuple(sorted((i, (i + 1) % count))) for i in range(count)}:
        raise ValueError("polygon native edges do not form the exact requested cycle")
    actual = validate_polygon([dict(x=vertices[i][0], y=vertices[i][1]) for i in range(count)])
    contours = _com_value(sketch, "GetSketchContours")
    if not isinstance(contours, (tuple, list)) or len(contours) != 1:
        raise ValueError("polygon must have one observable native contour")
    # Record the native boolean explicitly; solid extrusion is a separate proof.
    closed = _com_value(contours[0], "IsClosed")
    if type(closed) is not bool or not closed:
        raise ValueError("polygon native contour is not closed")
    return dict(passed=True, method="sketch-local-polygon-edge-cycle",
                segment_count=len(segments), vertex_count=count,
                contour_count=1, native_closed=closed,
                actual_vertices_mm=[dict(x=p[0], y=p[1]) for p in actual.vertices_mm],
                signed_area_mm2=actual.signed_area_mm2, perimeter_mm=actual.perimeter_mm,
                centroid_mm=dict(x=actual.centroid_mm[0], y=actual.centroid_mm[1]),
                absolute_tolerance_mm=TOLERANCE_MM)


def create_polygon_sketch_windows_with_handle(*, app, document, plane, vertices_mm):
    try:
        if plane not in STANDARD_PLANES:
            raise ValueError("polygon requires a standard origin plane")
        geometry = validate_polygon(vertices_mm)
    except (ValueError, TypeError, OverflowError) as exc:
        return dict(action="sketch.polygon", ok=False,
                    error=dict(type="InvalidArgument", message=str(exc))), None
    warnings = []

    def create(manager):
        lines = []
        points = geometry.vertices_mm
        for index, start in enumerate(points):
            end = points[(index + 1) % len(points)]
            segment = manager.CreateLine(start[0] / 1000, start[1] / 1000, 0,
                                         end[0] / 1000, end[1] / 1000, 0)
            if segment is None:
                raise RuntimeError("native polygon line creation returned no segment")
            lines.append(segment)
        return lines

    result, feature = _create_profile_sketch_windows_with_handle(
        app=app, document=document, plane=plane, action="sketch.polygon",
        dimensions=dict(unit="millimeter", vertices_mm=[dict(x=x, y=y) for x, y in geometry.vertices_mm]),
        create_segments=lambda manager: _create_without_inference(
            manager, lambda: create(manager), warnings,
            native_method="CreateLine", shape="polygon"),
        verify_sketch=lambda sketch: observe_polygon_sketch(sketch, geometry),
    )
    if warnings:
        result.setdefault("warnings", []).extend(warnings)
        if result["ok"]:
            result.update(ok=False, error=dict(type="SketchStateRestoreFailed",
                message="polygon was created but native creation mode could not be restored"))
    return result, feature
