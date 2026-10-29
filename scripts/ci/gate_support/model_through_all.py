"""Installed typed-CLI through-all cases; no direct native CAD calls."""
import hashlib
import math
from pathlib import PureWindowsPath

from swcli.result_schemas import validate_operation_result
from gate_support.model_checks import LEASE_TTL_SECONDS, near, require


def verify_through_geometry(metrics, thickness, profile_kind):
    """Analytic box-minus-through-profile oracle, independent of CAD readback."""
    require(profile_kind in ("circle", "rectangle"), "unknown through-all profile")
    area, perimeter = ((9 * math.pi, 6 * math.pi) if profile_kind == "circle" else (24, 20))
    require(type(metrics["solid_body_count"]) is int and metrics["solid_body_count"] == 1, "through-all changed solid count")
    near(metrics["volume_mm3"], (1200 - area) * thickness,
         "through-all analytic volume mismatch", 1e-5)
    near(metrics["surface_area_mm2"], 2 * (1200 - area) + (140 + perimeter) * thickness,
         "through-all analytic surface area mismatch", 1e-5)


class ThroughAllCases:
    def through_all_cut(self):
        evidence = self.record["through_all_cases"] = []
        for profile_kind in ("circle", "rectangle"):
            for plane in ("front", "top", "right"):
                for reverse in (False, True):
                    case = dict(profile_kind=profile_kind, plane=plane, reverse=reverse, success=False)
                    evidence.append(case)
                    self._through_all_case(case)
                    case["success"] = True
                    self.require_empty()

    def _through_all_case(self, case):
        profile_kind, plane, reverse = (case[key] for key in ("profile_kind", "plane", "reverse"))
        document, foreground = self.create(), self.create()
        self.command("document", "lease", "acquire", "--ttl-seconds", LEASE_TTL_SECONDS, document=document)
        rectangle = self.rectangle(document, plane=plane)
        boss = self.feature(document, rectangle["sketch"]["sketch_id"], depth=10, reverse=reverse)
        profile = (self.circle(document, plane=plane, radius=3) if profile_kind == "circle"
                   else self.rectangle(document, plane=plane, width=6, height=4))
        arguments = ["feature", "cut-extrude", profile["sketch"]["sketch_id"], "--through-all"]
        if reverse:
            arguments.append("--reverse")
        cut = case["creation"] = self.write(*arguments, document=document)
        validate_operation_result("feature.cut-extrude", cut)
        self.background(cut, document)
        require(cut["end_condition"] == "through-all" and cut["depth_mm"] is None,
                "through-all reported a blind travel length")
        verify_through_geometry(cut["measurement_after"], 10, profile_kind)
        cut_id = cut["feature"]["feature_id"]
        before = self.command("document", "inspect", document=document)["document"]
        self.write("feature", "set-depth", cut_id, "--depth-mm", 1, document=document,
                   expected_error="UnsupportedDepthDefinition")
        require(self.command("document", "inspect", document=document)["document"] == before,
                "refused through-all depth edit changed document state")
        grown = self.write("feature", "set-depth", boss["feature"]["feature_id"],
                           "--depth-mm", 25, document=document)
        self.background(grown, document)
        case["grown_geometry"] = self.measure(document)["metrics"]
        verify_through_geometry(case["grown_geometry"], 25, profile_kind)
        self._observe_through_all(document, cut_id, reverse)
        stem = "through-all-" + profile_kind + "-" + plane + ("-reverse" if reverse else "-forward")
        host_path = str(PureWindowsPath(self.host_directory) / (stem + ".SLDPRT"))
        path = self.directory / (stem + ".SLDPRT")
        saved = self.write("document", "save-as", host_path, document=document)
        require(saved["document"]["modified"] is False and path.is_file(), "through-all native save failed")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.close(document)
        opened = self.command("document", "open", host_path, "--read-only")
        require(opened["api_errors"] == 0
                and PureWindowsPath(opened["document"]["path"]) == PureWindowsPath(host_path),
                "through-all reopened a different path or reported native errors")
        reopened = opened["document"]["document_id"]
        require(reopened != document, "through-all reopen reused a retired document ID")
        listed = self.command("feature", "list", document=reopened)
        cuts = [feature for feature in listed["features"] if feature["kind"] == "cut-extrude"]
        require(listed["count"] == len(listed["features"]) == 2
                and len(cuts) == 1 and cuts[0]["feature_id"] != cut_id, "fresh through-all discovery is ambiguous or stale")
        self._observe_through_all(reopened, cuts[0]["feature_id"], reverse)
        self.command("feature", "inspect", cut_id, document=reopened, expected_error="FeatureNotFound")
        case["reopened_geometry"] = self.measure(reopened)["metrics"]
        verify_through_geometry(case["reopened_geometry"], 25, profile_kind)
        diagnosis = self.command("document", "diagnose", document=reopened)
        require(diagnosis["diagnostics"]["healthy"] is True
                and diagnosis["diagnostics"]["truncated"] is False and diagnosis["needs_rebuild"] == 0,
                "through-all reopen diagnostics are incomplete or unhealthy")
        require(self.command("document", "inspect", document=reopened)["document"]["modified"] is False
                and hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                "through-all readonly reopen changed saved state or bytes")
        case.update(file_sha256=digest, native_path=host_path)
        self.close(reopened)
        self.close(foreground)

    def _observe_through_all(self, document, feature_id, reverse):
        inspected = self.command("feature", "inspect", feature_id, document=document)
        definition = inspected["definition"]
        require(definition["end_condition"] == 1 and definition["reverse_direction"] is (not reverse)
                and definition["both_directions"] is False and definition["thin"] is False
                and definition["feature_scope"] is False and definition["from_type"] == 0
                and definition["forward_draft"] is False and definition["reverse_draft"] is False
                and inspected["observation"]["unchanged"] is True,
                "through-all definition or read-only state changed")
