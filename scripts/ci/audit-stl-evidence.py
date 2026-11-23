"""Independently audit retained STL report, bytes, source digest and native trace."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath

spec = importlib.util.spec_from_file_location("_stl_metrics", Path(__file__).with_name("verify-stl-options.py"))
metrics_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics_module)
require = metrics_module.require


def audit(directory, expected_head, *, phase="internal"):
    reports = list(directory.rglob("stl-calibration.json"))
    require(len(reports) == 1, "exactly one original STL report is required")
    report_path = reports[0]
    root = report_path.parent
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    require(report.get("success") is True and report.get("source_commit") == expected_head,
            "native report did not pass at the expected commit")
    public = phase == "public"
    require(report.get("public_acceptance") is public and report.get("full_acceptance") is False,
            "internal calibration must not claim public or full acceptance; public audit requires an explicit public result")
    if public:
        from swcli.stl_calibrated_profiles import QUALIFICATION, PROFILES, NATIVE_ENUMS
        require(report.get("scope") == "public-isolated-stl-options" and report.get("qualification") == QUALIFICATION,
                "public evidence does not reference the installed audited qualification")
        require(report["daemon_export_mode"]["internal_calibration"] is False
                and report["daemon_export_mode"]["explicit_exclusive_runner"] is True,
                "public evidence enabled the internal calibration bypass")
    require(report.get("native_timeout_seconds") == 600 and report.get("group_timeout_seconds") == 1800,
            "native timeout contract changed")
    require(not report.get("cleanup_errors"), "native report contains cleanup errors")
    source = root / PureWindowsPath(report["saved_reopened_fixture"]["path"]).name
    require(hashlib.sha256(source.read_bytes()).hexdigest() == report["saved_reopened_fixture"]["sha256"],
            "saved/reopened native fixture digest differs from retained original")
    require(report["saved_reopened_fixture"]["open_result"]["ok"] is True,
            "saved fixture reopen did not succeed")
    records = []
    for line in (root / "daemon.stderr.log").read_text(encoding="utf-8-sig").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            require('"swcli.native-call"' not in line, "malformed native trace row")
            continue
        if row.get("event") == "swcli.native-call":
            records.append(row)
    require(records, "no original native trace records")
    workers = set()
    baseline = None
    cases = []
    for case in report["cases"]:
        require(case.get("success") is True, "a planned native case did not complete")
        result = case["result"]
        prefs = result["stl_preferences"]
        if public:
            names = [name for name, options in PROFILES.items() if case["options"] == options]
            require(len(names) == 1 and prefs.get("execution_mode") == "public-isolated"
                    and prefs.get("calibrated_profile") == names[0] and prefs["constants"] == NATIVE_ENUMS,
                    "public export did not use the exact qualified native profile")
            if case["name"] == "mcp-fine":
                transport = case["mcp_transport"]
                require(transport["transport"] == "official-sdk-stdio" and transport["server_name"] == "swcli"
                        and "execute" in transport["tools"] and transport["is_error"] is False,
                        "public MCP evidence did not cross the official stdio tool transport")
            catalog = case["post_export_catalog"]["documents"]
            active = [row["document_id"] for row in catalog if row["active"]]
            current = [row["document_id"] for row in catalog if row["current"]]
            require(len(active) == 1 and active == current and active[0] != result["document"]["document_id"],
                    "public foreground/current catalog identity is not preserved")
        require(result["api_saved"] is True
                and type(result["save_errors"]) is type(result["save_warnings"]) is int
                and result["save_errors"] == result["save_warnings"] == 0,
                "modern save bool/error/warning receipt differs")
        require(result["ok"] is True and prefs["restored"] is True and not prefs["cleanup_errors"]
                and prefs["before"] == prefs["after"] and prefs["readback"] == prefs["requested"],
                "preference transaction is not exactly restored and retained")
        returns = prefs.get("setter_returns", [])
        require(len(returns) == 16 and Counter(row["phase"] for row in returns) == {"set": 8, "restore": 8},
                "native setter return evidence is incomplete")
        for row in returns:
            toggle = row["preference"] in {"swSTLBinaryFormat", "swSTLComponentsIntoOneFile", "swSTLShowInfoOnSave", "swSTLPreview"}
            require((row["return_type"] == "NoneType" and row["value"] is None) if toggle
                    else (row["return_type"] == "bool" and row["value"] is True),
                    "native setter did not obey its actual void/boolean signature")
        require(result["stl_source_state"]["unchanged"] is True
                and result["stl_source_state"]["before"] == result["stl_source_state"]["after"],
                "native source identity/state changed")
        if baseline is None:
            baseline = prefs["before"]
        require(prefs["before"] == baseline, "global STL preference state leaked between cases")
        path = root / PureWindowsPath(case["path"]).name
        metrics = metrics_module.mesh_metrics(path, unit=case["options"]["unit"],
                                              expected_encoding=case["options"]["encoding"])
        require(metrics == case["mesh"], "independent retained-byte mesh analysis differs from original report")
        require(metrics["max_wall_chord_error_mm"] <= case["options"]["deviation_mm"] + 0.001,
                "retained curved mesh exceeds requested deviation")
        request = result["request_id"]
        trace = [r for r in records if r.get("request_id") == request]
        require(trace and all(r.get("operation") == "document.export" for r in trace),
                "export request has missing/mismatched trace correlation")
        begins = Counter((r["sequence"], r["call"]) for r in trace if r["phase"] == "begin")
        ends = Counter((r["sequence"], r["call"]) for r in trace if r["phase"] == "end")
        require(begins == ends and all(n == 1 for n in begins.values())
                and begins[(0, "document.export")] == 1,
                "native trace contains errors, retries, missing or duplicated call boundaries")
        save_calls = [r for r in trace if r["phase"] == "begin" and r["call"].startswith(("IModelDoc2.SaveAs", "IModelDocExtension.SaveAs"))]
        require(len(save_calls) == 1 and save_calls[0]["call"] == "IModelDocExtension.SaveAs3", "export trace does not contain exactly one native save")
        setters = [r for r in trace if r["phase"] == "begin" and r.get("stage") == "stl-preferences-write"]
        reads = [r for r in trace if r["phase"] == "begin" and r.get("stage") == "stl-preferences-read"]
        require(len(setters) == 16 and len(reads) == 96,
                "full preference snapshot/CAS/set/readback/restore trace is incomplete")
        workers.update(r["worker_pid"] for r in trace)
        cases.append(dict(name=case["name"], request_id=request, **metrics,
                          native_save_count=len(save_calls), preference_set_count=len(setters),
                          preference_read_count=len(reads)))
    require(len(workers) == 1, "calibration replaced its COM worker between cases")
    planned = {"coarse", "deviation-fine", "angle-fine", "fine", "ascii-inch", "binary-meter"}
    if public:
        planned.update({"sdk-fine", "mcp-fine"})
        guards = report.get("negative_guards", [])
        require({row["name"] for row in guards} == {"stale-stamp", "foreign-lease", "uncalibrated-profile", "read-only-source"},
                "public native guard evidence is incomplete")
        for guard in guards:
            response = guard["response"]
            require(response["success"] is False and response["error"]["code"] == guard["expected_error"],
                    "public native guard returned the wrong first error")
            trace = [r for r in records if r.get("request_id") == response["request_id"]]
            require(trace and not any(r.get("stage") == "stl-preferences-write" or str(r.get("call", "")).startswith(("IModelDoc2.SaveAs", "IModelDocExtension.SaveAs")) for r in trace),
                    "a rejected public request entered native preference writes or export")
    require({c["name"] for c in cases} == planned,
            "planned independent tolerance/encoding/unit cases are incomplete")
    by_name = {c["name"]: c for c in cases}
    for name in ("deviation-fine", "angle-fine", "fine"):
        require(by_name[name]["triangle_count"] > by_name["coarse"]["triangle_count"]
                and by_name[name]["volume_relative_error"] < by_name["coarse"]["volume_relative_error"],
                "retained output does not prove individual tolerance improvement: " + name)
    for name in (("ascii-inch", "binary-meter", "sdk-fine", "mcp-fine") if public else ("ascii-inch", "binary-meter")):
        require(by_name[name]["triangle_count"] == by_name["fine"]["triangle_count"]
                and abs(by_name[name]["volume_mm3"]-by_name["fine"]["volume_mm3"])/by_name["fine"]["volume_mm3"] < 1e-4,
                "retained unit/encoding variant does not preserve scaled geometry")
    return dict(success=True, scope="independent-public-stl-audit" if public else "independent-internal-stl-audit", source_commit=expected_head,
                report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest(),
                native_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                trace_sha256=hashlib.sha256((root / "daemon.stderr.log").read_bytes()).hexdigest(),
                worker_pid=next(iter(workers)), cases=cases,
                native_constants=report["cases"][0]["result"]["stl_preferences"]["constants"],
                host=report["health"]["result"]["host"], public_acceptance=public, full_acceptance=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("internal", "public"), default="internal")
    args = parser.parse_args()
    result = audit(args.evidence_root, args.expected_head, phase=args.phase)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))

if __name__ == "__main__":
    main()
