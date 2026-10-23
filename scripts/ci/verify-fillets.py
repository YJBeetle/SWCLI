"""Public typed single-edge fillet roundtrip; no COM, retries or host restart."""
import importlib.util
import math
from pathlib import Path, PureWindowsPath

spec = importlib.util.spec_from_file_location("fillet_modeling", Path(__file__).with_name("verify-modeling.py"))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def fixture_edge(edges):
    """Identify the positive-X/Y vertical edge geometrically, never by ordinal."""
    matches = []
    for edge in edges:
        if edge["curve_kind"] != "line":
            continue
        data = edge["parameter_data"]
        a, b = data["start_point_mm"], data["end_point_mm"]
        if not (all(abs(p[0] - 20) < 1e-5 and abs(p[1] - 15) < 1e-5 for p in (a, b))
                and sorted(round(p[2], 5) for p in (a, b)) == [0, 10]):
            continue
        line = edge["curve_geometry"]["line"]
        base.near(abs(line["direction"][2]), 1, "edge direction changed")
        for axis, value in ((0, 20), (1, 15)):
            base.near(line["root_point_mm"][axis], value, "edge root moved")
            base.near(line["direction"][axis], 0, "edge tilted")
        matches.append(edge["entity_id"])
    base.require(len(matches) == 1, "exact fixture edge missing or ambiguous")
    return matches[0]


class FilletSmoke(base.ModelingSmoke):
    def run(self, **unused):
        self.record["host"] = self.health()["host"]
        capabilities = self.command("capabilities", "--full")
        base.require("feature.fillet" in capabilities["operations"], "fillet capability unavailable")
        self.require_empty()
        a = self.create()
        profile = self.rectangle(a)
        self.feature(a, profile["sketch"]["sketch_id"], depth=10)
        self.measure(a, volume=12000)
        b = self.create()
        listed = self.command("entity", "list", "--kind", "edge", document=a)
        self.background(listed, a)
        edge = fixture_edge(listed["entities"])
        stamp = listed["document"]["update_stamp"]
        base.require(type(stamp) is int, "native update stamp unavailable")
        self.command("document", "lease", "acquire", "--ttl-seconds", 600, document=a)
        args = ("feature", "fillet", edge, "--radius-mm", 2)
        self.command(*args, document=a, session=self.session + "-contender",
                     expected_error="DocumentLeaseConflict")
        self.command(*args, document=a, lease="l-000000000000",
                     expected_error="DocumentLeaseConflict")
        self.write(*args, "--if-update-stamp", stamp + 1, document=a,
                   expected_error="DocumentUpdateConflict")
        result = self.write(*args, "--if-update-stamp", stamp, document=a)
        self.background(result, a)
        proof = result["verification"]
        base.require(proof["passed"] is True and proof["edge_count"] == 1
                     and proof["profile"] == "circular" and proof["tangent_propagation"] is False
                     and result["feature"]["type"] == "Fillet"
                     and result["entity_id"] == edge and result["bodies"] == 1
                     and result["diagnostics"]["healthy"] is True
                     and result["diagnostics"]["truncated"] is False
                     and all(result["mutation"].get(key) is True for key in
                             ("attempted", "creation_returned", "may_have_changed"))
                     and result["rebuilt"] is True and result["cleanup_errors"] == [],
                     "fillet native readback/rebuild/cleanup failed")
        base.near(proof["radius_mm"], 2, "fillet radius changed")
        expected = 12000 - (1 - math.pi / 4) * 4 * 10
        base.near(result["before_volume_mm3"], 12000, "fillet baseline changed")
        base.near(result["after_volume_mm3"], expected, "fillet volume delta changed")
        self.measure(a, volume=expected)
        self.command("entity", "inspect", edge, "--kind", "edge", document=a,
                     expected_error="EntityReferenceStale")
        rediscovered = self.command("entity", "list", "--kind", "edge", document=a)
        base.require(rediscovered["entities"] and edge not in
                     {item["entity_id"] for item in rediscovered["entities"]},
                     "topology mutation retained stale edge handle")
        self.background(rediscovered, a)
        self.background(self.command("document", "inspect", document=a), a)
        status_b = self.command("document", "inspect", document=b)["document"]
        base.require(status_b["active"] and status_b["current"], "fillet changed foreground/current")
        target = str(PureWindowsPath(self.host_directory) / "fillet.SLDPRT")
        saved = self.write("document", "save-as", target, document=a)
        artifact = self.directory / "fillet.SLDPRT"
        base.require(not saved["document"]["modified"] and artifact.is_file()
                     and artifact.stat().st_size >= 512, "native fillet save failed")
        self.close(a)
        self.close(b)
        reopened = self.command("document", "open", target, "--read-only")["document"]
        c = reopened["document_id"]
        base.require(reopened["type"] == 1 and not reopened["modified"], "native part reopen failed")
        metrics = self.measure(c, volume=expected)["metrics"]
        base.require(metrics["solid_body_count"] == 1, "fillet roundtrip lost one solid")
        status = self.command("entity", "list", "--kind", "edge", document=c)
        base.require(status["observation"]["after"]["editing"] is False,
                     "fillet roundtrip left sketch editing")
        self.close(c)
        self.require_empty(after_case="single-edge-fillet")
        self.record["host_after"] = self.health()["host"]
        base.require(self.record["host_after"] == self.record["host"], "fillet replaced host")
        self.record["cases"].append("single-edge-fillet")


if __name__ == "__main__":
    base.ModelingSmoke = FilletSmoke
    base.main()
