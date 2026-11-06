"""Targeted public CLI/SDK/MCP proof. No direct COM or host restart."""

import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath

from swcli.sdk import Client
from swcli.mcp import DaemonBridge

spec = importlib.util.spec_from_file_location("topology_modeling", Path(__file__).with_name("verify-modeling.py"))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


class TopologySmoke(base.ModelingSmoke):
    def resolve(self, file, document, *, error=None):
        return self.command("entity", "reference-resolve", "--reference-file", str(file),
                            document=document, expected_error=error)

    def run(self, **unused):
        self.record.update(full_acceptance_eligible=False, scope="targeted-public-topology-references")
        self.record["host"] = self.health()["host"]
        self.require_empty()
        a = self.create()
        profile = self.rectangle(a)
        self.feature(a, profile["sketch"]["sketch_id"], depth=10)
        target = str(PureWindowsPath(self.host_directory) / "references.SLDPRT")
        self.write("document", "save-as", target, document=a)
        b = self.create()
        foreground_profile = self.rectangle(b)
        self.feature(b, foreground_profile["sketch"]["sketch_id"], depth=10)
        self.write("document", "save-as", str(PureWindowsPath(self.host_directory)/"foreground.SLDPRT"), document=b)
        self.command("document", "lease", "acquire", "--ttl-seconds", 3600, document=a)
        references, files = {}, {}
        for kind in ("face", "edge"):
            listed = self.command("entity", "list", "--kind", kind, document=a)
            self.background(listed, a)
            if kind == "face":
                candidates = [face for face in listed["entities"] if face["surface_kind"] == "plane"
                    and abs(face["surface_geometry"]["plane"]["outward_normal"][0] - 1) < 1e-9]
            else:
                candidates = [edge for edge in listed["entities"] if edge["curve_kind"] == "line"
                    and all(abs(p[0] - 20) < 1e-5 and abs(p[1] - 15) < 1e-5
                        for p in (edge["parameter_data"]["start_point_mm"], edge["parameter_data"]["end_point_mm"]))]
            base.require(len(candidates) == 1, "exact unaffected fixture target missing or ambiguous")
            capture = self.command("entity", "reference-create", candidates[0]["entity_id"], "--kind", kind, document=a)
            self.background(capture, a)
            references[kind] = capture
            files[kind] = self.directory / (kind + "-reference.json")
            files[kind].write_text(json.dumps(capture, indent=2), encoding="utf-8")
            resolved = self.resolve(files[kind], a)
            self.background(resolved, a)
            base.require(resolved["entity"]["entity_id"] == capture["entity_id"], "unchanged reference changed entity")
            # Read-only contender is allowed despite another session's write lease.
            self.command("entity", "reference-resolve", "--reference-file", str(files[kind]),
                         document=a, session=self.session + "-reader")
            self.resolve(files[kind], b, error="PersistentReferenceScopeMismatch")
        client = Client(endpoint=self.endpoint, session_id=self.session + "-sdk", timeout_seconds=600)
        sdk = client.entity.reference_resolve(reference=references["face"]["reference"], document_id=a).require_result()
        self.record["sdk_reference_result"] = sdk
        base.require(sdk["entity"]["entity_id"] == references["face"]["entity_id"], "SDK changed exact target")
        bridge = DaemonBridge(endpoint=self.endpoint, session_id=self.session + "-mcp", timeout_seconds=600)
        mcp = bridge.call("execute", {"operation": "entity.reference-resolve",
                          "parameters": {"reference": references["edge"]["reference"]}, "document_id": a})
        self.record["mcp_reference_result"] = mcp
        base.require(mcp.get("success") is True and mcp["result"]["ok"] is True, "MCP reference resolution failed")
        self.write("document", "rebuild", document=a)
        for file in files.values(): self.resolve(file, a)
        stamp = self.command("document", "inspect", document=a)["document"]["update_stamp"]
        self.command("entity", "reference-resolve", "--reference-file", str(files["face"]),
                     "--if-update-stamp", stamp + 1, document=a, expected_error="DocumentUpdateConflict")
        self.write("document", "save", document=a)
        artifact = self.directory / "references.SLDPRT"
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        self.close(a)
        c = self.command("document", "open", target, "--read-only")["document"]["document_id"]
        self.command("document", "use", b)
        for file in files.values():
            resolved = self.resolve(file, c)
            self.background(resolved, c)
        base.require(hashlib.sha256(artifact.read_bytes()).hexdigest() == digest, "readonly reopen changed saved file")
        self.measure(c, volume=12000)
        self.close(c)
        # Public mutation uses a fresh writeable reopen. Stored references remain
        # external; old e-* handles are never reused as mutation targets.
        d = self.command("document", "open", target)["document"]["document_id"]
        self.command("document", "use", b)
        circle = self.circle(d, radius=3)
        self.feature(d, circle["sketch"]["sketch_id"], cut=True, depth=10)
        for file in files.values(): self.resolve(file, d, error="PersistentReferenceTopologyChanged")
        self.write("document", "save", document=d)
        self.close(d)
        e = self.command("document", "open", target, "--read-only")["document"]["document_id"]
        for file in files.values(): self.resolve(file, e, error="PersistentReferenceTopologyChanged")
        import math
        self.measure(e, volume=(40 * 30 - math.pi * 9) * 10)
        self.close(e); self.close(b)
        self.require_empty(after_case="topology-references")
        self.record["host_after"] = self.health()["host"]
        base.require(self.record["host_after"] == self.record["host"], "reference proof replaced host")
        self.record["cases"].append("face-edge-capture-rebuild-readonly-reopen-topology-change")
        self.record["output_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()


if __name__ == "__main__":
    base.ModelingSmoke = TopologySmoke
    base.main()
