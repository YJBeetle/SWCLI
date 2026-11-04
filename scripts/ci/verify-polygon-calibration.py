"""Opt-in native polygon proof, not public polygon/full CAD acceptance."""

import argparse
import hashlib
import importlib.util
import math
from pathlib import Path

from swcli.hosts.windows import _com_value
from swcli.hosts.windows_documents import open_windows_document_with_handle, _diagnose_features
from swcli.hosts.windows_features import extrude_sketch_windows_with_handle
from swcli.hosts.windows_cuts import cut_extrude_sketch_windows_with_handle
from swcli.hosts.windows_measurements import measure_part_windows
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.hosts.windows_polygons import (
    create_polygon_sketch_windows_with_handle, observe_native_polygon_profile,
)
from swcli.hosts.windows_feature_depth_edits import set_extrusion_depth_windows
from swcli.hosts.windows_feature_depth_profiles import _owned_profile, _profile_transform
from swcli.hosts.windows_sketch_inspection import _feature_id
from swcli.polygon_geometry import TOLERANCE_MM
from swcli.hosts.windows_sketches import create_rectangle_sketch_windows_with_handle, _features
from swcli.hosts.windows_feature_inspection import _FeatureError, _observe, _same, _types
from swcli.hosts.windows_dimensions import _variant

spec = importlib.util.spec_from_file_location("_polygon_owned_harness",
    Path(__file__).with_name("verify-through-all-calibration.py"))
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
checked = harness.checked

PROFILES = {
    "triangle": [(-10, -5), (10, -5), (-10, 10)],
    "ell": [(-10, -5), (10, -5), (10, 0), (-5, 0), (-5, 10), (-10, 10)],
}


# Keep the first mutation proof bounded. The other cases retain read-only proof.
DEPTH_CASES = {
    ("triangle-ccw-boss", "front", False): 14,
    ("ell-cw-boss", "top", True): 6,
    ("triangle-cw-cut", "right", True): 7,
    ("ell-ccw-cut", "front", False): 3,
}


def verify_geometry(metrics, shape, plane, reverse, mode, depth_mm=None):
    # Independent fixture oracles; do not call the product's shoelace code here.
    area, perimeter, cx, cy = ((150, 60, -10 + 20 / 3, 0) if shape == "triangle"
                              else (150, 70, -2.5, 0))
    depth = depth_mm if depth_mm is not None else (10 if mode == "boss" else 5)
    if mode == "boss":
        volume, surface, normal = area * depth, 2 * area + perimeter * depth, depth / 2
        local_x, local_y = cx, cy
    else:
        removed_volume = area * depth
        volume, surface = 12000 - removed_volume, 3800 + perimeter * depth
        local_x, local_y = -removed_volume * cx / volume, -removed_volume * cy / volume
        normal = (12000 * 5 - removed_volume * depth / 2) / volume
    checked(metrics["solid_body_count"] == 1, "polygon fixture did not leave one solid")
    for key, expected in (("volume_mm3", volume), ("surface_area_mm2", surface)):
        checked(math.isfinite(metrics[key]) and abs(metrics[key] - expected) < 1e-5,
                "polygon analytic geometry differs: " + key)
    # Actual model-to-sketch transform supplies the in-plane basis; geometry
    # checks independently verify local centroid below in the caller.
    return dict(expected_volume_mm3=volume, expected_surface_area_mm2=surface,
                expected_sketch_centroid_mm=[local_x, local_y],
                expected_normal_distance_mm=-normal if reverse else normal, metrics=metrics)


def verify_centroid(app, transform, metric, expected):
    utility = _com_value(app, "GetMathUtility")
    utility._FlagAsMethod("CreatePoint")
    utility._FlagAsMethod("CreateTransform")
    point = utility.CreatePoint(_variant("double-array", tuple(metric["centroid_mm"][axis] / 1000 for axis in "xyz")))
    math_transform = utility.CreateTransform(_variant("double-array", tuple(transform)))
    values = _com_value(point.MultiplyTransform(math_transform), "ArrayData")
    target = [*expected["expected_sketch_centroid_mm"], expected["expected_normal_distance_mm"]]
    checked(all(abs(float(values[i]) * 1000 - target[i]) < 1e-5 for i in range(3)),
            "polygon centroid/direction differs in sketch-local coordinates")


def observe_owned_polygon(app, document, feature, expected_sketch=None):
    def fingerprint():
        profile, parent_ids, sketch = _owned_profile(app, document, feature)
        if expected_sketch is not None and not _same(app, profile, expected_sketch):
            raise _FeatureError("FeatureProfileUnavailable", "absorbed sketch differs from the created sketch")
        geometry, edges = observe_native_polygon_profile(sketch)
        return dict(
            profile_id=_feature_id(profile), parent_ids=parent_ids,
            vertices_mm=geometry.vertices_mm, edges_mm=edges,
            model_to_sketch_transform=_profile_transform(sketch),
        )

    def read():
        profile = fingerprint()
        if fingerprint() != profile:
            raise _FeatureError("FeatureObservationUnavailable", "owned polygon changed across native reads")
        return {"profile": profile}, []

    result, _ = _observe(action="polygon-profile-calibration", app=app, document=document, read=read)
    return result


def require_same_edges(actual, expected):
    checked(len(actual) == len(expected), "native polygon edge count differs")
    matches = []
    for a, b in actual:
        candidates = [
            index for index, (c, d) in enumerate(expected)
            if (max(math.dist(a, c), math.dist(b, d)) <= TOLERANCE_MM
                or max(math.dist(a, d), math.dist(b, c)) <= TOLERANCE_MM)
        ]
        checked(len(candidates) == 1, "native polygon edge differs or matches ambiguously")
        matches.append(candidates[0])
    checked(len(set(matches)) == len(expected), "native polygon edges do not cover the fixture")



def verify_depth_mutation(app, document, feature, target, call, case):
    for label, changed in (("polygon-depth-write", True), ("polygon-depth-equal", False)):
        result = case[label] = call(label, lambda: set_extrusion_depth_windows(
            app=app, document=document, feature=feature, depth_mm=target, _polygon_calibration=True))
        checked(result["ok"] and not result.get("warnings"),
                label + " failed: " + str(result.get("error")))
        expected_mutation = dict.fromkeys(
            ("staging_attempted", "configuration_scope_applied", "commit_attempted", "committed"),
            changed,
        )
        checked(result["mutation"] == expected_mutation and result["depth_changed"] is changed,
                label + " mutation state differs")
        checked(result["verification"]["passed"] and
                abs(result["definition_after"]["depth_mm"] - target) <= TOLERANCE_MM,
                label + " did not read back the requested depth")



def calibrate_case(app, output, constants, plane, reverse, call, case, report, live,
                   retained_documents=(), profile_kind="triangle-ccw-boss"):
    shape, winding, mode = profile_kind.split("-")
    case.update(shape=shape, winding=winding, mode=mode, plane=plane, reverse=reverse, success=False)
    made, document = call("create-owned-part", lambda: create_part_windows_with_handle(app=app))
    live["document"] = document
    checked(made["ok"] and document is not None, "polygon fixture creation failed")
    if mode == "cut":
        box, rectangle = call("box-profile", lambda: create_rectangle_sketch_windows_with_handle(
            app=app, document=document, plane=plane, width_mm=40, height_mm=30))
        checked(box["ok"] and not box.get("warnings"), "base rectangle failed")
        boss, _ = call("box-boss", lambda: extrude_sketch_windows_with_handle(
            app=app, document=document, sketch_feature=rectangle, depth_mm=10, reverse=reverse))
        checked(boss["ok"] and not boss.get("warnings"), "base boss failed")
    points = PROFILES[shape][::(-1 if winding == "cw" else 1)]
    result, sketch = call("polygon-create", lambda: create_polygon_sketch_windows_with_handle(
        app=app, document=document, plane=plane,
        vertices_mm=[dict(x=x, y=y) for x, y in points]))
    case["sketch_creation"] = result
    checked(result["ok"] and sketch is not None and not result.get("warnings"),
            "polygon native creation/closed cycle/state restore failed")
    function = extrude_sketch_windows_with_handle if mode == "boss" else cut_extrude_sketch_windows_with_handle
    built, feature = call("polygon-" + mode, lambda: function(app=app, document=document,
        sketch_feature=sketch, depth_mm=10 if mode == "boss" else 5, reverse=reverse))
    case["feature_creation"] = built
    checked(built["ok"] and feature is not None and not built.get("warnings"), "polygon solid feature failed")
    observation = case["owned_profile"] = call("polygon-owned-profile", lambda: observe_owned_polygon(
        app, document, feature, expected_sketch=sketch))
    checked(observation["ok"], "created polygon profile observation failed: " + str(observation.get("error")))
    profile = observation["profile"]
    expected_edges = [((*point, 0), (*points[(i + 1) % len(points)], 0)) for i, point in enumerate(points)]
    require_same_edges(profile["edges_mm"], expected_edges)
    measured = call("polygon-measure", lambda: measure_part_windows(document=document))
    checked(measured["ok"], "polygon fixture measurement failed")
    case["geometry"] = verify_geometry(measured["metrics"], shape, plane, reverse, mode)
    verify_centroid(app, result["model_to_sketch_transform"], measured["metrics"], case["geometry"])
    target = DEPTH_CASES.get((profile_kind, plane, reverse))
    saved_depth = target if target is not None else (10 if mode == "boss" else 5)
    if target is not None:
        verify_depth_mutation(app, document, feature, target, call, case)
        changed = call("polygon-edited-measure", lambda: measure_part_windows(document=document))
        checked(changed["ok"], "edited polygon measurement failed")
        case["edited_geometry"] = verify_geometry(changed["metrics"], shape, plane, reverse, mode, target)
        verify_centroid(app, profile["model_to_sketch_transform"], changed["metrics"], case["edited_geometry"])
    checked(_diagnose_features(document, 500)["healthy"], "polygon fixture diagnosis failed")
    path = output / (profile_kind + "-" + plane + ("-reverse" if reverse else "-forward") + ".SLDPRT")
    saved = call("polygon-save", lambda: save_as_native_windows(str(path), document=document))
    checked(saved["ok"] and not saved.get("warnings"), "polygon save failed")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    title = _com_value(document, "GetTitle")
    sketch = feature = document = live["document"] = None
    call("polygon-close", lambda: app.CloseDoc(title))
    harness.require_catalog(app, retained_documents, call, "polygon-closed-catalog")
    opened, document = call("polygon-reopen", lambda: open_windows_document_with_handle(
        str(path), app=app, read_only=True))
    live["document"] = document
    checked(opened["ok"] and opened["api_errors"] == 0, "polygon readonly reopen failed")
    measured = call("polygon-reopened-measure", lambda: measure_part_windows(document=document))
    checked(measured["ok"], "reopened polygon measurement failed")
    case["reopened_geometry"] = verify_geometry(measured["metrics"], shape, plane, reverse, mode, saved_depth)
    verify_centroid(app, result["model_to_sketch_transform"], measured["metrics"], case["reopened_geometry"])
    kind = "Extrusion" if mode == "boss" else "Cut"
    features = [f for f in _features(document) if _types(f)[1] == kind]
    checked(len(features) == 1, "reopened polygon feature is ambiguous")
    checked(_com_value(document, "IsOpenedReadOnly") is True, "reopened fixture is not read-only")
    reopened = case["reopened_owned_profile"] = call("polygon-reopened-owned-profile", lambda: observe_owned_polygon(
        app, document, features[0]))
    checked(reopened["ok"], "reopened polygon profile observation failed: " + str(reopened.get("error")))
    reopened_profile = reopened["profile"]
    require_same_edges(reopened_profile["edges_mm"], expected_edges)
    require_same_edges(reopened_profile["edges_mm"], profile["edges_mm"])
    checked(all(abs(a - b) <= 1e-9 for a, b in zip(
        reopened_profile["model_to_sketch_transform"], profile["model_to_sketch_transform"])),
        "polygon model-to-sketch transform changed after reopen")
    definition = _com_value(features[0], "GetDefinition")
    checked(definition.GetEndCondition(True) == 0 and abs(definition.GetDepth(True) * 1000 - saved_depth) < 1e-6,
            "reopened polygon feature depth/end condition changed")
    diagnostic = case["reopened_diagnostics"] = _diagnose_features(document, 500)
    checked(diagnostic["healthy"] and not diagnostic["truncated"] and _com_value(document.Extension, "NeedsRebuild2") == 0,
            "reopened polygon fixture is not healthy and clean")
    checked(not _com_value(document, "GetSaveFlag") and hashlib.sha256(path.read_bytes()).hexdigest() == digest,
            "readonly polygon reopen changed saved state/bytes")
    case["file_sha256"] = digest
    title = _com_value(document, "GetTitle")
    features = definition = document = live["document"] = None
    call("polygon-close-reopened", lambda: app.CloseDoc(title))
    harness.require_catalog(app, retained_documents, call, "polygon-case-cleanup")
    case["success"] = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.swconst.is_file():
        parser.error("official swconst type library is required")
    args.output_dir.mkdir()
    plan = [(f"{shape}-{winding}-{mode}", plane, reverse)
            for shape in PROFILES for winding in ("ccw", "cw") for mode in ("boss", "cut")
            for plane in ("front", "top", "right") for reverse in (False, True)]
    return harness.run(args.output_dir.resolve(), args.swconst.resolve(), False,
        case_runner=calibrate_case, case_plan=plan, diagnostic_case="polygon-calibration")


if __name__ == "__main__":
    raise SystemExit(main())
