"""Record and reuse completed Windows native evidence for the exact commit."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
from zipfile import BadZipFile, ZipFile

WORKFLOW = ".github/workflows/ci.yml"
ROOT = "swcli-native-smoke/"
REPORTS = ("hidden/runtime-sets/runtime-sets.json", "visible/visible.json")
STAMP = "native-acceptance.json"
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def validate_reports(read):
    full_bytes, visible_bytes = [read(path) for path in REPORTS]
    full = json.loads(full_bytes)
    visible = json.loads(visible_bytes)
    sets = full["sets"]
    if not (full["completed"] is True and full["success"] is True
            and full["suite"] == "full" and full["coverage_scope"] == "full-plan"
            and full["diagnostic_set"] is None and full["cleanup_errors"] == []
            and sets and [entry["name"] for entry in sets] == full["expected_sets"]):
        raise ValueError("native suite is not complete full acceptance")
    for entry in sets:
        if not (entry["success"] is True and entry["cleanup_errors"] == []
                and entry["server_exit_code"] == 0 and entry["host"]["platform"] == "windows"
                and entry["steps"] and all(step["success"] is True for step in entry["steps"])
                and all(entry[key]["verified"] is True and entry[key]["native_process_ids"] == []
                        for key in ("before_start", "after_stop"))):
            raise ValueError("native suite has a failed or incomplete set")
    if not (visible["state"] == "completed" and visible["success"] is True
            and visible["cleanup_errors"] == [] and visible["host"]["platform"] == "windows"
            and visible["host"]["owned_by_daemon"] is True and visible["host"]["visible"] is True
            and visible["host"] == visible["host_after"]):
        raise ValueError("visible Windows acceptance is incomplete")
    return {REPORTS[0]: sha(full_bytes), REPORTS[1]: sha(visible_bytes)}


def identity(repo, commit, run_id, attempt):
    return {"format": 1, "repository": repo, "commit": commit, "run_id": run_id,
            "attempt": attempt, "coverage": "windows-visible-and-full-default-media"}


def stamp(root, repo, commit):
    stamp_data = identity(repo, commit, int(os.environ["GITHUB_RUN_ID"]), int(os.environ["GITHUB_RUN_ATTEMPT"]))
    stamp_data["report_digests"] = validate_reports(lambda name: (root / name).read_bytes())
    (root / STAMP).write_text(json.dumps(stamp_data, indent=2) + "\n", encoding="utf-8")


def api(endpoint):
    return subprocess.check_output(["gh", "api", endpoint], stderr=subprocess.PIPE, timeout=30)


def verify_archive(artifact, expected):
    if not 0 < artifact["size_in_bytes"] <= MAX_ARCHIVE_BYTES:
        raise ValueError("invalid native artifact size")
    payload = api(f"repos/{expected['repository']}/actions/artifacts/{artifact['id']}/zip")
    if len(payload) > MAX_ARCHIVE_BYTES or sha(payload) != artifact.get("digest"):
        raise ValueError("native artifact digest differs from GitHub")
    with ZipFile(io.BytesIO(payload)) as archive:
        def read(name):
            path = ROOT + name
            if archive.namelist().count(path) != 1 or archive.getinfo(path).file_size > 1024 * 1024:
                raise ValueError("missing, duplicate or oversized native report")
            return archive.read(path)

        recorded = json.loads(read(STAMP))
        expected = {**expected, "report_digests": validate_reports(read)}
        if recorded != expected:
            raise ValueError("native receipt does not match the run and original reports")


def find(repo, commit):
    endpoint = f"repos/{repo}/actions"
    query = f"event=workflow_dispatch&status=success&head_sha={commit}&per_page=10"
    runs = json.loads(api(f"{endpoint}/workflows/ci.yml/runs?{query}"))["workflow_runs"]
    for run in runs:
        if not (run["head_sha"] == commit and run["event"] == "workflow_dispatch"
                and run["status"] == "completed" and run["conclusion"] == "success"
                and isinstance(run["path"], str) and run["path"].split("@", 1)[0] == WORKFLOW
                and (run.get("head_repository") or {}).get("full_name") == repo
                and type(run["id"]) is int and type(run["run_attempt"]) is int):
            continue
        artifacts = json.loads(api(f"{endpoint}/runs/{run['id']}/artifacts?per_page=100"))["artifacts"]
        name = f"swcli-windows-hosted-{run['id']}-{run['run_attempt']}"
        matching = [a for a in artifacts if a["name"] == name and a["expired"] is False]
        if len(matching) != 1 or not any(a["name"] == "swcli-dist" and a["expired"] is False for a in artifacts):
            continue
        try:
            verify_archive(matching[0], identity(repo, commit, run["id"], run["run_attempt"]))
        except (ValueError, KeyError, TypeError, BadZipFile, OSError, subprocess.SubprocessError):
            continue
        return run["id"], matching[0]["id"]
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stamp", type=Path)
    args = parser.parse_args()
    repo, commit = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_SHA"]
    if args.stamp is not None:
        stamp(args.stamp, repo, commit)
        return
    try:
        result = find(repo, commit)
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as exc:
        print(f"Prior native evidence lookup unavailable ({type(exc).__name__}); run the full gate.")
        result = None
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"reused={'true' if result else 'false'}\n")
    if result:
        run, artifact = result
        message = (f"Reused [Windows full acceptance](https://github.com/{repo}/actions/runs/{run}) "
                   f"for `{commit}` (verified native artifact {artifact}).")
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as summary:
            summary.write(message + "\n")
        print(message)
    else:
        print("No matching complete Windows evidence; run the full gate.")


if __name__ == "__main__":
    main()
