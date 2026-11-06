"""Exact boundary oracle for the owned 40x30x10 box, not a topology API.

Never round native coordinates. Full corners, straight edges and planes must
form the analytic box. Raw mass-property centroid is retained by the caller;
its analytic tolerance is the existing 1e-6 mm, not a stable identity key.
"""
from itertools import combinations, product
import math
import importlib.util
from pathlib import Path

checks_spec = importlib.util.spec_from_file_location("_dimension_existing_metric_checks", Path(__file__).with_name("model_checks.py"))
checks = importlib.util.module_from_spec(checks_spec)
checks_spec.loader.exec_module(checks)
verify_native_pair = checks.unchanged_depth_metrics
from swcli.hosts.windows import _com_value


def require(condition, message):
    if not condition: raise RuntimeError(message)


def point(values):
    require(isinstance(values, (list, tuple)) and len(values) == 3, "box point is incomplete")
    require(all(type(value) in (int, float) and math.isfinite(value) for value in values), "box point is unreadable")
    return tuple(float(value) for value in values)


def pair(first, second):
    a, b = point(first), point(second)
    require(a != b, "box edge has coincident endpoints")
    return tuple(sorted((a, b)))


def signature(vertices, edges, planes, metrics):
    vertices = sorted(point(value) for value in vertices)
    require(len(vertices) == len(set(vertices)) == 8, "box needs eight distinct complete vertices")
    axes = [sorted({p[axis] for p in vertices}) for axis in range(3)]
    require(all(len(values) == 2 for values in axes) and sorted(product(*axes)) == vertices,
            "box vertices are not the complete Cartesian corners")
    for axis, expected in enumerate((40, 30, 10)):
        require(math.isclose(axes[axis][1] - axes[axis][0], expected, rel_tol=0, abs_tol=1e-6),
                "owned box dimensions differ from the existing fixture tolerance")
    center = tuple((values[0] + values[1]) / 2 for values in axes)
    require(all(math.isclose(a, b, rel_tol=0, abs_tol=1e-6) for a, b in zip(center, (0, 0, 5))), "owned box center is incorrect")
    edges = sorted(pair(*edge) for edge in edges)
    expected_edges = sorted((a, b) for a, b in combinations(vertices, 2) if sum(x != y for x, y in zip(a, b)) == 1)
    require(len(edges) == 12 and edges == expected_edges, "box straight boundary edges are incomplete or changed")
    expected_planes = []
    for axis, values in enumerate(axes):
        for sign, offset in ((-1, -values[0]), (1, values[1])):
            normal = [0.0] * 3; normal[axis] = float(sign)
            expected_planes.append((*normal, offset))
    planes = sorted(tuple(row) for row in planes)
    require(len(planes) == 6 and planes == sorted(expected_planes), "box planar boundaries are incomplete or changed")
    require(metrics["solid_body_count"] == 1, "owned box is not a single solid")
    for key, expected in (("volume_mm3", 12000), ("surface_area_mm2", 3800)):
        require(type(metrics[key]) in (int, float) and math.isfinite(metrics[key])
                and math.isclose(metrics[key], expected, rel_tol=1e-7, abs_tol=1e-5),
                "native box mass geometry differs from the existing analytic bounds")
    native_center = point([metrics["centroid_mm"][axis] for axis in "xyz"])
    require(all(math.isclose(a, b, rel_tol=0, abs_tol=1e-6) for a, b in zip(native_center, center)),
            "native centroid disagrees with the exact boundary centroid")
    return dict(vertices_mm=vertices, edge_endpoints_mm=edges, planes_mm=planes,
                centroid_mm=dict(zip("xyz", center)), solid_body_count=1,
                volume_mm3=metrics["volume_mm3"], surface_area_mm2=metrics["surface_area_mm2"])


def observe_native(document, metrics, evidence):
    bodies = tuple(document.GetBodies2(0, False) or ())
    require(len(bodies) == 1 and not document.GetBodies2(1, False), "box oracle requires exactly one solid and no surface bodies")
    body = bodies[0]
    vertices = tuple(_com_value(body, "GetVertices") or ())
    edges = tuple(_com_value(body, "GetEdges") or ())
    faces = tuple(_com_value(body, "GetFaces") or ())
    counts = evidence["native_counts"] = dict(vertices=_com_value(body, "GetVertexCount"),
        edges=_com_value(body, "GetEdgeCount"), faces=_com_value(body, "GetFaceCount"))
    require(len(vertices) == counts["vertices"] == 8 and len(edges) == counts["edges"] == 12
            and len(faces) == counts["faces"] == 6, "native box boundary enumeration is incomplete")
    def vertex(value):
        require(value is not None, "native box vertex is absent")
        return tuple(coordinate * 1000 for coordinate in point(_com_value(value, "GetPoint")))
    def edge(value):
        require(_com_value(_com_value(value, "GetCurve"), "IsLine") is True, "box edge is not a native line")
        return pair(vertex(_com_value(value, "GetStartVertex")), vertex(_com_value(value, "GetEndVertex")))
    points = evidence["vertices_mm"] = [vertex(value) for value in vertices]
    edge_pairs = evidence["edge_endpoints_mm"] = [edge(value) for value in edges]
    planes = evidence["planes_mm"] = []
    for face in faces:
        require(_com_value(_com_value(face, "GetSurface"), "IsPlane") is True, "box face is not a native plane")
        boundary = tuple(_com_value(face, "GetEdges") or ())
        require(len(boundary) == _com_value(face, "GetEdgeCount") == 4, "box face boundary is incomplete")
        pairs = [edge(value) for value in boundary]
        corners = sorted({p for value in pairs for p in value})
        expected_face_edges = sorted((a, b) for a, b in combinations(corners, 2) if sum(x != y for x, y in zip(a, b)) == 1)
        require(len(corners) == 4 and len(expected_face_edges) == 4 and sorted(pairs) == expected_face_edges
                and all(value in edge_pairs for value in pairs), "box face has invalid closed corner/edge membership")
        normal = point(_com_value(face, "Normal"))
        offsets = {sum(a * b for a, b in zip(normal, p)) for p in corners}
        require(len(offsets) == 1, "box face vertices do not lie on their native plane")
        planes.append((*normal, offsets.pop()))
    return signature(points, edge_pairs, planes, metrics)


def observe_public(edges, faces, metrics):
    require(edges["body_count"] == faces["body_count"] == 1 and edges["edge_count"] == 12 and faces["face_count"] == 6,
            "public box enumeration is incomplete")
    pairs = []
    for edge in edges["entities"]:
        require(edge["curve_kind"] == "line" and edge["curve_geometry"]["available"] is True, "public box contains a non-line")
        data = edge["parameter_data"]
        # Official ICurveParamData swaps edge ends when Sense is false. For this
        # fixture only, the unordered endpoint pair is direction independent.
        pairs.append(pair(data["start_point_mm"], data["end_point_mm"]))
    vertices = sorted({p for edge in pairs for p in edge})
    planes = []
    for face in faces["entities"]:
        require(face["surface_kind"] == "plane" and face["surface_geometry"]["available"] is True, "public box contains a non-plane")
        plane = face["surface_geometry"]["plane"]
        normal = point(plane["outward_normal"])
        planes.append((*normal, sum(a * b for a, b in zip(normal, point(plane["point_mm"])))))
    return signature(vertices, pairs, planes, metrics)
