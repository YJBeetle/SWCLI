import copy
import argparse
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

script = Path(__file__).resolve().parents[1] / "scripts/ci/verify-driving-dimensions.py"
spec = importlib.util.spec_from_file_location("driving_smoke", script)
driving_smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driving_smoke)


class FakeDaemon:
    """Contract fixture for the gate, not native adapter/COM verification."""

    def __init__(self):
        self.documents = {}
        self.current = {}
        self.active = None
        self.files = {}
        self.serial = 0
        self.fail_lease = False
        self.modify_inspect = False
        self.wrong_volume = False
        self.stale_dimensions = False
        self.lose_foreground = False
        self.close_fails = False
        self.list_empty = False
        self.list_changes_stamp = False
        self.list_moves_foreground = False
        self.list_changes_current = False
        self.list_id_drift = False
        self.reopened_inspect_wrong_id = False
        self.list_serial = 0
        self.calls = []

    @staticmethod
    def response(result):
        return {"success": True, "result": result}

    @staticmethod
    def error(code):
        return {"success": False, "error": {"code": code, "message": code}}

    def descriptor(self, document_id, session):
        document = self.documents[document_id]
        return {
            "document_id": document_id,
            "active": self.active == document_id,
            "current": self.current.get(session) == document_id,
            "update_stamp": document["stamp"],
        }

    def dimension(self, document):
        return {
            "dimension_id": document["dimension"],
            "sketch_id": document["sketch"],
            "kind": "diameter",
            "unit": "millimeter",
            "value": document["radius"] * 2,
            "driven_state": 2,
            "read_only": False,
            "configuration": "默认",
            "native_name": "D1@草图1@零件",
        }

    def call(self, operation, parameters=None, **context):
        self.calls.append((operation, parameters, context))
        values = parameters or {}
        session = context["session_id"]
        document_id = context.get("document_id")
        if operation == "daemon.health":
            return self.response(
                {
                    "host_connected": True,
                    "host": {"process_id": 123},
                    "operations": [
                        "sketch.dimension-diameter",
                        "dimension.inspect",
                        "dimension.set",
                        "sketch.list",
                    ],
                }
            )
        if operation in ("document.create", "document.open"):
            self.serial += 1
            document_id = f"d-{self.serial:06d}"
            if operation == "document.open":
                document = copy.deepcopy(self.files[values["path"]])
                document["lease"] = None
                if not self.stale_dimensions:
                    document["dimension"] = None
                    document["sketch"] = None
            else:
                document = {
                    "stamp": 1,
                    "sketch": None,
                    "dimension": None,
                    "lease": None,
                    "radius": 0,
                    "absorbed": False,
                }
            self.documents[document_id] = document
            self.current[session] = self.active = document_id
            return self.response(
                {"ok": True, "document": self.descriptor(document_id, session)}
            )
        if operation == "document.list":
            return self.response(
                {
                    "current_document_id": self.current.get(session),
                    "documents": [
                        self.descriptor(key, session) for key in self.documents
                    ],
                }
            )
        document = self.documents[document_id]
        result = {"ok": True, "document": self.descriptor(document_id, session)}
        if operation == "document.lease.acquire":
            document["lease"] = (session, "l-000000000001")
            result["lease"] = {"lease_id": document["lease"][1]}
        elif operation == "document.inspect":
            if "detail" in values:
                result["structure"] = {
                    "bodies": {"count": 1},
                    "features": {"truncated": False, "items": [{"name": "Boss1"}]},
                }
        elif operation == "document.measure":
            radius = document["radius"]
            result["metrics"] = {
                "solid_body_count": 1,
                "volume_mm3": math.pi * radius**2 * 10
                + (1 if self.wrong_volume else 0),
                "surface_area_mm2": 2 * math.pi * radius * (radius + 10),
            }
        elif operation == "document.diagnose":
            result.update(diagnostics={"healthy": True}, needs_rebuild=0)
        elif operation == "dimension.inspect":
            if document["dimension"] != values["dimension_id"]:
                return self.error("DimensionNotFound")
            result["dimension"] = self.dimension(document)
            if self.modify_inspect:
                document["stamp"] += 1
        elif operation == "sketch.list":
            self.list_serial += 1
            if document["sketch"] is None or self.list_id_drift:
                document["sketch"] = f"s-{self.list_serial + 100000:06d}"
            sketches = (
                []
                if self.list_empty
                else [
                    {
                        "sketch_id": document["sketch"],
                        "name": "保存的圆草图",
                        "type": "ProfileFeature",
                        "constraint_status": 2,
                        "absorbed": document["absorbed"],
                        "owner": {"name": "Boss1", "type": "ICE"},
                    }
                ]
            )
            result.update(sketches=sketches, count=len(sketches))
            if self.list_changes_stamp:
                document["stamp"] += 1
            if self.list_moves_foreground:
                self.active = document_id
            if self.list_changes_current:
                self.current[session] = document_id
        elif operation == "sketch.inspect":
            if document["sketch"] != values["sketch_id"]:
                return self.error("SketchNotFound")
            result.update(
                geometry_complete=True,
                editing=False,
                coordinate_system="sketch-local",
                profile_segment_count=1,
                segment_count=1,
                sketch={
                    "absorbed": document["absorbed"],
                    "sketch_id": (
                        "s-999999"
                        if self.reopened_inspect_wrong_id
                        and document["dimension"] is None
                        else document["sketch"]
                    ),
                },
                segments=[
                    {
                        "construction": False,
                        "geometry": {
                            "kind": "arc",
                            "complete_circle": True,
                            "radius_mm": document["radius"],
                            "center_mm": {"x": 3, "y": 4, "z": 0},
                        },
                    }
                ],
            )
        else:
            if (
                context.get("expected_update_stamp", document["stamp"])
                != document["stamp"]
            ):
                return self.error("DocumentUpdateConflict")
            if (
                document["lease"]
                and (session, context.get("lease_id")) != document["lease"]
            ):
                if not self.fail_lease:
                    return self.error("DocumentLeaseConflict")
            if operation == "document.close":
                if self.close_fails:
                    return self.error("TestCloseFailed")
                del self.documents[document_id]
                self.current = {
                    key: value
                    for key, value in self.current.items()
                    if value != document_id
                }
                if self.active == document_id:
                    self.active = next(reversed(self.documents), None)
            elif operation == "sketch.circle":
                document["sketch"] = f"s-{self.serial:06d}"
                document["radius"] = values["radius_mm"]
                result["sketch"] = {"sketch_id": document["sketch"]}
            elif operation == "sketch.dimension-diameter":
                if document["dimension"]:
                    return self.error("SketchAlreadyDimensioned")
                document["dimension"] = f"m-{self.serial:06d}"
                document["radius"] = values["diameter_mm"] / 2
                result.update(
                    dimension=self.dimension(document),
                    native_status=0,
                    geometry_verification={"passed": True},
                    editing=False,
                )
            elif operation == "feature.extrude":
                document["absorbed"] = True
                result["feature"] = {"name": "Boss1"}
            elif operation == "dimension.set":
                if document["dimension"] != values["dimension_id"]:
                    return self.error("DimensionNotFound")
                document["radius"] = values["value_mm"] / 2
                result.update(
                    dimension=self.dimension(document),
                    native_status=0,
                    geometry_verification={"passed": True},
                    editing=False,
                )
                if self.lose_foreground:
                    self.active = document_id
            elif operation == "document.save-as":
                self.files[values["output"]] = copy.deepcopy(document)
                result["artifact"] = {"path": values["output"], "size_bytes": 1000}
            else:
                raise AssertionError(operation)
            document["stamp"] += 1
        return self.response(result)

    def command(self, command, **kwargs):
        def flag(name):
            return command[command.index(name) + 1]

        index = command.index("120") + 1
        arguments = command[index:]
        context = {"session_id": flag("--session"), "document_id": flag("--document")}
        if "--lease" in arguments:
            context["lease_id"] = flag("--lease")
        if "--if-update-stamp" in arguments:
            context["expected_update_stamp"] = int(flag("--if-update-stamp"))
        operation = ".".join(arguments[:2])
        if operation == "sketch.dimension-diameter":
            values = {
                "sketch_id": arguments[2],
                "diameter_mm": float(flag("--diameter-mm")),
            }
        elif operation == "dimension.set":
            values = {
                "dimension_id": arguments[2],
                "value_mm": float(flag("--value-mm")),
            }
        elif operation == "sketch.list":
            values = {}
        else:
            values = {"dimension_id": arguments[2]}
        response = self.call(operation, values, **context)
        return subprocess.CompletedProcess(
            command,
            0 if response["success"] else 1,
            json.dumps(response.get("result", response)).encode("utf-8"),
            b"",
        )


class DrivingDimensionsSmokeTests(unittest.TestCase):
    def setUp(self):
        self.daemon = FakeDaemon()
        self.smoke = driving_smoke.DrivingSmoke(
            endpoint="127.0.0.1:1",
            session="test-driving",
            output_directory=r"C:\Workspace\test",
        )

    def run_smoke(self):
        with (
            mock.patch.object(
                driving_smoke, "call_daemon", side_effect=self.daemon.call
            ),
            mock.patch.object(
                driving_smoke.subprocess, "run", side_effect=self.daemon.command
            ),
            mock.patch("sys.stdout", new_callable=io.StringIO) as progress,
        ):
            try:
                self.smoke.run()
            finally:
                self.smoke.cleanup()
                self.progress = progress.getvalue()

    def test_all_planes_and_installed_cli_route_pass(self):
        self.run_smoke()
        self.assertEqual(
            [item["plane"] for item in self.smoke.record["planes"]],
            ["front", "top", "right"],
        )
        self.assertEqual(
            len(
                [
                    item
                    for item in self.smoke.record["events"]
                    if item["transport"] == "cli"
                ]
            ),
            5,
        )
        self.assertFalse(self.daemon.documents)
        self.assertFalse(self.smoke.record["cleanup_errors"])
        self.assertTrue(
            all(
                item["expired_handles_rejected"] for item in self.smoke.record["planes"]
            )
        )
        for plane in self.smoke.record["planes"]:
            discovery = plane["reopened_sketch_discovery"]
            self.assertNotEqual(discovery["sketch_id"], plane["sketch_id"])
            self.assertEqual(
                discovery["update_stamp_before"], discovery["update_stamp_after"]
            )
            self.assertEqual(
                discovery["selection_before"], discovery["selection_after"]
            )
            self.assertEqual(
                discovery["listed"]["sketches"][0]["sketch_id"],
                discovery["observed"]["sketch"]["sketch_id"],
            )
        self.assertEqual(
            self.progress.splitlines(),
            [
                f"Driving-dimension gate: {plane} {phase}"
                for plane in ("front", "top", "right")
                for phase in ("starting", "passed")
            ],
        )

    def test_wrapper_is_one_exact_executable_without_shell(self):
        wrapper = "/tmp/a path with spaces/sw-cli"
        self.smoke.cli = [wrapper]
        with mock.patch.object(
            driving_smoke.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, b'{"ok":true}', b""),
        ) as run:
            self.smoke.command(["dimension", "inspect", "m-ab12cd"])
        command = run.call_args.args[0]
        self.assertEqual(command[0], wrapper)
        self.assertEqual(command[1:3], ["--endpoint", "127.0.0.1:1"])
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_default_cli_stays_isolated(self):
        self.assertEqual(self.smoke.cli[1:], ["-I", "-m", "swcli"])

    def test_cli_command_validation_rejects_ambiguous_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "sw cli"
            executable.write_text("test fixture", encoding="utf-8")
            executable.chmod(0o755)
            self.assertEqual(
                driving_smoke.cli_executable(str(executable)), str(executable.resolve())
            )
            for invalid in (
                "sw-cli",
                directory,
                str(executable) + " --flag",
                str(Path(directory) / "missing"),
            ):
                with (
                    self.subTest(path=invalid),
                    self.assertRaises(argparse.ArgumentTypeError),
                ):
                    driving_smoke.cli_executable(invalid)
            with mock.patch.object(driving_smoke.os, "access", return_value=False):
                with self.assertRaises(argparse.ArgumentTypeError):
                    driving_smoke.cli_executable(str(executable))

    def test_native_namespace_directory_requires_absolute_path(self):
        for value in (
            r"Z:\workspace\proof",
            r"\\server\share\proof",
            "/workspace/proof",
        ):
            self.assertEqual(driving_smoke.host_directory(value), value)
        for invalid in (
            "",
            "relative/proof",
            r"C:relative",
            r"\\server",
            "/workspace/\0proof",
        ):
            with (
                self.subTest(path=invalid),
                self.assertRaises(argparse.ArgumentTypeError),
            ):
                driving_smoke.host_directory(invalid)

    def test_main_passes_wrapper_and_native_directory_without_translation(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "sw cli"
            executable.write_text("test fixture", encoding="utf-8")
            executable.chmod(0o755)
            native_directory = r"Z:\output path\proof"
            with (
                mock.patch.object(
                    driving_smoke, "DrivingSmoke", return_value=self.smoke
                ) as factory,
                mock.patch.object(self.smoke, "run"),
                mock.patch("sys.stdout", new_callable=io.StringIO),
            ):
                driving_smoke.main(
                    [
                        "--output-dir",
                        directory,
                        "--host-output-dir",
                        native_directory,
                        "--cli-command",
                        str(executable),
                    ]
                )
            self.assertEqual(
                factory.call_args.kwargs["cli"], [str(executable.resolve())]
            )
            self.assertEqual(
                factory.call_args.kwargs["output_directory"], native_directory
            )

    def test_lease_false_success_fails_and_cleans_only_owned_documents(self):
        self.daemon.fail_lease = True
        with self.assertRaisesRegex(RuntimeError, "DocumentLeaseConflict"):
            self.run_smoke()
        self.assertFalse(self.daemon.documents)
        self.assertFalse(
            any(
                item[0].startswith("daemon.") and item[0] != "daemon.health"
                for item in self.daemon.calls
            )
        )

    def test_inspection_that_mutates_stamp_fails(self):
        self.daemon.modify_inspect = True
        with self.assertRaisesRegex(RuntimeError, "inspect changed native stamp"):
            self.run_smoke()

    def test_false_success_measurement_fails(self):
        self.daemon.wrong_volume = True
        with self.assertRaisesRegex(RuntimeError, "volume is incorrect"):
            self.run_smoke()

    def test_foreground_not_restored_fails(self):
        self.daemon.lose_foreground = True
        with self.assertRaisesRegex(RuntimeError, "foreground document"):
            self.run_smoke()

    def test_reopened_handles_must_expire(self):
        self.daemon.stale_dimensions = True
        with self.assertRaisesRegex(RuntimeError, "DimensionNotFound"):
            self.run_smoke()

    def test_missing_reopened_sketch_fails_instead_of_skipping_discovery(self):
        self.daemon.list_empty = True
        with self.assertRaisesRegex(RuntimeError, "discover exactly one"):
            self.run_smoke()
        self.assertFalse(self.daemon.documents)
        self.assertEqual(self.smoke.record["planes"], [])

    def test_repeated_discovery_must_keep_handle_stable(self):
        self.daemon.list_id_drift = True
        with self.assertRaisesRegex(
            RuntimeError, "changed a live native sketch handle"
        ):
            self.run_smoke()

    def test_reopened_inspect_must_report_the_newly_listed_exact_handle(self):
        self.daemon.reopened_inspect_wrong_id = True
        with self.assertRaisesRegex(RuntimeError, "different registered handle"):
            self.run_smoke()
        self.assertFalse(self.daemon.documents)
        proof = self.smoke.record["reopened_sketch_discoveries"][0]
        self.assertNotEqual(
            proof["sketch_id"], proof["observed"]["sketch"]["sketch_id"]
        )

    def test_reopened_discovery_does_not_change_stamp_foreground_or_session(self):
        for change, message in (
            ("list_changes_stamp", "changed native update stamp"),
            ("list_moves_foreground", "background document identity"),
            ("list_changes_current", "background document identity"),
        ):
            with self.subTest(change=change):
                self.setUp()
                setattr(self.daemon, change, True)
                with self.assertRaisesRegex(RuntimeError, message):
                    self.run_smoke()
                self.assertFalse(self.daemon.documents)

    def test_cleanup_failure_is_visible(self):
        self.daemon.fail_lease = self.daemon.close_fails = True
        with self.assertRaisesRegex(RuntimeError, "DocumentLeaseConflict"):
            self.run_smoke()
        self.assertEqual(len(self.smoke.record["cleanup_errors"]), 2)
        self.assertIn(
            "TestCloseFailed", self.smoke.record["cleanup_errors"][0]["message"]
        )

    def test_host_namespace_path_is_explicit(self):
        self.assertEqual(
            driving_smoke.host_path(r"C:\Workspace\proof", "front.SLDPRT"),
            r"C:\Workspace\proof\front.SLDPRT",
        )
        self.assertEqual(
            driving_smoke.host_path("/workspace/proof", "top.SLDPRT"),
            "/workspace/proof/top.SLDPRT",
        )
        self.assertEqual(
            driving_smoke.host_path(r"\\server\share", "right.SLDPRT"),
            r"\\server\share\right.SLDPRT",
        )

    def test_existing_record_refuses_before_any_daemon_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            record = Path(directory) / "driving-dimensions.json"
            record.write_text("previous proof", encoding="utf-8")
            with mock.patch.object(driving_smoke, "call_daemon") as call:
                with self.assertRaises(FileExistsError):
                    driving_smoke.main(["--output-dir", directory])
                call.assert_not_called()
            self.assertEqual(record.read_text(encoding="utf-8"), "previous proof")

    def test_main_retains_original_failure_and_cleanup_record(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                mock.patch.object(
                    driving_smoke, "DrivingSmoke", return_value=self.smoke
                ),
                mock.patch.object(
                    self.smoke, "run", side_effect=RuntimeError("original failure")
                ),
                mock.patch("sys.stdout", new_callable=io.StringIO),
            ):
                with self.assertRaisesRegex(RuntimeError, "original failure"):
                    driving_smoke.main(["--output-dir", directory])
            record = json.loads(
                (Path(directory) / "driving-dimensions.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(record["success"])
            self.assertEqual(record["state"], "completed")
            self.assertEqual(record["error"]["message"], "original failure")
            self.assertEqual(record["cleanup_errors"], [])

    def test_main_reserves_valid_running_record_before_any_work(self):
        with tempfile.TemporaryDirectory() as directory:
            record_path = Path(directory) / "driving-dimensions.json"

            def inspect_initial_record():
                record = json.loads(record_path.read_text(encoding="utf-8"))
                self.assertEqual(record["state"], "running")
                self.assertEqual(record["stage"], "initializing")
                self.assertNotIn("success", record)
                self.assertEqual(record["events"], [])

            with (
                mock.patch.object(
                    driving_smoke, "DrivingSmoke", return_value=self.smoke
                ),
                mock.patch.object(
                    self.smoke, "run", side_effect=inspect_initial_record
                ),
                mock.patch("sys.stdout", new_callable=io.StringIO),
            ):
                driving_smoke.main(["--output-dir", directory])
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(record["state"], "completed")
            self.assertTrue(record["success"])

    def test_completed_events_and_stages_are_atomically_checkpointed(self):
        with tempfile.TemporaryDirectory() as directory:
            record_path = Path(directory) / "driving-dimensions.json"
            snapshots = []
            write = driving_smoke.EvidenceCheckpoint.write

            def capture(checkpoint, record):
                write(checkpoint, record)
                snapshots.append(json.loads(record_path.read_text(encoding="utf-8")))
                self.assertEqual(record_path.stat().st_mode & 0o777, checkpoint.mode)

            with (
                mock.patch.object(
                    driving_smoke, "DrivingSmoke", return_value=self.smoke
                ),
                mock.patch.object(
                    driving_smoke, "call_daemon", side_effect=self.daemon.call
                ),
                mock.patch.object(
                    driving_smoke.subprocess, "run", side_effect=self.daemon.command
                ),
                mock.patch.object(
                    driving_smoke.EvidenceCheckpoint, "write", new=capture
                ),
                mock.patch("sys.stdout", new_callable=io.StringIO),
            ):
                driving_smoke.main(["--output-dir", directory])
            self.assertEqual(snapshots[0]["stage"], "daemon.health.completed")
            for record in snapshots[:-1]:
                self.assertEqual(record["state"], "running")
                self.assertNotIn("success", record)
            cli_snapshots = [
                item for item in snapshots if item["stage"] == "cli.completed"
            ]
            self.assertTrue(cli_snapshots)
            self.assertTrue(
                all(item["events"][-1]["result"]["ok"] for item in cli_snapshots)
            )
            for plane in ("front", "top", "right"):
                verified = next(
                    item
                    for item in snapshots
                    if item["stage"] == f"plane.{plane}.verified"
                )
                self.assertEqual(verified["planes"][-1]["plane"], plane)
                self.assertEqual(verified["current_plane"], plane)
            self.assertTrue(
                any(
                    item["stage"] == "reopened-sketch-discovery.observed"
                    for item in snapshots
                )
            )
            self.assertEqual(snapshots[-1]["state"], "completed")
            self.assertTrue(snapshots[-1]["success"])
            self.assertFalse(self.daemon.documents)

    def test_atomic_replacement_failure_keeps_last_record_and_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            record_path = Path(directory) / "driving-dimensions.json"
            checkpoint = driving_smoke.EvidenceCheckpoint(record_path)
            original = {"state": "running", "events": []}
            checkpoint.reserve(original)
            original_mode = record_path.stat().st_mode & 0o777
            original_bytes = record_path.read_bytes()
            with mock.patch.object(
                Path, "replace", side_effect=OSError("replace denied")
            ):
                with self.assertRaisesRegex(OSError, "replace denied"):
                    checkpoint.write({"state": "running", "events": ["latest"]})
            self.assertEqual(record_path.read_bytes(), original_bytes)
            self.assertEqual(
                list(Path(directory).glob(".driving-dimensions.*.tmp")), []
            )
            checkpoint.write({"state": "running", "events": ["latest"]})
            self.assertEqual(record_path.stat().st_mode & 0o777, original_mode)
            self.assertEqual(
                json.loads(record_path.read_text(encoding="utf-8"))["events"],
                ["latest"],
            )

    def test_checkpoint_failure_tracks_resources_before_cleanup(self):
        for failed_operation in (
            "document.create",
            "document.lease.acquire",
            "document.open",
        ):
            with (
                self.subTest(operation=failed_operation),
                tempfile.TemporaryDirectory() as directory,
            ):
                self.setUp()
                record_path = Path(directory) / "driving-dimensions.json"
                write = driving_smoke.EvidenceCheckpoint.write
                failed = False

                def fail_once(checkpoint, record):
                    nonlocal failed
                    if (
                        record["stage"] == failed_operation + ".completed"
                        and not failed
                    ):
                        failed = True
                        raise OSError("evidence disk unavailable")
                    write(checkpoint, record)

                with (
                    mock.patch.object(
                        driving_smoke, "DrivingSmoke", return_value=self.smoke
                    ),
                    mock.patch.object(
                        driving_smoke, "call_daemon", side_effect=self.daemon.call
                    ),
                    mock.patch.object(
                        driving_smoke.subprocess, "run", side_effect=self.daemon.command
                    ),
                    mock.patch.object(
                        driving_smoke.EvidenceCheckpoint, "write", new=fail_once
                    ),
                    mock.patch("sys.stdout", new_callable=io.StringIO),
                    mock.patch("sys.stderr", new_callable=io.StringIO) as warnings,
                ):
                    with self.assertRaisesRegex(OSError, "evidence disk unavailable"):
                        driving_smoke.main(["--output-dir", directory])
                self.assertTrue(failed)
                self.assertFalse(self.daemon.documents)
                self.assertFalse(self.smoke.owned)
                record = json.loads(record_path.read_text(encoding="utf-8"))
                self.assertEqual(record["state"], "completed")
                self.assertFalse(record["success"])
                self.assertEqual(
                    record["error"]["message"], "evidence disk unavailable"
                )
                self.assertEqual(
                    record["checkpoint_errors"][0]["stage"],
                    failed_operation + ".completed",
                )
                self.assertEqual(record["cleanup_errors"], [])
                self.assertIn("evidence checkpoint failed", warnings.getvalue())

    def test_persistent_checkpoint_failure_does_not_interrupt_owned_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            record_path = Path(directory) / "driving-dimensions.json"

            def run():
                self.smoke.create()
                self.smoke.create()
                self.smoke.checkpoint_writer = mock.Mock(
                    side_effect=OSError("disk gone")
                )
                self.smoke.checkpoint("fixture.write")

            with (
                mock.patch.object(
                    driving_smoke, "DrivingSmoke", return_value=self.smoke
                ),
                mock.patch.object(
                    driving_smoke, "call_daemon", side_effect=self.daemon.call
                ),
                mock.patch.object(self.smoke, "run", side_effect=run),
                mock.patch("sys.stdout", new_callable=io.StringIO),
                mock.patch("sys.stderr", new_callable=io.StringIO) as warnings,
            ):
                with self.assertRaisesRegex(OSError, "disk gone"):
                    driving_smoke.main(["--output-dir", directory])
            self.assertFalse(self.daemon.documents)
            self.assertFalse(self.smoke.owned)
            self.assertEqual(self.smoke.record["cleanup_errors"], [])
            self.assertGreater(len(self.smoke.record["checkpoint_errors"]), 2)
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(record["state"], "running")
            self.assertNotIn("success", record)
            self.assertEqual(len(record["events"]), 2)
            self.assertIn("disk gone", warnings.getvalue())

    def test_business_failure_survives_cleanup_and_final_checkpoint_failures(self):
        with tempfile.TemporaryDirectory() as directory:

            def run():
                self.smoke.create()
                self.smoke.create()
                self.smoke.checkpoint_writer = mock.Mock(
                    side_effect=OSError("disk gone")
                )
                raise RuntimeError("original business failure")

            with (
                mock.patch.object(
                    driving_smoke, "DrivingSmoke", return_value=self.smoke
                ),
                mock.patch.object(
                    driving_smoke, "call_daemon", side_effect=self.daemon.call
                ),
                mock.patch.object(self.smoke, "run", side_effect=run),
                mock.patch("sys.stdout", new_callable=io.StringIO),
                mock.patch("sys.stderr", new_callable=io.StringIO) as warnings,
            ):
                with self.assertRaisesRegex(RuntimeError, "original business failure"):
                    driving_smoke.main(["--output-dir", directory])
            self.assertFalse(self.daemon.documents)
            self.assertEqual(
                self.smoke.record["error"]["message"], "original business failure"
            )
            self.assertFalse(self.smoke.record["success"])
            self.assertIn("disk gone", warnings.getvalue())

    def test_failed_business_response_is_checkpointed_without_masking_primary_error(
        self,
    ):
        self.smoke.checkpoint_writer = mock.Mock(side_effect=OSError("disk gone"))
        with (
            mock.patch.object(
                driving_smoke,
                "call_daemon",
                return_value=FakeDaemon.error("COMFailure"),
            ),
            mock.patch("sys.stderr", new_callable=io.StringIO) as warnings,
        ):
            with self.assertRaisesRegex(RuntimeError, "COMFailure"):
                self.smoke.call("sketch.circle")
        event = self.smoke.record["events"][-1]
        self.assertEqual(event["response"]["error"]["code"], "COMFailure")
        self.assertIn("COMFailure", event["error"]["message"])
        self.assertIn("disk gone", warnings.getvalue())

    def test_failed_cli_response_is_checkpointed_without_masking_primary_error(self):
        self.smoke.checkpoint_writer = mock.Mock(side_effect=OSError("disk gone"))
        with (
            mock.patch.object(
                driving_smoke.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    [],
                    1,
                    b'{"ok":false,"error":{"code":"CLIComFailure"}}',
                    b"native diagnostic",
                ),
            ),
            mock.patch("sys.stderr", new_callable=io.StringIO) as warnings,
        ):
            with self.assertRaisesRegex(RuntimeError, "CLIComFailure"):
                self.smoke.command(["dimension", "inspect", "m-ab12cd"])
        event = self.smoke.record["events"][-1]
        self.assertEqual(event["returncode"], 1)
        self.assertEqual(json.loads(event["stdout"])["error"]["code"], "CLIComFailure")
        self.assertEqual(event["stderr"], "native diagnostic")
        self.assertIn("disk gone", warnings.getvalue())

    def test_final_checkpoint_failure_leaves_running_proof_and_exits_unsuccessfully(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            record_path = Path(directory) / "driving-dimensions.json"
            write = driving_smoke.EvidenceCheckpoint.write

            def fail_final(checkpoint, record):
                if record["state"] == "completed":
                    raise OSError("terminal write failed")
                write(checkpoint, record)

            with (
                mock.patch.object(
                    driving_smoke, "DrivingSmoke", return_value=self.smoke
                ),
                mock.patch.object(self.smoke, "run"),
                mock.patch.object(
                    driving_smoke.EvidenceCheckpoint, "write", new=fail_final
                ),
                mock.patch("sys.stdout", new_callable=io.StringIO),
                mock.patch("sys.stderr", new_callable=io.StringIO),
            ):
                with self.assertRaisesRegex(OSError, "terminal write failed"):
                    driving_smoke.main(["--output-dir", directory])
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(record["state"], "running")
            self.assertEqual(record["stage"], "cleanup.completed")
            self.assertNotIn("success", record)
            self.assertFalse(self.smoke.record["success"])
            self.assertEqual(
                self.smoke.record["error"]["message"], "terminal write failed"
            )

    @unittest.skipIf(os.name == "nt", "POSIX SIGKILL fixture; Windows has no SIGKILL")
    def test_killed_fake_gate_retains_latest_running_json_without_daemon(self):
        fixture = """
import importlib.util
import sys
spec = importlib.util.spec_from_file_location('driving_smoke_fixture', sys.argv[1])
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
gate.call_daemon = lambda *args, **kwargs: {'success': True, 'result': {'fixture': 'completed'}}
def paused_run(self):
    self.call('daemon.health')
    self.checkpoint('fixture.paused')
    sys.stdin.read()
gate.DrivingSmoke.run = paused_run
gate.main(['--output-dir', sys.argv[2]])
"""
        with tempfile.TemporaryDirectory() as directory:
            record_path = Path(directory) / "driving-dimensions.json"
            process = subprocess.Popen(
                [sys.executable, "-c", fixture, str(script), directory],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "PYTHONPATH": str(script.parents[2] / "src")},
            )
            try:
                deadline = time.monotonic() + 5
                record = None
                while time.monotonic() < deadline:
                    if record_path.exists():
                        try:
                            record = json.loads(record_path.read_text(encoding="utf-8"))
                        except json.JSONDecodeError:
                            # Exclusive initial reservation is written before
                            # any fake/native work starts; wait for that flush.
                            pass
                        else:
                            if record["stage"] == "fixture.paused":
                                break
                    if process.poll() is not None:
                        self.fail(
                            f"fixture unexpectedly exited: {process.communicate()}"
                        )
                    time.sleep(0.01)
                else:
                    self.fail("fixture did not checkpoint before its deadline")
                process.kill()
                process.communicate(timeout=5)
                record = json.loads(record_path.read_text(encoding="utf-8"))
                self.assertEqual(record["state"], "running")
                self.assertEqual(record["stage"], "fixture.paused")
                self.assertNotIn("success", record)
                self.assertEqual(
                    record["events"][0]["response"]["result"], {"fixture": "completed"}
                )
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
