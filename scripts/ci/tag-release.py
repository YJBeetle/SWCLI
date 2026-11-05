#!/usr/bin/env python3
"""Publish original same-run packages only after trusted-tag and native evidence checks."""
import argparse
import ast
import base64
import csv
import email.parser
import hashlib
import io
import json
import os
from pathlib import Path, PureWindowsPath
import re
import subprocess
import tarfile
import urllib.parse
import urllib.request
import zipfile

REPOSITORY = "YJBeetle/SWCLI"
VERSION = re.compile(r"(?:[0-9]+!)?[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?(?:\.post[0-9]+)?(?:\.dev[0-9]+)?(?:\+[a-z0-9]+(?:[.-][a-z0-9]+)*)?\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def source_version(source):
    tree = ast.parse(source)
    values = [ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)]
    require(len(values) == 1 and isinstance(values[0], str), "Source version is ambiguous")
    return values[0]


def validate_tag(root, env):
    require(env.get("GITHUB_REPOSITORY") == REPOSITORY, "Only the upstream repository can publish")
    require(env.get("GITHUB_EVENT_NAME") == "push", "Publication requires a tag push")
    ref = env.get("GITHUB_REF", "")
    require(ref.startswith("refs/tags/v"), "Publication requires a version tag")
    version = ref[len("refs/tags/v"):]
    require(VERSION.fullmatch(version), "Tag must contain a canonical PEP 440 version")
    commit = git(root, "rev-parse", "--verify", ref + "^{commit}")
    require(commit == env.get("GITHUB_SHA"), "Tag target differs from workflow SHA")
    subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", commit,
                    "refs/remotes/origin/main"], check=True, capture_output=True)
    require(source_version(git(root, "show", commit + ":src/swcli/__init__.py")) == version,
            "Tag version differs from source version")
    return {"tag": "v" + version, "version": version, "commit": commit,
            "prerelease": bool(re.search(r"(?:a|b|rc)[0-9]+|\.dev[0-9]+", version.split("+", 1)[0]))}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def clean_success(data, label):
    require(data.get("success") is True and data.get("state") == "completed",
            label + " is not completed successfully")
    require(data.get("cleanup_errors") == [], label + " did not clean up")


def verify_host(data, visible, label):
    host = data.get("host", {})
    require(host.get("owned_by_daemon") is True and host.get("shared_interactive") is False
            and host.get("visible") is visible and isinstance(host.get("process_id"), int),
            label + " has an unexpected host")
    after = data.get("host_after", {})
    require(after.get("process_id") == host["process_id"]
            and after.get("owned_by_daemon") is True and after.get("visible") is visible,
            label + " changed host")


def verify_native(root, version):
    """Audit public full-plan receipts, never a calibration/selected-set receipt."""
    import sys
    ci_dir = str(Path(__file__).resolve().parent)
    if ci_dir not in sys.path:
        sys.path.insert(0, ci_dir)
    from gate_support.runtime_plan import runtime_plan
    root = Path(root)
    require(not root.is_symlink(), "Evidence root cannot be a symlink")
    full_path = root / "hidden/runtime-sets/runtime-sets.json"
    full = read_json(full_path)
    require(full.get("completed") is True and full.get("success") is True
            and full.get("suite") == "full" and full.get("mode") == "hidden"
            and full.get("coverage_scope") == "full-plan"
            and full.get("session_policy") == "fresh-per-test-set"
            and full.get("diagnostic_set") is None and full.get("active_set") is None
            and full.get("cleanup_errors") == [], "Not a clean complete public full-plan receipt")
    plan = runtime_plan("full")
    names = [s.name for s in plan]
    rows = full.get("sets", [])
    require(full.get("expected_sets") == names and [r.get("name") for r in rows] == names,
            "Native full-plan sets are missing, repeated or reordered")
    proofs = [full_path]
    for expected, row in zip(plan, rows):
        require(row.get("success") is True and row.get("cleanup_errors") == []
                and row.get("server_exit_code") == 0, "Set failed/unclean: " + expected.name)
        for boundary in ("before_start", "after_stop"):
            require(row.get(boundary, {}).get("verified") is True
                    and row[boundary].get("native_process_ids") == [],
                    "Native process boundary is not empty: " + expected.name)
        steps = row.get("steps", [])
        require([s.get("script") for s in steps] == [s.script for s in expected.steps]
                and all(s.get("success") is True for s in steps), "Set steps are incomplete")
        for step in steps:
            parts = PureWindowsPath(step["record"]).parts
            require(parts.count("runtime-sets") == 1 and ".." not in parts, "Invalid record path")
            suffix = parts[parts.index("runtime-sets") + 1:]
            require(suffix and suffix[0] == expected.name, "Record belongs to another set")
            path = root / "hidden/runtime-sets" / Path(*suffix)
            require(path.resolve().is_relative_to(root.resolve()) and not path.is_symlink(),
                    "Record escapes evidence root")
            record = read_json(path)
            if expected.name == "toolbox":
                require(record.get("completed") is True and record.get("outcome") == "passed"
                        and record.get("native_test") == "passed" and record.get("cleanup_errors") == []
                        and record.get("evidence_errors") == [], "Toolbox native proof failed")
                sample = record.get("sample", {})
                require(sample.get("sha256_before") and sample.get("sha256_before") == sample.get("sha256_after"),
                        "Toolbox input changed")
            else:
                clean_success(record, expected.name)
                verify_host(record, False, expected.name)
                require(record["host"]["process_id"] == row.get("host", {}).get("process_id"),
                        "Step ran in another host")
            proofs.append(path)
    capabilities = root / "hidden/capabilities.json"
    caps = read_json(capabilities)
    require(caps.get("server_version") == version and caps.get("worker_alive") is True
            and caps.get("host_connected") is True and caps.get("recovery_required") is False,
            "Actual native daemon version/state differs from release")
    visible = root / "visible/visible.json"
    public_properties = root / "hidden/properties/properties.json"
    for path, visibility in ((visible, True), (public_properties, False)):
        data = read_json(path)
        clean_success(data, path.name)
        verify_host(data, visibility, path.name)
    exit_path = root / "visible/visible-exit.json"
    exit_data = read_json(exit_path)
    require(exit_data.get("wait_completed") is True and exit_data.get("has_exited") is True
            and exit_data.get("exit_code") == 0, "Visible server did not exit cleanly")
    proofs += [capabilities, visible, public_properties, exit_path]
    return {str(p.relative_to(root)): sha256(p) for p in proofs}


def metadata_version(raw):
    metadata = email.parser.BytesParser().parsebytes(raw)
    require(metadata.get("Name", "").lower() == "swcli", "Unexpected distribution name")
    return metadata.get("Version")


def verify_packages(dist, root, version):
    dist = Path(dist)
    wheels, sdists = list(dist.glob("*.whl")), list(dist.glob("*.tar.gz"))
    require(len(wheels) == len(sdists) == 1, "Expected exactly one original wheel and sdist")
    wheel, sdist = wheels[0], sdists[0]
    require(not wheel.is_symlink() and not sdist.is_symlink(), "Packages cannot be symlinks")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "Duplicate wheel entries")
        metadata = [n for n in names if n.endswith(".dist-info/METADATA")]
        require(len(metadata) == 1 and metadata_version(archive.read(metadata[0])) == version,
                "Original wheel version mismatch")
        sources = {str(p.relative_to(Path(root) / "src")).replace(os.sep, "/"): p
                   for p in (Path(root) / "src/swcli").rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
        packaged = {n for n in names if n.startswith("swcli/") and not n.endswith("/")}
        require(packaged == set(sources), "Wheel source/resources differ from tag")
        require(all(archive.read(n) == p.read_bytes() for n, p in sources.items()),
                "Wheel source bytes differ from tag")
        records = [n for n in names if n.endswith(".dist-info/RECORD")]
        require(len(records) == 1, "Original wheel RECORD is missing or ambiguous")
        rows = list(csv.reader(io.StringIO(archive.read(records[0]).decode("utf-8"))))
        files = {n for n in names if not n.endswith("/")}
        require(all(len(row) == 3 for row in rows) and len(rows) == len(files)
                and {row[0] for row in rows} == files, "Wheel RECORD file list differs")
        for name, digest, size in rows:
            if name == records[0]:
                require(digest == size == "", "Wheel RECORD cannot hash itself")
            else:
                data = archive.read(name)
                expected = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
                require(digest == expected and size == str(len(data)), "Wheel RECORD hash/size differs: " + name)
    with tarfile.open(sdist, "r:gz") as archive:
        entries = archive.getmembers()
        require(len({m.name for m in entries}) == len(entries), "Duplicate sdist entries")
        metadata = [m for m in entries if len(Path(m.name).parts) == 2 and m.name.endswith("/PKG-INFO")]
        require(len(metadata) == 1 and metadata_version(archive.extractfile(metadata[0]).read()) == version,
                "Original sdist version mismatch")
        source_files = set()
        for member in entries:
            require(not member.issym() and not member.islnk() and ".." not in Path(member.name).parts,
                    "Unsafe sdist member")
            if member.isfile():
                relative = Path(*Path(member.name).parts[1:])
                source_files.add(relative.as_posix())
                # setuptools adds generated src/swcli.egg-info; it is not a
                # checked-in source file and is not a package input to compare.
                source_member = (relative.parts[:2] == ("src", "swcli")
                                 or relative.parts[:1] in (("scripts",), ("tests",), ("docs",)))
                if source_member:
                    target = Path(root) / relative
                    require(target.is_file() and archive.extractfile(member).read() == target.read_bytes(),
                            "Sdist source bytes differ from tag: " + str(relative))
        require({"src/" + name for name in sources}.issubset(source_files),
                "Sdist is missing packaged source/resources")
    return [wheel, sdist]


def prepare(root, dist, evidence, output, env, artifacts=None):
    tag = validate_tag(root, env)
    require(git(root, "rev-parse", "HEAD") == tag["commit"], "Release checkout is not the tag commit")
    packages = verify_packages(dist, root, tag["version"])
    native = verify_native(evidence, tag["version"])
    note = Path(root) / "docs/releases" / (tag["tag"] + ".md")
    require(note.is_file() and note.stat().st_size > 0, "Tag-specific release notes are required")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for path in packages:
        (output / path.name).write_bytes(path.read_bytes())
    (output / "RELEASE_NOTES.md").write_bytes(note.read_bytes())
    provenance = {"schema_version": 1, "repository": REPOSITORY, **tag,
                  "run_id": env["GITHUB_RUN_ID"], "run_attempt": env["GITHUB_RUN_ATTEMPT"],
                  "run_url": "https://github.com/" + REPOSITORY + "/actions/runs/" + env["GITHUB_RUN_ID"],
                  "artifacts": ["swcli-dist", "swcli-windows-hosted-" + env["GITHUB_RUN_ID"] + "-" + env["GITHUB_RUN_ATTEMPT"]],
                  "artifact_metadata": artifacts or {},
                  "packages": {p.name: sha256(p) for p in packages}, "native_receipts": native,
                  "native_verified": True, "public_download_verified": False,
                  "public_download_note": "The release job separately verifies anonymous downloads after publication."}
    (output / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assets = sorted(output.iterdir())
    (output / "SHA256SUMS").write_text("".join(sha256(p) + "  " + p.name + "\n" for p in assets), encoding="utf-8")
    return tag


class GitHub:
    def api(self, path, payload=None, binary=False):
        args = ["gh", "api", "repos/" + REPOSITORY + "/" + path]
        if binary:
            args += ["-H", "Accept: application/octet-stream"]
        if payload is not None:
            args += ["--method", "POST", "--input", "-"]
        result = subprocess.run(args, input=None if payload is None else json.dumps(payload).encode(),
                                capture_output=True, check=True)
        return result.stdout if binary else json.loads(result.stdout)

    def release(self, tag):
        # Listing distinguishes an absent release from an API/auth/network error.
        page = 1
        while True:
            rows = self.api("releases?per_page=100&page=" + str(page))
            found = [r for r in rows if r["tag_name"] == tag]
            if found:
                return self.api("releases/" + str(found[0]["id"]))
            if len(rows) < 100:
                return None
            page += 1

    def upload(self, tag, path):
        subprocess.run(["gh", "release", "upload", tag, str(path), "--repo", REPOSITORY], check=True)

    def publish(self, release_id):
        subprocess.run(["gh", "api", "repos/" + REPOSITORY + "/releases/" + str(release_id),
                        "--method", "PATCH", "-F", "draft=false"], check=True, stdout=subprocess.DEVNULL)

    def public_bytes(self, tag, name):
        url = "https://github.com/" + REPOSITORY + "/releases/download/" + urllib.parse.quote(tag, safe="") + "/" + urllib.parse.quote(name, safe="")
        with urllib.request.urlopen(url, timeout=60) as response:
            return response.read()


def verify_run_artifacts(api, env):
    run_id = env["GITHUB_RUN_ID"]
    run = api.api("actions/runs/" + run_id)
    require(run.get("head_sha") == env["GITHUB_SHA"] and run.get("event") == "push"
            and run.get("repository", {}).get("full_name") == REPOSITORY
            and str(run.get("run_attempt")) == env["GITHUB_RUN_ATTEMPT"],
            "Workflow source/run attempt differs from release")
    rows = api.api("actions/runs/" + run_id + "/artifacts?per_page=100")["artifacts"]
    expected = ("swcli-dist", "swcli-windows-hosted-" + run_id + "-" + env["GITHUB_RUN_ATTEMPT"])
    result = {}
    for name in expected:
        selected = [a for a in rows if a["name"] == name]
        require(len(selected) == 1 and selected[0].get("expired") is False,
                "Missing/ambiguous original artifact: " + name)
        item = selected[0]
        require(item.get("workflow_run", {}).get("head_sha") == env["GITHUB_SHA"]
                and re.fullmatch(r"sha256:[0-9a-f]{64}", item.get("digest", "")),
                "Artifact has no matching source SHA/digest: " + name)
        result[name] = {key: item[key] for key in ("id", "name", "digest", "size_in_bytes")}
    return result


def publish(output, api):
    output = Path(output)
    proof = read_json(output / "provenance.json")
    tag = proof["tag"]
    assets = sorted(p for p in output.iterdir() if p.is_file())
    # Tags may be moved after the initial checkout; revalidate the live target.
    target = api.api("git/ref/tags/" + urllib.parse.quote(tag, safe=""))["object"]
    for _ in range(8):
        if target["type"] == "commit":
            break
        require(target["type"] == "tag", "Release tag does not resolve to a commit")
        target = api.api("git/tags/" + target["sha"])["object"]
    require(target["type"] == "commit" and target["sha"] == proof["commit"],
            "Live release tag moved from the verified commit")
    release = api.release(tag)
    if release is None:
        release = api.api("releases", {"tag_name": tag, "target_commitish": proof["commit"],
                         "name": tag, "body": (output / "RELEASE_NOTES.md").read_text(encoding="utf-8"),
                         "draft": True, "prerelease": proof["prerelease"]})
    require(release["tag_name"] == tag and release["prerelease"] == proof["prerelease"],
            "Existing release metadata conflicts")
    existing = release.get("assets", [])
    require(len({a["name"] for a in existing}) == len(existing), "Duplicate release assets")
    by_name = {a["name"]: a for a in existing}
    require(set(by_name).issubset({p.name for p in assets}), "Unexpected existing release assets")
    # Check every existing asset BEFORE uploading anything. Never overwrite.
    for path in assets:
        if path.name in by_name:
            require(api.api("releases/assets/" + str(by_name[path.name]["id"]), binary=True) == path.read_bytes(),
                    "Existing release asset differs: " + path.name)
    require(release.get("draft") or set(by_name) == {p.name for p in assets},
            "Published release is incomplete; manual review required")
    for path in assets:
        if path.name not in by_name:
            api.upload(tag, path)
    if release.get("draft"):
        api.publish(release["id"])
    for path in assets:
        require(api.public_bytes(tag, path.name) == path.read_bytes(),
                "Anonymous public download differs: " + path.name)
    return {"tag": tag, "public_download_verified": True,
            "assets": {p.name: sha256(p) for p in assets}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check-tag", "release"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--dist", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "check-tag":
        print(json.dumps(validate_tag(args.root, os.environ)))
    else:
        require(args.dist and args.evidence and args.output, "Release paths are required")
        api = GitHub()
        artifacts = verify_run_artifacts(api, os.environ)
        prepare(args.root, args.dist, args.evidence, args.output, os.environ, artifacts)
        print(json.dumps(publish(args.output, api), indent=2))


if __name__ == "__main__":
    main()
