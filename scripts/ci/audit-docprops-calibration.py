"""Fail-closed audit of the baseline properties diagnostic; never public acceptance."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trace_state(path):
    active = None
    started = None
    first_error = None
    records = []
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        if not line.endswith("\n"):
            raise ValueError("truncated trace record")
        row = json.loads(line)
        name, phase = row["call"], row["phase"]
        if phase == "begin":
            if active is not None:
                raise ValueError("nested or unfinished native call")
            active = name
            started = row["time"]
        elif phase in ("end", "error"):
            if active != name:
                raise ValueError("unmatched trace completion")
            if phase == "end" and not 0 <= row["time"] - started <= 600:
                raise ValueError("native call exceeded budget or clock regressed")
            active = None
            if phase == "error" and first_error is None:
                first_error = row
        else:
            raise ValueError("unknown trace phase")
        records.append(row)
    return active, first_error, records


def audit(root, expected_head):
    root = Path(root)
    errors = []
    first_failure = None
    def require(ok, message):
        if not ok:
            errors.append(message)
    try:
        driver = json.loads((root / "driver.json").read_text(encoding="utf-8"))
        report = json.loads((root / "native/report.json").read_text(encoding="utf-8"))
        first_failure = report.get("failure") or driver.get("failure")
        active, first_error, records = trace_state(root / "native/trace.jsonl")
        first_failure = first_error or report.get("failure") or driver.get("failure")
        require(driver["source_head"] == expected_head, "source head mismatch")
        require(driver["platform"] == "win32", "not a Windows execution")
        require(0 <= driver["elapsed_seconds"] <= 1800, "group duration exceeded budget")
        require(driver["exit_code"] == 0 and driver.get("failure") is None, "driver failed")
        require(driver["native_timeout_seconds"] == 600 and driver["group_timeout_seconds"] == 1800,
                "incorrect execution budgets")
        require(report["success"] is True and not report.get("failure"), "native report failed")
        require(report["full_acceptance_eligible"] is False, "diagnostic mislabeled as public acceptance")
        require(report["diagnostic_case"] == "document-properties-calibration", "unexpected calibration profile")
        host = report["host"]
        require(type(host["process_id"]) is int and host["process_id"] > 0 and bool(host["revision"]),
                "actual host identity missing")
        require(report["cleanup_errors"] == [], "native cleanup failed")
        require(active is None and first_error is None and bool(records), "native trace incomplete or failed")
        begins = [r["call"] for r in records if r["phase"] == "begin"]
        require(begins.count("acquire-owned-host") == 1, "host acquisition not exactly once")
        required = ["ExitApp", "WaitForOwnedProcess", "CloseProcessHandle", "CoUninitialize"]
        require(begins[-4:] == required, "owned host exit/cleanup sequence missing")
        cases = report["cases"]
        require([c["kind"] for c in cases] == ["part", "assembly"], "fixture plan mismatch")
        for case in cases:
            suffix = "SLDPRT" if case["kind"] == "part" else "SLDASM"
            saved = root / "native" / ("properties." + suffix)
            require(saved.is_file() and saved.stat().st_size > 0, "saved native copy missing")
            require(case["success"] is True and case["file_sha256"] == digest(saved), "saved copy hash mismatch")
            require(case["state_before"] == case["state_after"], "read mutated fixture state")
            require(case["listing"]["properties"] == case["reopened_properties"]["properties"],
                    "save/reopen property mismatch")
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        errors.append("missing or invalid original evidence: " + str(error))
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            errors.append("symlink in evidence: " + str(path.relative_to(root)))
        elif path.is_file() and path.name != "audit.json":
            files.append(dict(path=path.relative_to(root).as_posix(), bytes=path.stat().st_size, sha256=digest(path)))
    return dict(schema_version=1, scope="internal-calibration", full_acceptance_eligible=False,
                source_head=expected_head, success=not errors, errors=errors,
                first_failure=first_failure, originals=files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    args = parser.parse_args()
    result = audit(args.evidence, args.expected_head)
    (args.evidence / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("success", "scope", "errors", "first_failure")}))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
