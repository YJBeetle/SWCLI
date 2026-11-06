"""Independently audit a downloaded internal Line Font artifact without COM."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from swcli.document_line_font import LINE_FONT_FIELDS


OBSERVATION_CALLS = {
    "ActiveDoc", "ActiveDrawingView", "ActiveSketch", "Extension", "GetCurrentSheet",
    "GetDocuments", "GetEditSheet", "GetFirstView", "GetName", "GetName2", "GetPathName",
    "GetReferencedModelName", "GetSaveFlag", "GetSketch", "GetTemplateSketch", "GetTitle",
    "GetType", "GetUpdateStamp", "IsOpenedReadOnly", "IsOpenedViewOnly", "SketchManager",
    "RevisionNumber",
}


def audit(root):
    report_path, = root.rglob("line-font-calibration/report.json")
    folder = report_path.parent
    report = json.loads(report_path.read_text())
    def require(condition, message):
        if not condition:
            raise RuntimeError(message)
    require(report["success"] and not report["cleanup_errors"] and not report["full_acceptance_eligible"], "internal run/cleanup failed or claims public acceptance")
    require(report["diagnostic_case"] == "internal-document-line-font" and len(report["cases"]) == 1, "unexpected internal case plan")
    case = report["cases"][0]
    require(case["success"] and case["initial"]["ok"] and not case["initial"]["document"]["active"]
            and not case["initial"]["document"]["current"], "initial background read failed")
    rejected = case["public_write_rejection"]
    require(not rejected["ok"] and rejected["error"]["type"] == "DocumentLineFontUncalibrated"
            and rejected["mutation"] == dict(attempted=False, may_have_changed=False), "public gate was open during calibration")
    writes = case["internal_writes"]
    require(len(writes) == 4 and [row["field"] for row in writes] == list(LINE_FONT_FIELDS), "internal write plan incomplete")
    current = case["initial"]["options"]
    transitions = {}
    for row in writes:
        field = row["field"]
        require(row["ok"] and row["changed"] and row["before"] == current
                and row["mutation"] == dict(attempted=True, may_have_changed=True), "internal mutation failed")
        after = row["options"]
        require(after[field] != current[field] and after == {**current, field: after[field]}, "unrequested defaults changed")
        transitions[field] = [current[field], after[field]]
        current = after
    require(case["final_options"] == current == case["reopened"]["options"] and case["reopened"]["ok"], "reopened defaults differ")
    require(case["save"]["ok"] and case["save"]["api_saved"] and case["save"]["save_errors"] == 0, "native save failed")
    drawing = folder / "line-font.SLDDRW"
    require(drawing.stat().st_size >= 512 and hashlib.sha256(drawing.read_bytes()).hexdigest() == case["file_sha256"], "saved fixture digest differs")
    events = [json.loads(line) for line in (folder / "process.log").read_text(encoding="utf-8-sig").splitlines()
              if line.startswith('{"event": "swcli.native-call"')]
    proofs = []
    for field in LINE_FONT_FIELDS:
        operation = "internal-single-write-" + field
        rows = [row for row in events if row["operation"] == operation]
        require(rows and len({row["request_id"] for row in rows}) == 1, "internal request trace missing/repeated")
        begins = Counter((row["sequence"], row["call"]) for row in rows if row["phase"] == "begin")
        ends = Counter((row["sequence"], row["call"]) for row in rows if row["phase"] == "end")
        require(begins == ends and all(n == 1 for n in begins.values()) and not any(row["phase"] == "error" for row in rows), "native calls failed/repeated/incomplete")
        calls = [row["call"] for row in rows if row["phase"] == "begin" and row["sequence"] != 0]
        getter, setter = "IModelDocExtension.GetUserPreferenceInteger", "IModelDocExtension.SetUserPreferenceInteger"
        require(all(call in OBSERVATION_CALLS | {getter, setter, "IModelDoc2.SetSaveFlag"} for call in calls),
                "unrecognized native method in internal operation")
        observations = [call for call in calls if call in OBSERVATION_CALLS]
        calls = [call for call in calls if call not in OBSERVATION_CALLS]
        require(calls.count(getter) == 12 and calls.count(setter) == 1 and calls.count("IModelDoc2.SetSaveFlag") <= 1,
                "internal getter/setter counts differ")
        expected = [getter]*4 + [setter] + [getter]*4
        if "IModelDoc2.SetSaveFlag" in calls:
            expected.append("IModelDoc2.SetSaveFlag")
        require(calls == expected + [getter]*4, "native write order differs or global mutation was called")
        proofs.append(dict(field=field, request_id=rows[0]["request_id"], calls=calls, observation_calls=observations))
    return dict(success=True, evidence_kind="independent-internal-artifact-audit", public_acceptance=False,
                host=report["host"], transitions=transitions, fixture_sha256=case["file_sha256"], native_call_proofs=proofs,
                report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest(),
                trace_sha256=hashlib.sha256((folder / "trace.jsonl").read_bytes()).hexdigest(),
                native_process_log_sha256=hashlib.sha256((folder / "process.log").read_bytes()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.root), indent=2) + "\n")


if __name__ == "__main__":
    main()
