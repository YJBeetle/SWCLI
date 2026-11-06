"""Real rooted files and bounded transfers; no SOLIDWORKS or native worker calls."""

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import uuid

from swcli.daemon.client import call_daemon
from swcli.daemon.server import SwclidServer, validate_request
from swcli.file_transfer import FileTransferClient, TransferError
from swcli.safe_workspace import SafeWorkspace, CHUNK_BYTES, file_hash, relative_parts
from swcli.secure_transport import ServerSecurity
from swcli.workspace import WorkspaceStore
from tests.test_secure_transport import certificate


def request(name, parameters, session="file-tests", request_id=None):
    return validate_request({"api_version": "swcli/v1", "operation": "workspace." + name,
        "parameters": parameters, "session_id": session, "request_id": request_id or str(uuid.uuid4())})


class RootedFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.workspace = SafeWorkspace(self.path); self.addCleanup(self.workspace.close)

    def test_paths_reject_traversal_devices_ads_and_internal_files(self):
        for path in ("../a", "/a", "a//b", "C:\\file", "\\server\\share", "a/./b", "file:stream", "NUL.txt",
                     "a/COM1.log", "lpt²", "a.", "a ", "a/../b", ".swcli-upload-hidden.tmp", "a/\x00b"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                relative_parts(path)
        self.assertEqual(relative_parts("parts\\中文 1.SLDPRT"), ["parts", "中文 1.SLDPRT"])

    def test_atomic_default_conflict_and_explicit_replacement(self):
        target = self.path / "中文 file.bin"
        with self.workspace.stage(target.name) as stage:
            stage.stream.write(b"new")
            self.assertFalse(target.exists())
            stage.publish()
        self.assertEqual(target.read_bytes(), b"new")
        with self.assertRaises(FileExistsError):
            self.workspace.stage(target.name)
        with self.workspace.stage(target.name, overwrite=True) as stage:
            stage.stream.write(b"replacement")
            self.assertEqual(target.read_bytes(), b"new")
            stage.publish()
        self.assertEqual(target.read_bytes(), b"replacement")
        self.assertFalse(list(self.path.glob(".swcli-*")))

    def test_publish_never_overwrites_a_destination_created_mid_transfer(self):
        with self.workspace.stage("race") as stage:
            stage.stream.write(b"uploaded")
            (self.path / "race").write_bytes(b"other writer")
            with self.assertRaises(FileExistsError):
                stage.publish()
        self.assertEqual((self.path / "race").read_bytes(), b"other writer")
        self.assertFalse(list(self.path.glob(".swcli-*")))

    def test_hard_link_is_not_a_readable_workspace_file(self):
        (self.path / "original").write_bytes(b"outside")
        os.link(self.path / "original", self.path / "link")
        with self.assertRaises(ValueError):
            self.workspace.open_read("link")

    @unittest.skipIf(os.name == "nt", "POSIX descriptor traversal; Windows reparse test is separate")
    def test_symlink_and_moved_parent_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / "secret").write_bytes(b"outside")
            (self.path / "escape").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(OSError):
                self.workspace.open_read("escape/secret")
            with self.assertRaises(OSError):
                self.workspace.stage("escape/write")
            (self.path / "dir").mkdir()
            with self.workspace.stage("dir/file") as stage:
                stage.stream.write(b"data")
                (self.path / "dir").rename(self.path / "old")
                (self.path / "dir").mkdir()
                with self.assertRaisesRegex(ValueError, "parent changed"):
                    stage.publish()
            self.assertFalse((self.path / "old/file").exists())
            self.assertFalse((Path(outside) / "write").exists())

    @unittest.skipUnless(os.name == "nt", "Windows junction boundary")
    def test_windows_junction_is_not_followed(self):
        with tempfile.TemporaryDirectory() as outside:
            junction = self.path / "junction"
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), outside], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.addCleanup(lambda: os.rmdir(junction) if junction.exists() else None)
            with self.assertRaises(ValueError):
                self.workspace.stage("junction/secret")
            self.assertFalse((Path(outside) / "secret").exists())


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.now = 0
        self.store = WorkspaceStore(self.path, max_bytes=16, clock=lambda: self.now)
        self.addCleanup(self.store.close)

    def call(self, name, parameters, **kwargs):
        return self.store.execute(request(name, parameters, **kwargs))

    def begin(self, data=b"abc", path="file", **kwargs):
        return self.call("upload-begin", {"path": path, "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}, **kwargs)

    def put(self, transfer, data=b"abc", offset=0, **kwargs):
        return self.call("upload-chunk", {"transfer_id": transfer["transfer_id"], "offset": offset,
            "data": base64.b64encode(data).decode()}, **kwargs)

    def test_chunk_replay_commit_and_lost_commit_ack_are_idempotent(self):
        handle = self.begin(request_id="once")
        self.assertEqual(self.begin(request_id="once"), handle)
        with self.assertRaises(ValueError):
            self.begin(b"different", request_id="once")
        self.put(handle); self.put(handle)
        with self.assertRaises(ValueError):
            self.put(handle, b"bad")
        committed = self.call("upload-commit", {"transfer_id": handle["transfer_id"]})
        self.assertEqual(committed["state"], "committed")
        self.assertEqual(self.call("upload-commit", {"transfer_id": handle["transfer_id"]}), committed)
        self.assertEqual(self.begin(request_id="once")["state"], "committed")
        self.call("upload-abort", {"transfer_id": handle["transfer_id"]})
        self.assertEqual((self.path / "file").read_bytes(), b"abc")

    def test_incomplete_and_corrupt_upload_never_publish(self):
        handle = self.begin()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.call("upload-commit", {"transfer_id": handle["transfer_id"]})
        self.put(handle, b"bad")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            self.call("upload-commit", {"transfer_id": handle["transfer_id"]})
        self.assertFalse((self.path / "file").exists())
        self.assertEqual(self.call("upload-status", {"transfer_id": handle["transfer_id"]})["state"], "failed")
        self.call("upload-abort", {"transfer_id": handle["transfer_id"]})
        self.assertFalse(list(self.path.glob(".swcli-*")))

    def test_size_active_count_and_session_boundaries(self):
        with self.assertRaisesRegex(ValueError, "maximum"):
            self.begin(b"x" * 17)
        handle = self.begin(path="0")
        for name in ("upload-status", "upload-commit", "upload-abort"):
            with self.assertRaisesRegex(ValueError, "session"):
                self.call(name, {"transfer_id": handle["transfer_id"]}, session="other")
        for i in range(1, 4):
            self.begin(path=str(i))
        with self.assertRaisesRegex(ValueError, "limit"):
            self.begin(path="fifth")
        self.assertEqual(len(list(self.path.glob(".swcli-*"))), 4)
        self.now = 1801
        self.begin(path="after-expiry")
        self.assertEqual(len(list(self.path.glob(".swcli-*"))), 1)

    def test_download_detects_source_mutation_and_blocks_staging_path(self):
        (self.path / "source").write_bytes(b"abc")
        handle = self.call("download-begin", {"path": "source"})
        (self.path / "source").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.call("download-chunk", {"transfer_id": handle["transfer_id"], "offset": 0, "length": 16})
        for path in ("../secret", ".swcli-upload-private.tmp"):
            with self.assertRaises(ValueError):
                self.call("download-begin", {"path": path})

    def test_failed_transfers_count_against_resource_quota(self):
        for i in range(4):
            record = self.begin(path=str(i))
            self.put(record, b"bad")
            with self.assertRaises(ValueError):
                self.call("upload-commit", {"transfer_id": record["transfer_id"]})
        with self.assertRaisesRegex(ValueError, "limit"):
            self.begin(path="fifth")
        self.assertEqual(len(list(self.path.glob(".swcli-*"))), 4)

    def test_empty_file_commits_without_chunks(self):
        handle = self.begin(b"")
        result = self.call("upload-commit", {"transfer_id": handle["transfer_id"]})
        self.assertEqual(result["state"], "committed")
        self.assertEqual((self.path / "file").read_bytes(), b"")

    def test_workspace_operations_forbid_cad_context(self):
        for context in ({"document_id": "active"}, {"lease_id": "l-ab12cd34ef56"}, {"expected_update_stamp": 0}):
            data = request("download-begin", {"path": "file"})
            with self.assertRaises(ValueError):
                validate_request(dict(data, **context))


class FileTransferSocketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cert_temp = tempfile.TemporaryDirectory()
        cls.cert, cls.key = certificate(Path(cls.cert_temp.name) / "tls")
        cls.token = Path(cls.cert_temp.name) / "token"
        cls.token.write_text("integration-secret-token-" + uuid.uuid4().hex)

    @classmethod
    def tearDownClass(cls):
        cls.cert_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.local, self.remote = self.path / "client", self.path / "host"
        self.local.mkdir(); self.remote.mkdir()
        self.store = WorkspaceStore(self.remote, max_bytes=20 * CHUNK_BYTES)
        self.manager = Mock()
        self.server = SwclidServer(("127.0.0.1", 0), self.manager, workspace=self.store,
            security=ServerSecurity.load(str(self.cert), str(self.key), str(self.token)))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)
        self.endpoint = "127.0.0.1:" + str(self.server.server_address[1])
        self.env = {"SWCLI_TLS_CA_FILE": str(self.cert), "SWCLI_AUTH_TOKEN_FILE": str(self.token), "SWCLI_TLS_SERVER_NAME": "localhost",
                    "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
        p = patch.dict(os.environ, self.env); p.start(); self.addCleanup(p.stop)
        self.client = FileTransferClient(self.local, endpoint=self.endpoint, session_id="socket-tests")

    def source(self):
        source = self.local / "大文件.bin"
        with source.open("wb") as stream:
            for i in range(9):
                stream.write(bytes([i]) * CHUNK_BYTES)
            stream.write(b"final")
        return source

    def test_actual_tls_roundtrip_larger_than_inline_limit_and_cli(self):
        source = self.source(); progress = []
        result = self.client.upload(source.name, "models/large.bin", progress=lambda d,t: progress.append((d,t)))
        self.assertTrue(result["success"]); self.assertGreater(result["size_bytes"], 8 * CHUNK_BYTES)
        self.assertEqual(progress[-1], (source.stat().st_size,) * 2)
        result = self.client.download("models/large.bin", "returned.bin")
        with source.open("rb") as a, (self.local / "returned.bin").open("rb") as b:
            self.assertEqual(file_hash(a), file_hash(b))
        self.assertFalse(list(self.remote.rglob(".swcli-*")))
        self.assertFalse(list(self.local.rglob(".swcli-*")))
        cli = subprocess.run([sys.executable, "-m", "swcli", "--endpoint", self.endpoint,
            "--client-workspace", str(self.local), "transfer", "download", "models/large.bin", "cli.bin", "--json"],
            capture_output=True, text=True, env=dict(os.environ))
        self.assertEqual(cli.returncode, 0, cli.stderr + cli.stdout)
        self.assertTrue(json.loads(cli.stdout)["success"])
        self.manager.call.assert_not_called(); self.manager.shutdown.assert_not_called()

    def test_interrupted_upload_exposes_handle_and_can_resume_without_rewriting(self):
        source = self.source(); original = self.client.rpc; writes = []
        def interrupt(name, parameters, **kwargs):
            if name == "upload-chunk":
                writes.append(parameters["offset"])
                if len(writes) == 2:
                    raise ConnectionError("interrupted before sending chunk")
            return original(name, parameters, **kwargs)
        with patch.object(self.client, "rpc", side_effect=interrupt):
            with self.assertRaises(TransferError) as error:
                self.client.upload(source.name, "resume.bin")
        handle = error.exception.transfer_id
        self.assertTrue(handle); self.assertEqual(error.exception.session_id, "socket-tests")
        self.assertFalse((self.remote / "resume.bin").exists())
        observed = []
        result = self.client.upload(source.name, "resume.bin", resume_transfer=handle, progress=lambda d,t: observed.append(d))
        self.assertEqual(observed[0], CHUNK_BYTES)
        self.assertTrue(result["success"])

    def test_corrupt_download_preserves_existing_destination(self):
        (self.remote / "file").write_bytes(b"original")
        (self.local / "existing").write_bytes(b"keep")
        original = self.client.rpc
        def corrupt(name, p, **kwargs):
            value = original(name, p, **kwargs)
            if name == "download-chunk":
                value["data"] = base64.b64encode(b"tampered").decode()
            return value
        with patch.object(self.client, "rpc", side_effect=corrupt), self.assertRaises(TransferError):
            self.client.download("file", "existing", overwrite=True)
        self.assertEqual((self.local / "existing").read_bytes(), b"keep")
        self.assertFalse(list(self.local.glob(".swcli-*")))

    @unittest.skipUnless(sys.version_info >= (3,10) and importlib.util.find_spec("mcp"), "optional MCP SDK")
    def test_official_sdk_file_tools_copy_bytes_between_explicit_roots(self):
        import asyncio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        source = self.source()
        async def exercise():
            env = dict(os.environ, SWCLI_CLIENT_WORKSPACE=str(self.local))
            parameters = StdioServerParameters(command=sys.executable,
                args=["-m", "swcli", "--endpoint", self.endpoint, "mcp", "serve"], env=env)
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    names = {t.name for t in (await session.list_tools()).tools}
                    self.assertIn("upload_file", names); self.assertIn("download_file", names)
                    progress = []
                    async def on_progress(done, total, message):
                        progress.append((done, total))
                    uploaded = await session.call_tool("upload_file", {"source": source.name, "destination": "mcp.bin"}, progress_callback=on_progress)
                    self.assertEqual(progress[-1], (source.stat().st_size,) * 2)
                    self.assertFalse(uploaded.isError, uploaded)
                    self.assertLess(len(uploaded.model_dump_json()), 4096)
                    downloaded = await session.call_tool("download_file", {"source": "mcp.bin", "destination": "mcp-return.bin"})
                    self.assertFalse(downloaded.isError, downloaded)
                    escaped = await session.call_tool("upload_file", {"source": "../secret", "destination": "escape"})
                    self.assertTrue(escaped.isError)
        asyncio.run(exercise())
        with source.open("rb") as a, (self.local / "mcp-return.bin").open("rb") as b:
            self.assertEqual(file_hash(a), file_hash(b))
        self.manager.call.assert_not_called()


class TransferReviewRegressions(unittest.TestCase):
    def test_hash_does_not_block_unrelated_transfer_and_close_waits(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "source").write_bytes(b"abc")
            store = WorkspaceStore(directory)
            entered, proceed, completed, closed = (threading.Event() for _ in range(4))
            failures = []
            def digest(stream):
                entered.set()
                if not proceed.wait(5):
                    raise RuntimeError("test hash barrier timed out")
                return hashlib.sha256(b"abc").hexdigest()
            def begin():
                try: store.execute(request("download-begin", {"path": "source"}))
                except Exception as exc: failures.append(exc)
            def independent():
                try:
                    store.execute(request("upload-begin", {"path": "out", "size_bytes": 0,
                        "sha256": hashlib.sha256(b"").hexdigest()}))
                    completed.set()
                except Exception as exc: failures.append(exc)
            def close():
                store.close(); closed.set()
            with patch("swcli.workspace.file_hash", digest):
                a = threading.Thread(target=begin); a.start()
                self.assertTrue(entered.wait(2))
                b = threading.Thread(target=independent); b.start()
                try:
                    self.assertTrue(completed.wait(2))
                    c = threading.Thread(target=close); c.start()
                    self.assertFalse(closed.wait(.05))
                finally:
                    proceed.set(); a.join(5); b.join(5)
                c.join(5)
            self.assertTrue(closed.is_set())
            self.assertEqual(failures, [])

    def test_initial_download_and_upload_errors_have_transfer_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FileTransferClient(directory, session_id="review")
            cause = ConnectionRefusedError("offline")
            cause._swcli_transport_phase = "connect"
            with patch.object(client, "rpc", side_effect=cause):
                with self.assertRaises(TransferError) as caught:
                    client.download("source", "target")
            self.assertIs(caught.exception.__cause__, cause)
            self.assertEqual(caught.exception.session_id, "review")
            self.assertEqual(caught.exception._swcli_transport_phase, "connect")
            with self.assertRaises(TransferError) as caught:
                client.upload("missing", "target")
            self.assertIsInstance(caught.exception.__cause__, OSError)
