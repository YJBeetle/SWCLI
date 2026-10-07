"""Portable contract tests for the gate, not proof of native CAD behavior."""

import copy
import importlib.util
import io
import json
import math
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import unittest
from unittest import mock

from swcli.cli import build_parser

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci/verify-modeling.py"
spec = importlib.util.spec_from_file_location("modeling_smoke", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class FakeCLI:
    def __init__(self, directory):
        self.directory = directory
        self.parser = build_parser()
        self.documents = {}
        self.current = {}
        self.active = None
        self.serial = 0
        self.saved = {}
        self.calls = []
        self.rejected = False
        self.defect = None
        self.health_calls = 0

    def descriptor(self, document, session):
        return {
            "document_id": document["id"],
            "path": document["path"],
            "type": 1,
            "modified": document["modified"],
            "update_stamp": document["stamp"],
            "active": self.active == document["id"],
            "current": self.current.get(session) == document["id"],
        }

    @staticmethod
    def failure(code, **extra):
        return {
            "ok": False,
            "error": {"type": code, "message": "native reason"},
            **extra,
        }

    def run(self, command, **kwargs):
        # Parse real generated command lines, including options before paths.
        start = command.index("--endpoint")
        args = self.parser.parse_args(command[start:])
        self.calls.append(args)
        result = self.dispatch(args)
        return subprocess.CompletedProcess(
            command,
            1 if result.get("ok") is False else 0,
            json.dumps(result, ensure_ascii=False).encode("utf-8"),
            b"native stderr\n",
        )

    def dispatch(self, args):
        session = args.session
        action = args.command
        subcommand = getattr(args, action + "_command", None)
        if action in ("capabilities", "daemon"):
            self.health_calls += 1
            health = {
                "host_connected": self.defect != "disconnected",
                "recovery_required": False,
                "host": {
                    "process_id": (
                        124
                        if self.defect == "host-replaced" and self.health_calls > 2
                        else 123
                    )
                },
            }
            return (
                health
                if action == "capabilities"
                else {"success": True, "result": health}
            )
        if action == "document" and subcommand in ("create", "open"):
            self.serial += 1
            document_id = f"d-{self.serial:06x}"
            if subcommand == "open":
                document = copy.deepcopy(
                    self.saved.get(
                        args.path,
                        {
                            "profiles": {},
                            "count": 1,
                            "volume": 12000,
                            "area": 8000,
                            "stamp": 1,
                            "modified": False,
                            "lease": None,
                        },
                    )
                )
                document["path"] = args.path
            else:
                document = {
                    "path": "",
                    "stamp": 1,
                    "modified": False,
                    "profiles": {},
                    "count": 0,
                    "volume": 0,
                    "area": 0,
                    "lease": None,
                }
            document["id"] = document_id
            self.documents[document_id] = document
            self.active = self.current[session] = document_id
            return {
                "ok": True,
                "created": True,
                "document": self.descriptor(document, session),
            }
        if action == "document" and subcommand == "list":
            documents = [
                self.descriptor(document, session)
                for document in self.documents.values()
            ]
            if self.defect == "close-no-op" and self.rejected:
                documents.append({"document_id": "d-orphan"})
            return {"ok": True, "count": len(documents), "documents": documents}
        document_id = getattr(args, "document_id", None) or self.current.get(session)
        if (
            action == "document"
            and subcommand == "lease"
            and args.lease_command in ("renew", "release")
        ):
            document_id = next(
                key
                for key, value in self.documents.items()
                if value["lease"] and value["lease"]["lease_id"] == args.lease_id
            )
        document = self.documents[document_id]
        descriptor = self.descriptor(document, session)
        if action == "document" and subcommand == "lease":
            if args.lease_command == "acquire":
                document["lease"] = {"lease_id": "l-0123456789ab", "session": session}
            result = {"ok": True, "lease": document["lease"]}
            if args.lease_command == "release":
                document["lease"] = None
            return result
        if action == "document" and subcommand == "close":
            self.documents.pop(document_id)
            if self.active == document_id:
                self.active = next(reversed(self.documents), None)
            for owner, current in list(self.current.items()):
                if current == document_id:
                    self.current[owner] = None
            return {"ok": True}
        if action == "document" and subcommand == "inspect":
            if self.defect == "null-stamp":
                descriptor["update_stamp"] = None
            return {
                "ok": True,
                "document": descriptor,
                "structure": {"bodies": {"count": document["count"]}},
            }
        if action == "document" and subcommand == "diagnose":
            return {"ok": True, "needs_rebuild": 0, "diagnostics": {"healthy": True}}
        if action == "document" and subcommand == "measure":
            volume = document["volume"]
            if self.defect == "rejected-volume" and self.rejected:
                volume += 100
            return {
                "ok": True,
                "document": descriptor,
                "metrics": {
                    "solid_body_count": document["count"],
                    "volume_mm3": volume,
                    "surface_area_mm2": document["area"],
                    "centroid_mm": {"x": 10, "y": 20, "z": 10},
                },
            }
        if (
            getattr(args, "expected_update_stamp", None) is not None
            and args.expected_update_stamp != document["stamp"]
        ):
            return self.failure("DocumentUpdateConflict")
        if (
            document["lease"]
            and document["lease"]["session"] != session
            and not (action == "sketch" and subcommand == "inspect")
        ):
            return self.failure("DocumentLeaseConflict")
        if action == "document" and subcommand in ("save-as", "export"):
            target = self.directory / gate.PureWindowsPath(args.output).name
            if target.exists():
                if self.defect == "overwrite-existing":
                    target.write_bytes(b"damaged")
                return self.failure("OutputExists")
            target.write_bytes(
                b"ISO-10303-21;" if subcommand == "export" else b"native model"
            )
            if subcommand == "save-as":
                document["path"], document["modified"] = args.output, False
                self.saved[args.output] = copy.deepcopy(document)
            return {
                "ok": True,
                "document": self.descriptor(document, session),
                "file_verification": {"minimum_size_valid": True},
            }
        if action == "sketch" and subcommand == "inspect":
            profile = document["profiles"][args.sketch_id]
            editing = self.defect == "editing" and self.rejected
            if self.defect == "editing-unknown" and self.rejected:
                editing = None
            return {
                "ok": True,
                "document": descriptor,
                "editing": editing,
                "geometry_complete": True,
                "profile_segment_count": 1,
                "sketch": {"absorbed": profile["absorbed"], "owner": {"name": "Cut1"}},
                "segments": [
                    {
                        "geometry": {
                            "complete_circle": True,
                            "radius_mm": profile["radius"],
                        }
                    }
                ],
            }
        if action == "sketch":
            if self.rejected and self.defect == "post-rejection-sketch":
                return self.failure("SketchCreationFailed")
            self.serial += 1
            profile = {
                "absorbed": False,
                "radius": getattr(args, "radius_mm", 0),
                "x": args.center_x_mm,
                "y": args.center_y_mm,
                "width": getattr(args, "width_mm", 0),
                "height": getattr(args, "height_mm", 0),
            }
            sketch_id = f"s-{self.serial:06x}"
            document["profiles"][sketch_id] = profile
            document["stamp"] += 1
            document["modified"] = True
            result = {
                "ok": True,
                "document": self.descriptor(document, session),
                "plane": args.plane,
                "editing": False,
                "coordinate_system": "sketch-local",
                "sketch": {"sketch_id": sketch_id},
                "geometry_verification": {
                    "passed": True,
                    "profile_segment_count": 4 if subcommand == "rectangle" else 1,
                    "complete_circle": True,
                    "actual_radius_mm": profile["radius"],
                    "actual_center_mm": {"x": profile["x"], "y": profile["y"], "z": 0},
                },
            }
            if self.rejected and self.defect == "lost-foreground":
                result["document"]["active"] = True
            return result
        if action == "feature":
            profile = document["profiles"][args.sketch_id]
            if profile["absorbed"]:
                return self.failure("SketchUnavailable")
            if subcommand == "cut-extrude" and profile["x"] == 1000:
                self.rejected = True
                result = self.failure("CutExtrusionFailed")
                if self.defect == "cleanup-warning":
                    result["warnings"] = [{"code": "sketch-cleanup-failed"}]
                if self.defect == "wrong-rejection":
                    result["error"]["type"] = "HostDisconnected"
                return result
            profile["absorbed"] = True
            document["stamp"] += 1
            document["modified"] = True
            removed = math.pi * profile["radius"] ** 2 * args.depth_mm
            if subcommand == "cut-extrude":
                document["volume"] -= removed
                document["area"] += 128 * math.pi
            else:
                document["count"] += 1
                document["volume"] += (
                    removed
                    if profile["radius"]
                    else profile["width"] * profile["height"] * args.depth_mm
                )
                document["area"] += 16000
            return {
                "ok": True,
                "document": self.descriptor(document, session),
                "feature": {"name": "Cut1"},
                "bodies": {
                    "count": document["count"],
                    "items": [
                        {
                            "approximate_bounding_box": {
                                "size_mm": {"x": 100, "y": 50, "z": 20}
                            }
                        }
                    ],
                },
                "geometry_verification": {
                    "passed": True,
                    "actual_reverse": args.reverse,
                    "actual_merge": getattr(args, "merge", True),
                    "actual_depth_mm": args.depth_mm,
                    "volume_removed_mm3": removed,
                },
                "measurement_after": {"surface_area_mm2": document["area"]},
            }
        raise AssertionError(f"unhandled generated CLI call: {args}")


class ModelingSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "evidence with spaces"
        self.fake = FakeCLI(self.directory)
        self.arguments = [
            "--output-dir",
            str(self.directory),
            "--host-output-dir",
            "C:\\evidence with spaces",
        ]

    def run_gate(self, *, samples=False):
        arguments = self.arguments + (
            [
                "--sample-part",
                "C:\\samples\\Paper.SLDPRT",
                "--sample-assembly",
                "C:\\samples\\Mold.SLDASM",
            ]
            if samples
            else []
        )
        with (
            mock.patch.object(gate.subprocess, "run", side_effect=self.fake.run),
            mock.patch("sys.stdout", new=io.StringIO()),
        ):
            gate.main(arguments)

    def record(self):
        return json.loads(
            (self.directory / "modeling.json").read_text(encoding="utf-8")
        )

    def test_complete_shared_sequence_parses_real_cli_and_keeps_one_host(self):
        self.run_gate(samples=True)
        record = self.record()
        self.assertTrue(record["success"])
        self.assertEqual(
            record["cases"],
            [
                "native-model",
                "reverse-cut",
                "sample-exports",
                "rejected-cut-then-sketch",
            ],
        )
        self.assertEqual(
            record["host"]["process_id"], record["host_after"]["process_id"]
        )
        self.assertEqual(record["cleanup_errors"], [])
        self.assertEqual(self.fake.documents, {})
        calls = self.fake.calls
        failed = next(
            i
            for i, args in enumerate(calls)
            if args.command == "feature"
            and args.feature_command == "cut-extrude"
            and record["events"][i]["result"].get("error", {}).get("type")
            == "CutExtrusionFailed"
        )
        self.assertEqual(calls[failed + 1].document_command, "inspect")
        self.assertEqual(calls[failed + 2].sketch_command, "inspect")
        self.assertTrue(
            any(
                args.command == "sketch" and args.sketch_command == "circle"
                for args in calls[failed + 3 :]
            )
        )
        self.assertFalse(
            any(
                args.command == "daemon" and args.daemon_command != "status"
                for args in calls
            )
        )
        self.assertTrue(
            all(event["state"] == "completed" for event in record["events"])
        )
        self.assertTrue(
            all(event["stderr"] == "native stderr\n" for event in record["events"])
        )

    def test_native_failure_state_and_host_defects_fail_without_restart(self):
        for defect in (
            "cleanup-warning",
            "wrong-rejection",
            "editing",
            "editing-unknown",
            "rejected-volume",
            "post-rejection-sketch",
            "lost-foreground",
            "host-replaced",
            "null-stamp",
            "overwrite-existing",
            "close-no-op",
        ):
            with (
                self.subTest(defect=defect),
                tempfile.TemporaryDirectory() as temporary,
            ):
                self.directory = Path(temporary)
                self.fake = FakeCLI(self.directory)
                self.fake.defect = defect
                self.arguments = [
                    "--output-dir",
                    temporary,
                    "--host-output-dir",
                    "C:\\tests",
                ]
                with self.assertRaises(RuntimeError):
                    self.run_gate()
                self.assertFalse(self.record()["success"])
                self.assertEqual(self.fake.documents, {})
                self.assertFalse(
                    any(
                        args.command == "daemon" and args.daemon_command != "status"
                        for args in self.fake.calls
                    )
                )

    def test_existing_evidence_refused_before_any_cli_call(self):
        self.directory.mkdir()
        target = self.directory / "modeling.json"
        target.write_text('{"previous":true}', encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.run_gate()
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(target.read_text(), '{"previous":true}')

    def test_partial_sample_configuration_refused_before_any_cli_call(self):
        with self.assertRaises(SystemExit), mock.patch("sys.stderr", new=io.StringIO()):
            gate.main(self.arguments + ["--sample-part", "C:\\sample.SLDPRT"])
        self.assertEqual(self.fake.calls, [])

    def test_posix_output_needs_explicit_host_path(self):
        # Simulate the local POSIX namespace even on Windows runners. The real
        # Windows output path is valid without an override and must not cause
        # this offline unit test to contact an actual daemon.
        local_path = mock.Mock()
        local_path.expanduser.return_value.resolve.return_value = PurePosixPath(
            "/workspace/proof"
        )
        with (
            mock.patch.object(gate, "Path", return_value=local_path),
            mock.patch.object(gate.subprocess, "run") as command,
            self.assertRaises(gate.argparse.ArgumentTypeError),
        ):
            gate.main(["--output-dir", "/workspace/proof"])
        local_path.mkdir.assert_not_called()
        command.assert_not_called()
        self.assertFalse(self.directory.exists())


if __name__ == "__main__":
    unittest.main()
