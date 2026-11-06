"""Offline release tests: never invoke GitHub, SOLIDWORKS or a publication command."""
import copy
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tag_release", ROOT / "scripts/ci/tag-release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def native_fixture(root, version="1.2.0rc1"):
    import sys
    with patch.object(sys, "path", [str(ROOT / "scripts/ci")] + sys.path):
        from gate_support.runtime_plan import runtime_plan
    plan = runtime_plan("full")
    host = {"process_id": 12, "owned_by_daemon": True, "shared_interactive": False, "visible": False}
    rows = []
    for item in plan:
        steps = []
        for index, step in enumerate(item.steps):
            path = "hidden/runtime-sets/" + item.name + "/" + str(index) + ".json"
            data = {"state": "completed", "success": True, "cleanup_errors": [], "host": host, "host_after": host}
            if item.name == "toolbox":
                data = {"completed": True, "outcome": "passed", "native_test": "passed",
                        "cleanup_errors": [], "evidence_errors": [],
                        "sample": {"sha256_before": "same", "sha256_after": "same"}}
            write_json(root / path, data)
            steps.append({"script": step.script, "success": True, "record": "C:\\smoke\\" + path.replace("/", "\\")})
        rows.append({"name": item.name, "success": True, "cleanup_errors": [], "server_exit_code": 0,
                     "before_start": {"verified": True, "native_process_ids": []},
                     "after_stop": {"verified": True, "native_process_ids": []}, "host": host, "steps": steps})
    write_json(root / "hidden/runtime-sets/runtime-sets.json", {
        "completed": True, "success": True, "suite": "full", "mode": "hidden", "coverage_scope": "full-plan",
        "session_policy": "fresh-per-test-set", "cleanup_errors": [], "diagnostic_set": None, "active_set": None,
        "expected_sets": [s.name for s in plan], "sets": rows})
    write_json(root / "hidden/capabilities.json", {"server_version": version, "worker_alive": True,
                                                 "host_connected": True, "recovery_required": False})
    for name, visible in (("visible/visible.json", True), ("hidden/properties/properties.json", False)):
        selected = dict(host, visible=visible)
        write_json(root / name, {"state": "completed", "success": True, "cleanup_errors": [],
                                "host": selected, "host_after": selected})
    write_json(root / "visible/visible-exit.json", {"wait_completed": True, "has_exited": True, "exit_code": 0})


class TagPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Offline release test")
        self.git("config", "user.email", "test@example.invalid")
        (self.root / "src/swcli").mkdir(parents=True)
        (self.root / "src/swcli/__init__.py").write_text('__version__ = "1.2.0rc1"\n')
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.sha = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.sha)
        self.git("tag", "v1.2.0rc1")
        self.env = {"GITHUB_REPOSITORY": release.REPOSITORY, "GITHUB_EVENT_NAME": "push",
                    "GITHUB_REF": "refs/tags/v1.2.0rc1", "GITHUB_SHA": self.sha}

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

    def test_trusted_main_tag_marks_release_candidates_prerelease(self):
        result = release.validate_tag(self.root, self.env)
        self.assertTrue(result["prerelease"])
        self.assertEqual(result["commit"], self.sha)

    def test_untrusted_source_manual_event_and_changed_sha_are_rejected(self):
        for key, value in (("GITHUB_REPOSITORY", "fork/SWCLI"), ("GITHUB_EVENT_NAME", "workflow_dispatch"),
                           ("GITHUB_SHA", "0" * 40), ("GITHUB_REF", "refs/heads/main")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                release.validate_tag(self.root, dict(self.env, **{key: value}))

    def test_tag_not_reachable_from_main_is_rejected(self):
        (self.root / "other").write_text("unmerged")
        self.git("add", ".")
        self.git("commit", "-qm", "unmerged")
        self.git("tag", "-f", "v1.2.0rc1")
        with self.assertRaises(subprocess.CalledProcessError):
            release.validate_tag(self.root, dict(self.env, GITHUB_SHA=self.git("rev-parse", "HEAD")))

    def test_tag_source_version_mismatch_is_rejected(self):
        self.git("tag", "v1.2.0")
        with self.assertRaisesRegex(ValueError, "source version"):
            release.validate_tag(self.root, dict(self.env, GITHUB_REF="refs/tags/v1.2.0"))

    def test_alpha_beta_dev_and_stable_versions(self):
        for version, expected in (("1.0a1", True), ("1.0b2", True), ("1.0rc1", True),
                                  ("1.0.dev1", True), ("1.0", False), ("1.0.post1", False), ("1.0+a1", False)):
            (self.root / "src/swcli/__init__.py").write_text('__version__ = "' + version + '"\n')
            self.git("add", ".")
            self.git("commit", "-qm", version)
            sha = self.git("rev-parse", "HEAD")
            self.git("update-ref", "refs/remotes/origin/main", sha)
            self.git("tag", "v" + version)
            result = release.validate_tag(self.root, dict(self.env, GITHUB_REF="refs/tags/v" + version, GITHUB_SHA=sha))
            self.assertEqual(result["prerelease"], expected)


class NativeProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        native_fixture(self.root)

    def test_full_public_receipts_have_all_twenty_steps(self):
        proofs = release.verify_native(self.root, "1.2.0rc1")
        self.assertEqual(len(proofs), 25)

    def test_first_incomplete_native_proof_blocks_release(self):
        path = self.root / "hidden/runtime-sets/runtime-sets.json"
        original = release.read_json(path)
        variants = []
        for key, value in (("coverage_scope", "diagnostic"), ("diagnostic_set", "exports"),
                           ("completed", False), ("cleanup_errors", ["leftover"])):
            variants.append(dict(original, **{key: value}))
        data = copy.deepcopy(original)
        data["sets"].pop()
        variants.append(data)
        data = copy.deepcopy(original)
        data["sets"][0]["after_stop"]["native_process_ids"] = [99]
        variants.append(data)
        data = copy.deepcopy(original)
        data["sets"][0]["steps"][0]["record"] = "C:\\runtime-sets\\..\\outside.json"
        variants.append(data)
        for item in variants:
            write_json(path, item)
            with self.subTest(item=str(item)[:70]), self.assertRaises(ValueError):
                release.verify_native(self.root, "1.2.0rc1")

    def test_actual_server_version_and_visible_exit_are_required(self):
        with self.assertRaisesRegex(ValueError, "version/state"):
            release.verify_native(self.root, "1.2.0")
        write_json(self.root / "visible/visible-exit.json", {"wait_completed": True, "has_exited": False, "exit_code": 0})
        with self.assertRaisesRegex(ValueError, "exit cleanly"):
            release.verify_native(self.root, "1.2.0rc1")

    def test_failed_step_or_public_properties_cannot_hide_behind_green_summary(self):
        for path in (self.root / "hidden/runtime-sets/native-model/0.json", self.root / "hidden/properties/properties.json"):
            data = release.read_json(path)
            data["success"] = False
            write_json(path, data)
            with self.assertRaises(ValueError):
                release.verify_native(self.root, "1.2.0rc1")
            data["success"] = True
            write_json(path, data)


class PackageTests(unittest.TestCase):
    def test_original_package_version_and_source_bytes_must_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src/swcli").mkdir(parents=True)
            (root / "src/swcli/__init__.py").write_bytes(b'__version__ = "1.0"\n')
            dist = root / "dist"
            dist.mkdir()
            wheel_files = {"swcli/__init__.py": (root / "src/swcli/__init__.py").read_bytes(),
                           "swcli-1.0.dist-info/METADATA": b"Name: swcli\nVersion: 1.0\n"}
            record = "".join(name + ",sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode() + "," + str(len(data)) + "\n" for name, data in wheel_files.items())
            wheel_files["swcli-1.0.dist-info/RECORD"] = (record + "swcli-1.0.dist-info/RECORD,,\n").encode()
            with zipfile.ZipFile(dist / "swcli-1.0-py3-none-any.whl", "w") as archive:
                for name, data in wheel_files.items():
                    archive.writestr(name, data)
            with tarfile.open(dist / "swcli-1.0.tar.gz", "w:gz") as archive:
                for name, data in (("swcli-1.0/PKG-INFO", b"Name: swcli\nVersion: 1.0\n"),
                                   ("swcli-1.0/src/swcli/__init__.py", (root / "src/swcli/__init__.py").read_bytes()),
                                   ("swcli-1.0/src/swcli.egg-info/PKG-INFO", b"generated metadata")):
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
            self.assertEqual(len(release.verify_packages(dist, root, "1.0")), 2)
            with self.assertRaisesRegex(ValueError, "version mismatch"):
                release.verify_packages(dist, root, "2.0")
            original_wheel = (dist / "swcli-1.0-py3-none-any.whl").read_bytes()
            wheel_files["swcli-1.0.dist-info/RECORD"] = b"swcli/__init__.py,sha256=wrong,1\n"
            with zipfile.ZipFile(dist / "swcli-1.0-py3-none-any.whl", "w") as archive:
                for name, data in wheel_files.items():
                    archive.writestr(name, data)
            with self.assertRaisesRegex(ValueError, "RECORD"):
                release.verify_packages(dist, root, "1.0")
            (dist / "swcli-1.0-py3-none-any.whl").write_bytes(original_wheel)
            with tarfile.open(dist / "swcli-1.0.tar.gz", "w:gz") as archive:
                data = b"Name: swcli\nVersion: 1.0\n"
                info = tarfile.TarInfo("swcli-1.0/PKG-INFO"); info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            with self.assertRaisesRegex(ValueError, "missing packaged source"):
                release.verify_packages(dist, root, "1.0")
            (root / "src/swcli/__init__.py").write_text("changed")
            with self.assertRaisesRegex(ValueError, "source bytes"):
                release.verify_packages(dist, root, "1.0")


class FakeGitHub:
    def __init__(self, assets=None, draft=True):
        self.assets = assets or {}
        self.current = {"id": 1, "tag_name": "v1.0", "prerelease": False, "draft": draft,
                        "assets": [{"name": name, "id": name} for name in self.assets]}
        self.uploads, self.published = [], False

    def release(self, tag):
        return self.current

    def api(self, path, payload=None, binary=False):
        if path.startswith("git/ref/"):
            return {"object": {"type": "commit", "sha": "1" * 40}}
        return self.assets[path.split("/")[-1]]

    def upload(self, tag, path):
        self.uploads.append(path.name)
        self.assets[path.name] = path.read_bytes()

    def publish(self, release_id):
        self.published = True

    def public_bytes(self, tag, name):
        return self.assets[name]


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        write_json(self.root / "provenance.json", {"tag": "v1.0", "prerelease": False, "commit": "1" * 40})
        (self.root / "swcli-1.0.whl").write_bytes(b"original wheel")

    def test_new_release_is_created_draft_then_uploaded_and_published(self):
        api = FakeGitHub()
        api.release = lambda tag: None
        original_api = api.api
        created = []
        def create_or_read(path, payload=None, binary=False):
            if path == "releases":
                created.append(payload)
                return api.current
            return original_api(path, payload, binary)
        api.api = create_or_read
        (self.root / "RELEASE_NOTES.md").write_text("Verified original release")
        result = release.publish(self.root, api)
        self.assertTrue(created[0]["draft"])
        self.assertEqual(created[0]["target_commitish"], "1" * 40)
        self.assertFalse(created[0]["prerelease"])
        self.assertEqual(set(api.uploads), {p.name for p in self.root.iterdir()})
        self.assertTrue(api.published)
        self.assertTrue(result["public_download_verified"])

    def test_draft_resume_only_uploads_missing_assets_and_publicly_verifies(self):
        api = FakeGitHub({"swcli-1.0.whl": b"original wheel"})
        result = release.publish(self.root, api)
        self.assertEqual(api.uploads, ["provenance.json"])
        self.assertTrue(api.published)
        self.assertTrue(result["public_download_verified"])

    def test_conflicting_original_asset_fails_before_any_mutation(self):
        api = FakeGitHub({"swcli-1.0.whl": b"replaced wheel"})
        with self.assertRaisesRegex(ValueError, "asset differs"):
            release.publish(self.root, api)
        self.assertEqual(api.uploads, [])
        self.assertFalse(api.published)

    def test_published_release_identical_bytes_are_reused_without_changes(self):
        api = FakeGitHub({p.name: p.read_bytes() for p in self.root.iterdir()}, draft=False)
        release.publish(self.root, api)
        self.assertEqual(api.uploads, [])
        self.assertFalse(api.published)

    def test_anonymous_download_mismatch_is_not_a_verified_publication(self):
        api = FakeGitHub()
        api.public_bytes = lambda *args: b"wrong download"
        with self.assertRaisesRegex(ValueError, "public download differs"):
            release.publish(self.root, api)

    def test_moved_live_tag_prevents_even_a_draft_mutation(self):
        api = FakeGitHub()
        api.api = lambda *args, **kwargs: {"object": {"type": "commit", "sha": "2" * 40}}
        with self.assertRaisesRegex(ValueError, "tag moved"):
            release.publish(self.root, api)
        self.assertEqual(api.uploads, [])
        self.assertFalse(api.published)

    def test_published_incomplete_release_is_not_silently_modified(self):
        api = FakeGitHub(draft=False)
        with self.assertRaisesRegex(ValueError, "manual review"):
            release.publish(self.root, api)
        self.assertEqual(api.uploads, [])


class ArtifactSourceTests(unittest.TestCase):
    def test_artifacts_are_same_sha_run_attempt_and_have_digest(self):
        env = {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_SHA": "1" * 40}
        run = {"head_sha": env["GITHUB_SHA"], "event": "push", "run_attempt": 2,
               "repository": {"full_name": release.REPOSITORY}}
        artifacts = [{"id": index, "name": name, "expired": False, "size_in_bytes": 100,
                      "digest": "sha256:" + "a" * 64, "workflow_run": {"head_sha": env["GITHUB_SHA"]}}
                     for index, name in enumerate(("swcli-dist", "swcli-windows-hosted-123-2"))]
        class API:
            def api(self, path):
                return {"artifacts": artifacts} if "/artifacts?" in path else run
        self.assertEqual(len(release.verify_run_artifacts(API(), env)), 2)
        for key, value in (("expired", True), ("digest", ""), ("workflow_run", {"head_sha": "2" * 40})):
            original = copy.deepcopy(artifacts[0])
            artifacts[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                release.verify_run_artifacts(API(), env)
            artifacts[0] = original
        run["run_attempt"] = 1
        with self.assertRaisesRegex(ValueError, "run attempt"):
            release.verify_run_artifacts(API(), env)


if __name__ == "__main__":
    unittest.main()


class GitHubFailureTests(unittest.TestCase):
    def test_structured_api_error_is_visible_without_request_secrets(self):
        result = subprocess.CompletedProcess([], 1, b'{"message":"Resource not accessible by integration","status":"403"}', b'private stderr')
        with patch.object(release.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "Resource not accessible by integration") as caught:
                release.GitHub().api("releases", {"private": "secret"})
        self.assertNotIn("private", str(caught.exception))
        self.assertIn("403", str(caught.exception))
