import copy
import importlib.util
import io
import json
import math
from pathlib import Path
import subprocess
import tempfile
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
        elif operation == "sketch.inspect":
            if document["sketch"] != values["sketch_id"]:
                return self.error("SketchNotFound")
            result.update(
                geometry_complete=True,
                editing=False,
                coordinate_system="sketch-local",
                profile_segment_count=1,
                segment_count=1,
                sketch={"absorbed": document["absorbed"]},
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
        ):
            try:
                self.smoke.run()
            finally:
                self.smoke.cleanup()

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
            3,
        )
        self.assertFalse(self.daemon.documents)
        self.assertFalse(self.smoke.record["cleanup_errors"])
        self.assertTrue(
            all(
                item["expired_handles_rejected"] for item in self.smoke.record["planes"]
            )
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
            self.assertEqual(record["error"]["message"], "original failure")
            self.assertEqual(record["cleanup_errors"], [])
