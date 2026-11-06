"""Publish verified original tag-run assets after its publication job was cancelled.

This runs in a separate manual workflow. Source run identity and publication run
identity stay separate; no tag moves, CAD reruns or synthetic CI environments.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

REPOSITORY = "YJBeetle/SWCLI"
JOBS = ("Validate release tag before private native runtime", "Windows / Python 3.9",
        "Windows / Python 3.14", "Build wheel", "Complete SOLIDWORKS functional verification")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def load_publisher(path):
    spec = importlib.util.spec_from_file_location("original_tag_publisher", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_context(api, run_id):
    require(re.fullmatch(r"[1-9][0-9]*", str(run_id)), "Invalid original run ID")
    run_id = str(run_id)
    run = api.api("actions/runs/" + run_id)
    require(str(run.get("id")) == run_id and run.get("repository", {}).get("full_name") == REPOSITORY
            and run.get("event") == "push" and run.get("path") == ".github/workflows/ci.yml"
            and run.get("status") == "completed", "Original tag workflow is not complete/trusted")
    tag = run.get("head_branch", "")
    require(re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+)?", tag), "Original run is not a version tag")
    commit = run.get("head_sha", "")
    require(re.fullmatch(r"[0-9a-f]{40}", commit), "Invalid original source SHA")
    jobs = api.api("actions/runs/" + run_id + "/jobs?filter=latest&per_page=100")["jobs"]
    for name in JOBS:
        selected = [job for job in jobs if job["name"] == name]
        require(len(selected) == 1 and selected[0].get("conclusion") == "success",
                "Original required job did not pass: " + name)
    attempt = int(run["run_attempt"])
    rows = api.api("actions/runs/" + run_id + "/artifacts?per_page=100")["artifacts"]
    artifacts = {}
    for key, name in (("dist", "swcli-dist"), ("native", "swcli-windows-hosted-" + run_id + "-" + str(attempt))):
        selected = [row for row in rows if row["name"] == name]
        require(len(selected) == 1, "Missing/ambiguous original artifact: " + name)
        row = selected[0]
        require(row.get("expired") is False and row.get("workflow_run", {}).get("head_sha") == commit
                and isinstance(row.get("id"), int) and row["id"] > 0
                and re.fullmatch(r"sha256:[0-9a-f]{64}", row.get("digest", "")),
                "Original artifact source/digest is invalid: " + name)
        artifacts[key] = {field: row[field] for field in ("id", "name", "digest", "size_in_bytes")}
    return {"repository": REPOSITORY, "run_id": run_id, "run_attempt": attempt,
            "tag": tag, "version": tag[1:], "commit": commit, "artifacts": artifacts}


def publish_original(context, root, dist, evidence, output, api, env):
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == REPOSITORY
            and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
            and env.get("GITHUB_REF") == "refs/heads/main", "Recovery must run from the trusted main workflow")
    require(source_context(api, context["run_id"]) == context, "Original run/artifacts changed during recovery")
    root = Path(root)
    git = lambda *args: subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
    require(git("rev-parse", "HEAD") == context["commit"], "Recovery checkout is not original source")
    subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", context["commit"], "origin/main"], check=True)
    publisher = load_publisher(root / "scripts/ci/tag-release.py")
    require(publisher.source_version((root / "src/swcli/__init__.py").read_text()) == context["version"],
            "Original tag/source version mismatch")
    packages = publisher.verify_packages(Path(dist), root, context["version"])
    native = publisher.verify_native(Path(evidence), context["version"])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for path in packages:
        (output / path.name).write_bytes(path.read_bytes())
    note = root / "docs/releases" / (context["tag"] + ".md")
    require(note.is_file() and note.stat().st_size > 0, "Original release notes missing")
    (output / "RELEASE_NOTES.md").write_bytes(note.read_bytes())
    run_url = "https://github.com/" + REPOSITORY + "/actions/runs/"
    proof = {"schema_version": 1, "repository": REPOSITORY, "tag": context["tag"],
        "version": context["version"], "commit": context["commit"],
        "prerelease": bool(re.search(r"(?:a|b|rc)[0-9]+", context["version"])),
        "run_id": context["run_id"], "run_attempt": context["run_attempt"],
        "run_url": run_url + context["run_id"],
        "artifacts": [a["name"] for a in context["artifacts"].values()],
        "artifact_metadata": {a["name"]: a for a in context["artifacts"].values()},
        "packages": {p.name: publisher.sha256(p) for p in packages}, "native_receipts": native,
        "native_verified": True, "public_download_verified": False,
        "public_download_note": "The publication workflow verifies anonymous downloads after publication.",
        "publication": {"recovery": True, "run_id": env["GITHUB_RUN_ID"],
                        "run_url": run_url + env["GITHUB_RUN_ID"], "publisher_commit": env["GITHUB_SHA"]}}
    (output / "provenance.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    (output / "SHA256SUMS").write_text("".join(publisher.sha256(p) + "  " + p.name + "\n"
        for p in sorted(output.iterdir())), encoding="utf-8")
    # The frozen publisher rechecks the live tag and refuses replacing assets.
    return publisher.publish(output, api)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "publish"))
    parser.add_argument("--source-run")
    parser.add_argument("--context", type=Path, required=True)
    for name in ("root", "dist", "evidence", "output"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    current = load_publisher(Path(__file__).with_name("tag-release.py"))
    api = current.GitHub()
    if args.mode == "inspect":
        context = source_context(api, args.source_run)
        args.context.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            for key, value in (("commit", context["commit"]), ("dist_id", context["artifacts"]["dist"]["id"]),
                               ("native_id", context["artifacts"]["native"]["id"])):
                out.write(key + "=" + str(value) + "\n")
    else:
        require(all((args.root, args.dist, args.evidence, args.output)), "Recovery paths required")
        context = json.loads(args.context.read_text())
        print(json.dumps(publish_original(context, args.root, args.dist, args.evidence, args.output, api, os.environ), indent=2))


if __name__ == "__main__":
    main()
