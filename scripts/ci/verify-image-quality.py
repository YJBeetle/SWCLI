"""Bounded installed image-quality calibration and opt-in public property gate.

Uses public CLI and SDK on one already-owned hidden daemon. Each request has a
600s budget, the complete group a hard external 1800s watchdog. First failure
stops; no CAD retries, rollback, exporter-option guesses or host replacement.
"""
import argparse
import hashlib
import importlib.util
import importlib.metadata
import os
import json
import math
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

from swcli import __version__
from swcli.document_image_quality import IMAGE_QUALITY_FIELDS, exact_snapshot
from swcli.result_schemas import validate_operation_result
from swcli.sdk import Client
from swcli.mcp import DaemonBridge
from swcli.operation_schemas import OPERATION_CATALOG

spec = importlib.util.spec_from_file_location("_quality_annotations", Path(__file__).with_name("verify-document-annotations.py"))
annotations = importlib.util.module_from_spec(spec); spec.loader.exec_module(annotations)
modeling = annotations.modeling
require = modeling.require
from gate_support.glb_mesh import inspect_glb


class QualitySmoke(modeling.ModelingSmoke):
    def __init__(self, *, document_properties=False, public_acceptance=False, **kwargs):
        self.public_acceptance = public_acceptance
        self.document_properties = document_properties
        super().__init__(request_timeout_seconds=600, **kwargs)
        self.started = time.monotonic()
        self.record.update(profile="document-image-quality-public" if public_acceptance else "document-image-quality-calibration" if document_properties else "image-quality-calibration",
            covers_glb_mesh=not document_properties, evidence_kind="public-installed-cli-sdk-mcp-document-image-quality" if public_acceptance else "internal-installed-cli-sdk-calibration",
            full_acceptance_eligible=False, covers_full_modeling_suite=False,
            group_timeout_seconds=1800, image_quality_writes_accepted=False, public_acceptance_passed=False, image_quality_calibration_passed=False, glb_control_proven=False,
            expected_version=__version__, source_commit=os.environ.get("GITHUB_SHA"),
            export_staging_profile="not used by document-properties group" if document_properties else "plain filename in internal CI only; default exporter unchanged",
            python_version=sys.version,
            format_options_status="unsupported: no verified API mapping; same host defaults observed, not independently controlled")

    def command(self, *args, **kwargs):
        require(self.cleaning_up or time.monotonic()-self.started < 1800, "image quality 1800-second group budget exceeded")
        result = super().command(*args, **kwargs)
        require(self.cleaning_up or time.monotonic()-self.started < 1800, "image quality 1800-second group budget exceeded")
        return result


class Trace:
    def __init__(self, path): self.path, self.requests = path, set()

    def verify(self, gate, *, setters):
        event = gate.record["events"][-1]
        identifier = event["result"]["request_id"]
        require(identifier not in self.requests, "reused image-quality request id")
        records = []
        for line in self.path.read_text(encoding="utf-8-sig").splitlines():
            if '"swcli.native-call"' not in line: continue
            item = json.loads(line)
            if item.get("request_id") == identifier: records.append(item)
        operation = "document." + event["command"][event["command"].index("document")+1]
        require(records and records[0]["sequence"] == records[-1]["sequence"] == 0
            and records[0]["call"] == records[-1]["call"] == operation
            and records[0]["phase"] == "begin" and records[-1]["phase"] == "end", "incomplete quality operation trace")
        require(all(r["operation"] == operation and r["worker_pid"] == records[0]["worker_pid"] for r in records), "quality trace operation/worker drift")
        pairs = records[1:-1]
        require(len(pairs)%2 == 0, "incomplete quality call trace")
        for sequence, (begin, end) in enumerate(zip(pairs[::2], pairs[1::2]), 1):
            require(begin["sequence"] == end["sequence"] == sequence and begin["phase"] == "begin"
                and end["phase"] == "end" and begin["call"] == end["call"], "quality native call failure/order mismatch")
        all_calls = [r["call"] for r in pairs[::2]]
        require(not any(c.startswith(("ISldWorks.SetUserPreference", "SldWorks.SetUserPreference")) for c in all_calls),
                "quality operation called a global preference setter")
        # The trace also includes _com_value state/identity and API-sequence
        # guards. Validate every pair above, then compare only preference/dirty
        # calls against the strict single-write lifecycle, as annotation gates do.
        calls = [c for c in all_calls if c.startswith(("IModelDocExtension.GetUserPreference",
                 "IModelDocExtension.SetUserPreference")) or c == "IModelDoc2.SetSaveFlag"]
        getter_cycle = ["IModelDocExtension.GetUserPreference"+kind for kind in ("Integer", "Double", "Toggle", "Toggle", "Toggle")]
        getter_cycle += ["IModelDocExtension.GetUserPreferenceDoubleValueRange"]
        dirty = calls.count("IModelDoc2.SetSaveFlag")
        require(dirty <= int(bool(setters)), "quality noop/failed CAS marked dirty or repeated dirty call")
        expected = getter_cycle
        if setters:
            command = event["command"]
            field = command[command.index("image-quality-set")+1]
            expected = getter_cycle + ["IModelDocExtension.SetUserPreference"+IMAGE_QUALITY_FIELDS[field]["kind"]] + getter_cycle + ["IModelDoc2.SetSaveFlag"]*dirty + getter_cycle
        require(calls == expected, "quality native getter/setter count or order mismatch")
        self.requests.add(identifier)
        proof = dict(request_id=identifier, setter_count=setters, dirty_count=dirty, calls=calls, all_native_call_count=len(all_calls))
        gate.record.setdefault("native_call_proofs", []).append(proof)
        return proof


def constants(path):
    import pythoncom
    expected = {"swImageQualityShaded":44, "swImageQualityShadedDeviation":32,
        "swImageQualityUseHighQualityEdgeSize":210, "swImageQualitySaveTesselationWithPartDoc":255,
        "swImageQualityApplyToAllReferencedPartDoc":158, "swDetailingNoOptionSpecified":0,
        "swShadedImageQualityCoarse":1, "swShadedImageQualityFine":2, "swShadedImageQualityCustom":3}
    found = {}
    lib = pythoncom.LoadTypeLib(str(path))
    for index in range(lib.GetTypeInfoCount()):
        info = lib.GetTypeInfo(index); attributes = info.GetTypeAttr()
        if attributes.typekind != pythoncom.TKIND_ENUM: continue
        for offset in range(attributes.cVars):
            descriptor = info.GetVarDesc(offset); name = info.GetDocumentation(descriptor[0])[0]
            if name in expected:
                require(name not in found, "duplicate official quality enum")
                found[name] = descriptor.value
    require(found == expected, "installed official quality enums differ from catalog")
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), values=found)


def read(gate, document, trace):
    result = gate.command("document", "image-quality", document=document)
    validate_operation_result("document.image-quality", result)
    gate.background(result, document); trace.verify(gate, setters=0)
    return result


def edit(gate, document, before, field, value, trace):
    result = gate.write("document", "image-quality-set", field, annotations.scalar_argument(value),
        "--if-quality", json.dumps(before["quality"], allow_nan=False),
        "--if-update-stamp", before["document"]["update_stamp"], document=document)
    validate_operation_result("document.image-quality-set", result)
    trace.verify(gate, setters=int(result["changed"]))
    gate.background(result, document)
    require(exact_snapshot(result["before"], before["quality"]) and result["quality"][field] == value,
            "quality CAS/target readback differs")
    if not result["changed"]:
        require(result["document"] == before["document"], "quality noop changed document state")
    return result


def public_mcp_observation(gate, document, current, trace):
    """Discover the installed public contract and read the exact background handle."""
    bridge = DaemonBridge(endpoint=gate.endpoint, session_id=gate.session+"-mcp", timeout_seconds=600)
    capability = bridge.call("capabilities", {"operation": "document.image-quality-set"})
    require(capability.get("success") is True, "MCP public schema discovery failed")
    contract = capability["result"]
    require(contract["operation_schemas"]["document.image-quality-set"] == OPERATION_CATALOG["document.image-quality-set"].parameters
            and contract["operation_result_schemas"]["document.image-quality-set"] == OPERATION_CATALOG["document.image-quality-set"].result,
            "MCP installed request/result contract differs")
    reply = bridge.call("execute", dict(operation="document.image-quality", parameters={},
        document_id=document, expected_update_stamp=current["document"]["update_stamp"]))
    require(reply.get("success") is True, "MCP public image-quality observation failed")
    result = reply["result"]
    validate_operation_result("document.image-quality", result)
    require(result["document"]["document_id"] == document
            and result["document"]["active"] is False and result["document"]["current"] is False
            and exact_snapshot(result["quality"], current["quality"]), "MCP background identity/raw quality differs")
    proof = trace.verify(SimpleNamespace(record=dict(events=[dict(command=["MCP", "document", "image-quality"],
        result={**result, "request_id":reply["request_id"]})])), setters=0)
    return dict(capabilities=capability, read=reply, native_call_proof=proof, request_timeout_seconds=600)


def open_saved(gate, saved, kind, *, read_only):
    result = gate.command("document", "open", saved["host_path"], *(("--read-only",) if read_only else ()))
    require(result["api_errors"] == result["api_warnings"] == 0 and result["read_only"] is read_only
        and result["document"]["type"] == 1 and result["document"]["modified"] is False
        and Path(result["document"]["path"]) == Path(saved["host_path"]), "quality native reopen path/type/access/clean failed")
    document = result["document"]["document_id"]
    foreground = gate.create()
    if not read_only: gate.command("document", "lease", "acquire", "--ttl-seconds", 600, document=document)
    return result, document, foreground


def run(gate, trace, swconst):
    gate.record["decoder_versions"] = {package: importlib.metadata.version(package) for package in ("DracoPy", "numpy")}
    gate.record["swconst"] = constants(swconst)
    health = gate.health(); gate.record["host"] = health["host"]
    require(health["server_version"] == __version__ and health["host"]["owned_by_daemon"] is True
        and health["host"]["visible"] is False and health["host"]["shared_interactive"] is False,
        "quality calibration requires one owned hidden matching-version host")
    gate.require_empty()
    for shape in ("cylinder", "box"):
        case = dict(shape=shape, success=False, levels=[]); gate.record["cases"].append(case)
        document = gate.create(); foreground = gate.create()
        gate.command("document", "lease", "acquire", "--ttl-seconds", 600, document=document)
        profile = gate.circle(document, radius=10) if shape == "cylinder" else gate.rectangle(document)
        case["profile"] = profile
        case["extrusion"] = gate.feature(document, profile["sketch"]["sketch_id"], depth=10)
        volume, area = (1000*math.pi, 400*math.pi) if shape == "cylinder" else (12000, 3800)
        geometry = gate.measure(document, volume=volume, area=area)["metrics"]; case["geometry"] = geometry
        current = case["initial"] = read(gate, document, trace)
        # SDK must read the same exact document under a separate session without mutation.
        sdk = Client(endpoint=gate.endpoint, session_id=gate.session+"-sdk", timeout_seconds=600)
        reply = sdk.document.image_quality(document_id=document, expected_update_stamp=current["document"]["update_stamp"])
        case["sdk_read"] = reply.raw
        require(reply.ok and exact_snapshot(reply.require_result()["quality"], current["quality"])
                and reply.require_result()["document"]["document_id"] == document
                and reply.require_result()["document"]["active"] is False
                and reply.require_result()["document"]["current"] is False,
                "SDK quality or exact background identity mapping disagrees with public CLI")
        if gate.public_acceptance:
            case["mcp"] = public_mcp_observation(gate, document, current, trace)
        require(current["quality"]["apply_to_referenced_parts"] is False and current["quality"]["shaded_mode"] != "other", "unsupported initial image quality profile")
        # Keep an immutable, independently reopened baseline before the first
        # preference setter. A first-call failure must leave native input evidence.
        baseline = case["baseline_save"] = annotations.save_copy(gate, document, shape+"-baseline.SLDPRT", "SLDPRT")
        expected_baseline = current["quality"]
        require(exact_snapshot(read(gate, document, trace)["quality"], expected_baseline), "baseline save changed raw quality")
        gate.close(document); gate.close(foreground)
        baseline_open, baseline_document, foreground = open_saved(gate, baseline, shape, read_only=True)
        case["baseline_readonly_open"] = baseline_open
        case["baseline_reopened_quality"] = read(gate, baseline_document, trace)
        require(baseline_document != document and exact_snapshot(case["baseline_reopened_quality"]["quality"], expected_baseline),
                "baseline raw quality did not persist to a fresh readonly handle")
        annotations.same_geometry(geometry, gate.measure(baseline_document, volume=volume, area=area)["metrics"])
        require(hashlib.sha256(Path(baseline["path"]).read_bytes()).hexdigest() == baseline["sha256"], "readonly baseline observation changed native input")
        gate.close(baseline_document); gate.close(foreground)
        writable_open, document, foreground = open_saved(gate, baseline, shape, read_only=False)
        case["baseline_writable_open"] = writable_open
        current = case["baseline_writable_quality"] = read(gate, document, trace)
        require(exact_snapshot(current["quality"], expected_baseline), "writable baseline reopen lost raw quality")
        case["edge_write"] = current = edit(gate, document, current, "optimize_edge_length", not current["quality"]["optimize_edge_length"], trace)
        # Full-value CAS refusal even when stamp is unchanged: no setter allowed.
        stale = json.loads(json.dumps(current["quality"]))
        stale["save_tessellation"] = stale["native"]["save_tessellation"] = not stale["save_tessellation"]
        case["cas_refusal"] = gate.write("document", "image-quality-set", "optimize_edge_length", annotations.scalar_argument(not current["quality"]["optimize_edge_length"]),
            "--if-quality", json.dumps(stale), "--if-update-stamp", current["document"]["update_stamp"], document=document, expected_error="DocumentImageQualityConflict")
        trace.verify(gate, setters=0)
        for mode in ("coarse", "fine", "custom"):
            row = dict(mode=mode, success=False); case["levels"].append(row)
            if mode != "custom":
                row["mode_write"] = current = edit(gate, document, current, "shaded_mode", mode, trace)
            if mode == "custom":
                bounds = current["quality"]["deviation_range"]
                require(bounds["status"] == 0, "custom quality native range unavailable")
                low, high = bounds["bounds_m"]
                target = (low+(high-low)*0.25)*1000
                if math.isclose(target, current["quality"]["shaded_deviation_mm"], rel_tol=1e-12, abs_tol=1e-12):
                    target = (low+(high-low)*0.75)*1000
                require(target > 0 and not math.isclose(target, current["quality"]["shaded_deviation_mm"], rel_tol=1e-12, abs_tol=1e-12), "custom deviation must actually change")
                row["deviation_write"] = current = edit(gate, document, current, "shaded_deviation_mm", target, trace)
                require(current["quality"]["shaded_mode"] == "custom", "single deviation setter did not establish custom mode")
            if gate.document_properties and mode == "custom":
                # An explicit second requested test value, never failure
                # rollback: verify disabling independently after enabling.
                row["edge_disable_write"] = current = edit(gate, document, current, "optimize_edge_length", False, trace)
            row["noops"] = []
            for field in IMAGE_QUALITY_FIELDS:
                if field == "shaded_mode" and current["quality"]["shaded_mode"] == "custom":
                    continue  # custom is an observation, never an Integer write target
                current = edit(gate, document, current, field, current["quality"][field], trace)
                row["noops"].append(current)
            expected = current["quality"]
            saved = row["native_save"] = annotations.save_copy(gate, document, shape+"-"+mode+".SLDPRT", "SLDPRT")
            saved_quality = row["saved_quality"] = read(gate, document, trace)
            require(exact_snapshot(expected, saved_quality["quality"]), "native save changed quality snapshot")
            if not gate.document_properties:
                output = gate.directory/(shape+"-"+mode+".glb")
                row["export"] = gate.write("document", "export", str(output), "--strict", document=document)
                require(not row["export"].get("warnings") and row["export"]["artifact"]["size_bytes"] == output.stat().st_size, "GLB export warnings/size mismatch")
                row["mesh"] = inspect_glb(output)
            require(exact_snapshot(read(gate, document, trace)["quality"], expected), "GLB export changed quality")
            annotations.same_geometry(geometry, gate.measure(document, volume=volume, area=area)["metrics"])
            gate.close(document); gate.close(foreground)
            reopened, fresh, foreground = open_saved(gate, saved, shape, read_only=True)
            row["reopen"] = reopened
            require(fresh != document, "native quality reopen reused stale document identity")
            row["reopened_quality"] = read(gate, fresh, trace)
            require(exact_snapshot(row["reopened_quality"]["quality"], expected), "complete raw quality did not persist after reopen")
            annotations.same_geometry(geometry, gate.measure(fresh, volume=volume, area=area)["metrics"])
            require(hashlib.sha256(Path(saved["path"]).read_bytes()).hexdigest() == saved["sha256"], "readonly quality reopen changed saved file")
            gate.close(fresh); gate.close(foreground)
            row["success"] = True
            if mode != "custom":
                opened, document, foreground = open_saved(gate, saved, shape, read_only=False)
                row["next_writable_open"] = opened
                current = read(gate, document, trace)
                require(exact_snapshot(current["quality"], expected), "writable reopen lost raw quality")
        if not gate.document_properties:
            counts = {row["mode"]: row["mesh"]["triangles"] for row in case["levels"]}
            case["triangle_counts"] = counts
            case["quality_associated_triangle_difference_observed"] = len(set(counts.values())) > 1
            case["format_materials_extensions_stable"] = all(all(row["mesh"][key] == case["levels"][0]["mesh"][key]
                for key in ("materials", "extensions_used", "extensions_required", "camera_count", "animation_count", "scene_extensions")) for row in case["levels"])
            require(case["format_materials_extensions_stable"], "GLB material/extension/scene controls drifted between quality levels")
        require(hashlib.sha256(Path(baseline["path"]).read_bytes()).hexdigest() == baseline["sha256"], "quality experiment modified its original native baseline")
        case["success"] = True
        gate.require_empty()
    gate.record["host_after"] = gate.health()["host"]
    require(gate.record["host_after"] == gate.record["host"], "quality calibration host state changed")
    gate.record.update(state="completed", success=True,
        image_quality_calibration_passed=not gate.public_acceptance, public_acceptance_passed=gate.public_acceptance,
        image_quality_writes_accepted=gate.public_acceptance, glb_control_proven=False,
        optimize_edge_length_verified_values=[True, False] if gate.document_properties else [True])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--native-trace", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--endpoint", default=modeling.DEFAULT_ENDPOINT)
    parser.add_argument("--document-properties", action="store_true", help="independent document-properties evidence group; does not export or claim GLB meshes")
    parser.add_argument("--public-acceptance", action="store_true", help="document-property public route, with calibration switches absent")
    parser.add_argument("--inside-watchdog", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.public_acceptance and (not args.document_properties or any(os.environ.get(name) == "1" for name in
            ("SWCLI_IMAGE_QUALITY_CALIBRATION", "SWCLI_GLB_PLAIN_STAGING_CALIBRATION"))):
        parser.error("public acceptance requires the document-properties profile and both calibration switches absent")
    if not args.inside_watchdog:
        # External watchdog also bounds a hung CLI, SDK, decoder, or cleanup.
        try:
            return subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()),
                *(sys.argv[1:] if argv is None else argv), "--inside-watchdog"], timeout=1800).returncode
        except subprocess.TimeoutExpired:
            (args.output_dir/"group-timeout.json").write_text(json.dumps(dict(success=False, first_failure="hard 1800-second group deadline", full_acceptance_eligible=False)))
            return 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    gate = QualitySmoke(directory=args.output_dir.resolve(), host_directory=str(args.output_dir.resolve()), endpoint=args.endpoint, document_properties=args.document_properties, public_acceptance=args.public_acceptance)
    gate.record_path = args.output_dir/"image-quality.json"
    with gate.record_path.open("x") as stream: json.dump(gate.record, stream)
    trace = Trace(args.native_trace)
    try:
        require(args.native_trace.is_file() and args.swconst.is_file(), "quality trace and official swconst are required")
        run(gate, trace, args.swconst)
    except BaseException as exc:
        gate.record.update(state="failed", success=False, image_quality_writes_accepted=False, public_acceptance_passed=False,
            image_quality_calibration_passed=False, error=dict(type=type(exc).__name__, message=str(exc)))
        raise
    finally:
        gate.cleanup()
        if gate.record["cleanup_errors"]:
            gate.record.update(state="failed", success=False, image_quality_writes_accepted=False,
                public_acceptance_passed=False, image_quality_calibration_passed=False)
        gate.checkpoint("image-quality-final")
    if gate.checkpoint_error: raise gate.checkpoint_error
    require(not gate.record["cleanup_errors"], "quality cleanup failed")
    return 0


if __name__ == "__main__": raise SystemExit(main())
