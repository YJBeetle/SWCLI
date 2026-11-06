#!/usr/bin/env python3
"""Summarize caller-approved public test receipts without changing their verdicts.

This is a reporting tool, not an acceptance gate. It never reads command stdout,
return codes or private installer/licensing inputs to invent a CAD verdict.
"""
import argparse
import html
import json
import math
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

SCHEMA_VERSION = 1
FULL_SET_NAMES = (
    "native-model", "assemblies", "exports", "drawing-save", "drawing-save-as",
    "reverse-cut", "feature-depth", "fillets", "drawings", "continuation-front-diameter",
    "center-front", "rectangle-front", "diameter-top", "center-top", "rectangle-top",
    "diameter-right", "center-right", "rectangle-right", "toolbox",
)
RECEIPTS = {
    "runtime-sets.json", "runtime.json", "properties.json", "visible.json",
    "attach-refusal.json", "equation-dimension-result.json", "equation-dimension.json",
    "modeling.json", "driving-dimensions.json", "drawings.json", "toolbox.json",
}
MAX_RECEIPT_BYTES = 64 * 1024 * 1024


def duration(record):
    for name, scale in (("seconds", 1), ("duration_seconds", 1), ("duration_ms", .001)):
        value = record.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
            return value * scale
    return None


def markdown(value):
    text = html.escape(str(value), quote=False)
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~])", r"\\\1", text)


def run_url(environment):
    server = environment.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    # Validate the literal authority before urlsplit: older Python accepts
    # malformed bracketed hosts that newer versions reject outright.
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]+)?", server):
        return None
    try:
        parsed = urlsplit(server)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    repository, run_id = environment.get("GITHUB_REPOSITORY", ""), environment.get("GITHUB_RUN_ID", "")
    if (parsed.scheme != "https" or not hostname or not re.fullmatch(r"[A-Za-z0-9.-]+", hostname)
            or (port is not None and not 1 <= port <= 65535) or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
            or not re.fullmatch(r"[0-9]+", run_id)):
        return None
    return server + "/" + repository + "/actions/runs/" + run_id


def parse_stage(value):
    if "=" not in value:
        raise argparse.ArgumentTypeError("stage must be NAME=OUTCOME")
    name, outcome = value.split("=", 1)
    if not name.strip():
        raise argparse.ArgumentTypeError("stage name cannot be empty")
    outcome = outcome.strip().lower()
    if outcome in ("success", "pass", "passed"):
        status = "PASS"
    elif outcome in ("failure", "fail", "failed", "timed_out", "action_required", "startup_failure"):
        status = "FAIL"
    elif outcome in ("", "skipped", "skip", "cancelled", "canceled", "neutral", "pending", "queued", "in_progress", "stale"):
        status = "SKIP"
    else:
        raise argparse.ArgumentTypeError("unknown stage outcome: " + outcome)
    return name, status, outcome or "not-executed"


def is_cleanup(name):
    return bool(re.search(r"(?:^|[./_-])cleanup(?:$|[./_-])", name, re.I))


def error_value(value):
    if isinstance(value, dict):
        code = value.get("code") or value.get("type") or "TestFailure"
        message = value.get("message") or value.get("reason") or value.get("error") or code
        return {"code": str(code), "message": str(message)}
    return {"code": "TestFailure", "message": str(value)}


def business_error(record):
    # Never inspect events/commands: nonzero and error responses can be expected.
    for key in ("first_failure", "error", "failure"):
        if record.get(key):
            return error_value(record[key]), 0 if key == "first_failure" else 1
    return None, None


def diagnostic(record):
    return bool(record.get("native_test") == "not-run" or record.get("diagnostic_set") or record.get("diagnostic_test_set")
                or record.get("coverage_scope") in ("selected-set", "direct-native-control", "calibration")
                or (record.get("full_acceptance_eligible") is False
                    and record.get("profile") != "visible-smoke"))


def record_status(record, kind):
    if any(key in record and not isinstance(record[key], list) for key in ("cleanup_errors", "evidence_errors")):
        return "FAIL"
    if record.get("first_failure") or record.get("error") or record.get("failure"):
        return "FAIL"
    if record.get("outcome") in ("skipped", "not-run") or record.get("status") == "skipped":
        return "SKIP"
    if record.get("cleanup_errors") or record.get("evidence_errors"):
        return "FAIL"
    if record.get("state") in ("running", "failed", "initializing") or record.get("status") == "running":
        return "FAIL"
    if "completed" in record and record["completed"] is not True:
        return "FAIL"
    if kind == "toolbox.json":
        return "PASS" if record.get("completed") is True and record.get("outcome") == "passed" and record.get("native_test") == "passed" else "FAIL"
    if kind == "runtime.json" and record.get("success") is None:
        if record.get("completed") is not True or record.get("phase") != "completed":
            return "FAIL"
        if record.get("profile") == "visible-smoke":
            proof = record.get("visible_smoke", {})
            return ("PASS" if isinstance(proof, dict) and record_status(proof, "visible.json") == "PASS"
                    and record.get("server_exit_code") == 0 and record.get("host_process_exited") is True else "FAIL")
        proofs = record.get("functional_sets", {})
        return ("PASS" if record.get("profile") == "hidden-full" and isinstance(proofs, dict) and proofs
                and all(isinstance(proof, dict) and proof.get("completed") is True and proof.get("success") is True
                        for proof in proofs.values()) else "FAIL")
    if record.get("success") is not True:
        return "FAIL"
    if kind in ("modeling.json", "driving-dimensions.json", "drawings.json", "properties.json", "visible.json"):
        return "PASS" if record.get("state") == "completed" else "FAIL"
    if kind in ("runtime.json", "runtime-sets.json"):
        return "PASS" if record.get("completed") is True else "FAIL"
    # Equation's public receipt uses success/failure and has no completed field.
    return "PASS"


class Summary:
    def __init__(self, root, source):
        self.root = Path(root)
        self.source = source
        self.phases = []
        self.cleanup_errors = []
        self.failures = []

    def phase(self, name, status, *, evidence=None, seconds=None, detail=None):
        row = {"name": name, "status": status, "seconds": seconds, "evidence": evidence or []}
        if detail:
            row["detail"] = str(detail)
        self.phases.append(row)
        return row

    def failure(self, phase, error, priority=1):
        self.failures.append((priority, len(self.failures), {
            "phase": phase["name"], **error_value(error), "evidence": phase["evidence"],
        }))

    def cleanups(self, record, phase):
        values = record.get("cleanup_errors", [])
        if not isinstance(values, list):
            values = [{"code": "InvalidEvidence", "message": "cleanup_errors must be a JSON array"}]
        for value in values:
            self.cleanup_errors.append({"phase": phase["name"], **error_value(value), "evidence": phase["evidence"]})

    def stage(self, item):
        name, status, outcome = item
        row = self.phase(name, status, detail=outcome)
        if status == "FAIL":
            if is_cleanup(name):
                self.cleanup_errors.append({"phase": name, "code": "StageFailure", "message": outcome, "evidence": []})
            else:
                self.failure(row, {"code": "StageFailure", "message": outcome}, priority=4)

    def ordinary(self, record, path, kind=None, name=None):
        kind = kind or Path(path).name
        name = name or Path(path).with_suffix("").as_posix()
        if diagnostic(record):
            return self.phase(name, "SKIP", evidence=[path], detail="diagnostic/calibration evidence excluded from public acceptance")
        status = record_status(record, kind)
        row = self.phase(name, status, evidence=[path], seconds=duration(record))
        self.cleanups(record, row)
        if status == "FAIL":
            error, priority = business_error(record)
            children = record.get("sets", [])
            children = children if isinstance(children, list) else []
            nested_cleanup_only = (kind == "runtime-sets.json" and any(
                isinstance(item, dict) and item.get("cleanup_errors") for item in children)
                and not any(isinstance(item, dict) and business_error(item)[0] for item in children))
            if error and not (nested_cleanup_only and not record.get("first_failure")):
                self.failure(row, error, max(priority, 3) if kind == "runtime-sets.json" and priority else priority)
            elif record.get("evidence_errors"):
                self.failure(row, {"code": "EvidenceError", "message": str(record["evidence_errors"])}, 3)
            elif not record.get("cleanup_errors") and not nested_cleanup_only:
                self.failure(row, {"code": "IncompleteEvidence", "message": "Receipt does not confirm completed public acceptance"}, 5)
        return row

    def runtime_sets(self, record, path, name=None):
        row = self.ordinary(record, path, "runtime-sets.json", name)
        if diagnostic(record):
            return
        expected = record.get("expected_sets")
        if not isinstance(expected, list) or not expected or not all(isinstance(x, str) for x in expected):
            expected = list(FULL_SET_NAMES) if record.get("suite") == "full" else []
        canonical = list(FULL_SET_NAMES) if record.get("suite") == "full" else expected
        actual = record.get("sets", [])
        if not isinstance(actual, list) or not all(isinstance(x, dict) and isinstance(x.get("name"), str) for x in actual):
            actual = []
        complete = (canonical and record.get("expected_sets") == canonical
                    and [x["name"] for x in actual] == canonical
                    and all(x.get("success") is True for x in actual))
        if row["status"] == "PASS" and not complete:
            row["status"] = "FAIL"
            self.failure(row, {"code": "IncompleteEvidence", "message": "Runtime full/expected set coverage is incomplete"}, 5)
        by_name = {}
        for item in actual:
            by_name.setdefault(item["name"], []).append(item)
        for expected_name in canonical:
            label = row["name"] + "/" + expected_name
            items = by_name.get(expected_name, [])
            if not items:
                self.phase(label, "SKIP", evidence=[path], detail="not executed")
                continue
            item = items[0]
            status = ("PASS" if item.get("success") is True and isinstance(item.get("cleanup_errors", []), list)
                      and not item.get("cleanup_errors") else "FAIL")
            step = self.phase(label, status, evidence=[path], seconds=duration(item))
            self.cleanups(item, step)
            error, priority = business_error(item)
            if error:
                self.failure(step, error, 0 if priority == 0 else max(priority, 2))
            elif status == "FAIL" and not item.get("cleanup_errors"):
                self.failure(step, {"code": "IncompleteEvidence", "message": "Runtime set did not complete successfully"}, 5)
            if len(items) != 1:
                step["status"] = "FAIL"
                self.failure(step, {"code": "DuplicateEvidence", "message": "Repeated runtime set"}, 3)

    def receipt(self, path, direct_runtime_paths):
        relative = path.relative_to(self.root).as_posix()
        if path.is_symlink() or not path.is_file():
            row = self.phase(Path(relative).with_suffix("").as_posix(), "FAIL", evidence=[relative])
            self.failure(row, {"code": "EvidenceError", "message": "Receipt is not a regular non-symlink file"}, 3)
            return
        try:
            if path.stat().st_size > MAX_RECEIPT_BYTES:
                raise ValueError("Receipt exceeds summary size limit")
            record = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(record, dict):
                raise ValueError("Public acceptance receipt must be a JSON object")
        except (OSError, ValueError) as exc:
            row = self.phase(Path(relative).with_suffix("").as_posix(), "FAIL", evidence=[relative])
            self.failure(row, {"code": "UnreadableEvidence", "message": str(exc)}, 6)
            return
        if path.name == "runtime-sets.json":
            self.runtime_sets(record, relative)
        elif path.name == "runtime.json" and isinstance(record.get("functional_sets"), dict):
            self.ordinary(record, relative)
            # Mac adapter embeds the same shared receipts. Prefer actual files
            # when they were collected, otherwise use the embedded public proof.
            has_direct = any(p.is_relative_to(path.parent) for p in direct_runtime_paths)
            if not has_direct and not diagnostic(record):
                for mode, proof in sorted(record["functional_sets"].items()):
                    if isinstance(proof, dict):
                        self.runtime_sets(proof, relative, name=Path(relative).with_suffix("").as_posix() + "/" + mode)
        else:
            if path.name == "runtime.json" and record.get("profile") == "visible-smoke":
                # Outer Mac completion is valid only with its embedded shared gate.
                embedded = record.get("visible_smoke")
                if isinstance(embedded, dict) and record_status(embedded, "visible.json") != "PASS":
                    record = dict(record, success=False)
            self.ordinary(record, relative)

    def scan(self):
        if not self.root.exists():
            self.phase("public-evidence", "SKIP", detail="evidence root does not exist; no public acceptance claimed")
            return
        if self.root.is_symlink() or not self.root.is_dir():
            row = self.phase("public-evidence", "FAIL")
            self.failure(row, {"code": "EvidenceError", "message": "Evidence root must be a non-symlink directory"}, 3)
            return
        paths = []
        for directory, names, files in os.walk(self.root, followlinks=False):
            names[:] = sorted(n for n in names if not Path(directory, n).is_symlink()
                              and n not in (".git", "__pycache__")
                              and not n.lower().startswith(("private", "licens"))
                              and "calibration" not in n.lower())
            paths.extend(Path(directory, name) for name in sorted(files) if name in RECEIPTS)
        if not paths:
            self.phase("public-evidence", "SKIP", detail="no public acceptance receipts found")
        direct = [p for p in paths if p.name == "runtime-sets.json"]
        for path in sorted(paths):
            self.receipt(path, direct)

    def result(self):
        return {"schema_version": SCHEMA_VERSION, "source": self.source, "phases": self.phases,
                "first_failure": min(self.failures, default=(None, None, None))[-1],
                "cleanup_errors": self.cleanup_errors,
                "totals": {"phases": len(self.phases), **{key.lower(): sum(p["status"] == key for p in self.phases)
                                                          for key in ("PASS", "FAIL", "SKIP")}}}


def render(summary):
    source = summary["source"]
    lines = ["## Test summary", "", markdown(source["host"]) + " · " + markdown(source["scope"]), "",
             "Source: " + markdown(source["commit"]) + " · SWCLI " + markdown(source["client_version"]), ""]
    url = source.get("run_url")
    if url:
        lines += ["[Run artifacts](" + url + "#artifacts)", ""]
    total = summary["totals"]
    lines += [f"PASS {total['pass']} · FAIL {total['fail']} · SKIP {total['skip']}", "",
              "| Phase | Status | Seconds | Evidence / detail |", "| --- | --- | ---: | --- |"]
    for row in summary["phases"]:
        evidence = ", ".join(markdown(p) for p in row["evidence"])
        if row.get("detail"):
            evidence += ("; " if evidence else "") + markdown(row["detail"])
        seconds = "—" if row["seconds"] is None else format(row["seconds"], ".3f")
        lines.append("| " + markdown(row["name"]) + " | " + row["status"] + " | " + seconds + " | " + evidence + " |")
    if summary["first_failure"]:
        failure = summary["first_failure"]
        lines += ["", "### First failure", "", markdown(failure["phase"]) + ": " + markdown(failure["code"]) + " — " + markdown(failure["message"])]
    if summary["cleanup_errors"]:
        lines += ["", "### Cleanup errors", ""]
        for error in summary["cleanup_errors"]:
            lines.append("- " + markdown(error["phase"]) + ": " + markdown(error["message"]))
    return "\n".join(lines) + "\n"


def write_report(path, text):
    # Replacing our report path must not follow a stale symlink/hardlink into
    # an original receipt. Only these two generated report names are replaced.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True, help="Caller-approved public receipts only; may not exist")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--host", choices=("windows", "linux-wine", "macos-wine"), required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--client-version", required=True)
    parser.add_argument("--stage", type=parse_stage, action="append", default=[], help="Repeat NAME=GitHub outcome; empty/cancelled means SKIP")
    parser.add_argument("--step-summary", type=Path, help="Append Markdown here (default: GITHUB_STEP_SUMMARY)")
    args = parser.parse_args(argv)
    summary = Summary(args.evidence_root, {"commit": args.source_commit, "client_version": args.client_version,
        "host": args.host, "scope": args.scope, "run_url": run_url(os.environ)})
    for item in args.stage:
        summary.stage(item)
    summary.scan()
    result = summary.result()
    output = args.output_dir
    if output.is_symlink():
        raise ValueError("Output directory cannot be a symlink")
    output.mkdir(parents=True, exist_ok=True)
    text = render(result)
    write_report(output / "summary.json", json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    write_report(output / "summary.md", text)
    step_summary = args.step_summary or os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        web_path = Path(step_summary)
        if web_path.resolve().name in RECEIPTS and web_path.resolve().is_relative_to(args.evidence_root.resolve()):
            raise ValueError("Step summary must not append to an original test receipt")
        with web_path.open("a", encoding="utf-8") as stream:
            stream.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
