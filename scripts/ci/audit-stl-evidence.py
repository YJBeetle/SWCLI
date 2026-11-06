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


def audit(directory, expected_head):
    reports = list(directory.rglob("stl-calibration.json"))
    require(len(reports) == 1, "exactly one original STL report is required")
    report_path = reports[0]
    root = report_path.parent
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    require(report.get("success") is True and report.get("source_commit") == expected_head,
            "native report did not pass at the expected commit")
    require(report.get("public_acceptance") is False and report.get("full_acceptance") is False,
            "internal calibration must not claim public or full acceptance")
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
        save_calls = [r for r in trace if r["phase"] == "begin" and r["call"] == "IModelDoc2.SaveAs3"]
        require(len(save_calls) == 1, "export trace does not contain exactly one native save")
        setters = [r for r in trace if r["phase"] == "begin" and r.get("stage") == "stl-preferences-write"]
        reads = [r for r in trace if r["phase"] == "begin" and r.get("stage") == "stl-preferences-read"]
        require(len(setters) == 16 and len(reads) == 96,
                "full preference snapshot/CAS/set/readback/restore trace is incomplete")
        workers.update(r["worker_pid"] for r in trace)
        cases.append(dict(name=case["name"], request_id=request, **metrics,
                          native_save_count=len(save_calls), preference_set_count=len(setters),
                          preference_read_count=len(reads)))
    require(len(workers) == 1, "calibration replaced its COM worker between cases")
    require({c["name"] for c in cases} == {"coarse", "deviation-fine", "angle-fine", "fine", "ascii-inch", "binary-meter"},
            "planned independent tolerance/encoding/unit cases are incomplete")
    by_name = {c["name"]: c for c in cases}
    for name in ("deviation-fine", "angle-fine", "fine"):
        require(by_name[name]["triangle_count"] > by_name["coarse"]["triangle_count"]
                and by_name[name]["volume_relative_error"] < by_name["coarse"]["volume_relative_error"],
                "retained output does not prove individual tolerance improvement: " + name)
    for name in ("ascii-inch", "binary-meter"):
        require(by_name[name]["triangle_count"] == by_name["fine"]["triangle_count"]
                and abs(by_name[name]["volume_mm3"]-by_name["fine"]["volume_mm3"])/by_name["fine"]["volume_mm3"] < 1e-4,
                "retained unit/encoding variant does not preserve scaled geometry")
    return dict(success=True, scope="independent-internal-stl-audit", source_commit=expected_head,
                report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest(),
                native_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                trace_sha256=hashlib.sha256((root / "daemon.stderr.log").read_bytes()).hexdigest(),
                worker_pid=next(iter(workers)), cases=cases,
                native_constants=report["cases"][0]["result"]["stl_preferences"]["constants"],
                host=report["health"]["result"]["host"], public_acceptance=False, full_acceptance=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.evidence_root, args.expected_head)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))

if __name__ == "__main__":
    main()
