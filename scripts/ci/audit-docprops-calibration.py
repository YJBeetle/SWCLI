"""Check baseline evidence structure only; cannot establish native calibration or source provenance."""
import argparse
import hashlib
import json
import re
from pathlib import Path


FIXTURE = {"Chinese Name": (30, "测试零件"), "English Name": (30, "Property fixture"),
           "Drawing No": (30, ""), "Quantity": (3, "42"), "Approved": (11, "Yes")}
CASE_CALLS = (["create-properties-fixture", "document-property-manager"]
              + ["seed-document-property-" + n for n in FIXTURE]
              + ["seed-configuration-shadow", "create-foreground", "list-properties"]
              + ["lookup-" + n for n in FIXTURE]
              + ["lookup-missing", "close-foreground", "save-properties", "close-properties-fixture",
                 "reopen-properties-readonly", "read-reopened-properties", "close-reopened-properties"])
PLAN = (["read-official-swconst", "acquire-owned-host", "wait-ready", "capture-owned-process"]
        + CASE_CALLS * 2 + ["ExitApp", "WaitForOwnedProcess", "CloseProcessHandle", "CoUninitialize"])


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
        require(begins == PLAN, "missing, duplicated or out-of-order fixture/read/save/reopen calls")
        required = ["ExitApp", "WaitForOwnedProcess", "CloseProcessHandle", "CoUninitialize"]
        require(begins[-4:] == required, "owned host exit/cleanup sequence missing")
        cases = report["cases"]
        require([c["kind"] for c in cases] == ["part", "assembly"], "fixture plan mismatch")
        for case in cases:
            suffix = "SLDPRT" if case["kind"] == "part" else "SLDASM"
            saved = root / "native" / ("properties." + suffix)
            require(saved.is_file() and saved.stat().st_size >= 512, "saved native copy missing or implausibly short")
            require(saved.read_bytes()[:8] == bytes.fromhex("d0cf11e0a1b11ae1"), "saved copy lacks compound-file header")
            require(case["success"] is True and case["file_sha256"] == digest(saved), "saved copy hash mismatch")
            require(case["state_before"] == case["state_after"], "read mutated fixture state")
            state = case["state_before"]
            require(len(state) == 4 and state[0] == (1 if case["kind"] == "part" else 2)
                    and type(state[1]) is int and type(state[2]) is bool and bool(state[3]), "invalid state snapshot")
            listing = case["listing"]
            rows = {r["name"]: r for r in listing["properties"]}
            require(len(listing["properties"]) == 5 and set(rows) == set(FIXTURE), "five fixture properties required")
            for name, (code, value) in FIXTURE.items():
                row = rows[name]
                require(row["type_code"] == code and row["raw_value"] == value, "fixture type/value mismatch: " + name)
                lookup = case["lookups"][name]
                require(lookup["ok"] is True and lookup["requested_name"] == name and lookup["properties"] == [row],
                        "fixture query mismatch: " + name)
            require(rows["Drawing No"]["evaluated_value"] == "", "empty property/configuration shadow mismatch")
            require(case["missing"]["ok"] is True and case["missing"]["requested_name"] == "Absent property"
                    and case["missing"]["properties"] == [], "missing lookup not proved")
            require(listing["ok"] is True and listing["scope"] == "document" and listing["requested_name"] is None,
                    "listing scope mismatch")
            original = listing["document"]
            reopened = case["reopened_properties"]["document"]
            require(original["active"] is False and original["current"] is False, "background read not recorded")
            require(all(re.fullmatch(r"d-[0-9a-f]+", d["document_id"]) for d in (original, reopened))
                    and original["document_id"] != reopened["document_id"], "fresh reopened document identity missing")
            require(reopened["modified"] is False and case["reopen"]["read_only"] is True
                    and case["reopen"]["ok"] is True and case["reopen"]["api_errors"] == case["reopen"]["api_warnings"] == 0,
                    "clean readonly reopen not recorded")
            require(case["save"]["ok"] is True, "save receipt failed")
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
    return dict(schema_version=2, scope="evidence-structure-only", full_acceptance_eligible=False,
                expected_head=expected_head, source_provenance_verified=False, calibration_passed=False,
                structure_complete=not errors, errors=errors,
                first_failure=first_failure, originals=files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    args = parser.parse_args()
    result = audit(args.evidence, args.expected_head)
    (args.evidence / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("structure_complete", "calibration_passed", "source_provenance_verified", "scope", "errors", "first_failure")}))
    return 0 if result["structure_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
