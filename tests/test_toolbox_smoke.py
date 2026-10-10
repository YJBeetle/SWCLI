"""Portable Toolbox gate contracts, not proof of native standard-part usage."""

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from swcli.cli import build_parser

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci/verify-toolbox.py"
spec = importlib.util.spec_from_file_location("toolbox_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ToolboxTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "data with spaces"
        self.xml = ("<ToolboxStandards><Standard><Name>GB</Name><Source>gb.zip</Source>"
                    "<Install>Yes</Install></Standard><Standard><Name>ISO</Name>"
                    "<Source>iso.zip</Source><Install>No</Install></Standard></ToolboxStandards>")
        for relative, content in (("ToolboxStandards.xml", self.xml.encode()),
                                  ("browser/ToolboxFiles.index", b"binary index"),
                                  ("lang/english/swbrowser.sldedb", b"database"),
                                  ("browser/GB/bolts/bolt.SLDPRT", b"native sample")):
            path = self.data / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    def args(self, **overrides):
        return argparse.Namespace(**{
            "output_dir": self.root / "evidence", "data_dir": self.data,
            "host_data_dir": r"Q:\Library with spaces", "wine_prefix": None,
            "require_toolbox": True, "inventory_only": False,
            "cli_command": None, "endpoint": "127.0.0.1:18495",
            "request_timeout": 120, **overrides})

    def test_inventory_checks_enabled_standards_without_assuming_year_or_count(self):
        result = gate.inventory(self.data)
        self.assertEqual(result["model_count"], 1)
        self.assertEqual(result["enabled_standards"], [{"name": "GB", "source": "gb.zip",
            "model_count": 1, "representative": "browser/GB/bolts/bolt.SLDPRT"}])
        self.assertGreater(result["index_bytes"], 0)

    def test_each_enabled_standard_requires_its_own_models(self):
        (self.data / "ToolboxStandards.xml").write_text(self.xml.replace("<Install>No", "<Install>Yes"))
        with self.assertRaisesRegex(RuntimeError, "ISO"):
            gate.inventory(self.data)

    def test_missing_empty_index_database_or_model_fails(self):
        for relative in ("browser/ToolboxFiles.index", "lang/english/swbrowser.sldedb",
                         "browser/GB/bolts/bolt.SLDPRT"):
            path = self.data / relative
            original = path.read_bytes()
            for state in ("missing", "empty"):
                with self.subTest(relative=relative, state=state):
                    path.unlink()
                    if state == "empty":
                        path.write_bytes(b"")
                    with self.assertRaises(RuntimeError):
                        gate.inventory(self.data)
                    path.write_bytes(original)

    def test_xml_rejects_unsafe_duplicate_disabled_and_unbounded_input(self):
        path = self.data / "ToolboxStandards.xml"
        for xml in ("<unrelated/>", "<ToolboxStandards>",
                    self.xml.replace("GB", "../GB"), self.xml.replace("gb.zip", "..\\gb.zip"),
                    self.xml.replace("Yes", "Maybe"), self.xml.replace("Yes", "No"),
                    self.xml.replace("<Name>ISO", "<Name>GB").replace("<Install>No", "<Install>Yes"),
                    '<!DOCTYPE ToolboxStandards [<!ENTITY x "GB">]>' + self.xml):
            with self.subTest(xml=xml[:80]):
                path.write_text(xml)
                with self.assertRaises((RuntimeError, gate.ET.ParseError)):
                    gate.inventory(self.data)
        path.write_bytes(('<!DOCTYPE ToolboxStandards>' + self.xml).encode("utf-16"))
        with self.assertRaisesRegex(RuntimeError, "DTD"):
            gate.inventory(self.data)
        path.write_text(self.xml)
        with patch.object(gate, "MAX_XML_BYTES", 10), self.assertRaisesRegex(RuntimeError, "size"):
            gate.inventory(self.data)
        with patch.object(gate, "MAX_FILES", 1), self.assertRaisesRegex(RuntimeError, "bound"):
            gate.inventory(self.data)

    def test_symlinked_model_or_standard_is_not_counted_as_deployment(self):
        model = self.data / "browser/GB/bolts/bolt.SLDPRT"
        original = model.read_bytes()
        outside = self.root / "outside.SLDPRT"
        outside.write_bytes(original)
        model.unlink()
        try:
            model.symlink_to(outside)
        except OSError:
            self.skipTest("Symlink permission unavailable")
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            gate.inventory(self.data)
        model.unlink()
        model.write_bytes(original)
        (self.data / "browser/GB/alias").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            gate.inventory(self.data)

    def test_wine_location_filters_unrelated_values_and_preserves_unicode(self):
        text = r'''[Software\\SolidWorks\\SOLIDWORKS 2027\\General] 123
"Toolbox Data Location"="D:\\标准件库"
[Software\\Unrelated]
"Toolbox Data Location"="C:\\not-toolbox"
"License"="private-not-returned"
'''
        self.assertEqual(gate.wine_locations(text), {"D:\\标准件库"})

    def test_actual_wine_drive_mapping_and_user_precedence_no_z_assumption(self):
        prefix = self.root / "prefix"
        (prefix / "dosdevices").mkdir(parents=True)
        try:
            (prefix / "dosdevices/q:").symlink_to(self.root, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink permission unavailable")
        text = '[Software\\\\SolidWorks\\\\SOLIDWORKS 2028\\\\General]\n"Toolbox Data Location"="Q:\\\\data with spaces"\n'
        (prefix / "user.reg").write_text(text)
        (prefix / "system.reg").write_text(text.replace("Q:", "D:"))
        self.assertEqual(gate.configured_location(prefix), r"Q:\data with spaces")
        self.assertEqual(gate.local_location(gate.configured_location(prefix), prefix), self.data.resolve())
        (prefix / "user.reg").write_text(text + text.replace("Q:", "D:"))
        with self.assertRaisesRegex(RuntimeError, "Ambiguous"):
            gate.configured_location(prefix)
        with self.assertRaisesRegex(RuntimeError, "mapping"):
            gate.local_location(r"R:\unmapped", prefix)
        with self.assertRaisesRegex(RuntimeError, "UNC"):
            gate.local_location(r"\\server\share\library", prefix)

    def test_inventory_only_never_launches_cli_and_is_not_native_proof(self):
        instance = gate.Gate(self.args(inventory_only=True))
        with patch.object(gate.subprocess, "run", side_effect=AssertionError("No CLI")):
            self.assertEqual(instance.run(), 0)
        self.assertEqual(instance.record["outcome"], "passed")
        self.assertEqual(instance.record["native_test"], "not-run")
        self.assertIsNone(instance.record["updater_exit_code"])

    def test_optional_missing_config_skips_but_required_and_corrupt_fail(self):
        for required in (False, True):
            args = self.args(data_dir=None, host_data_dir=None, require_toolbox=required,
                             output_dir=self.root / str(required))
            with patch.object(gate, "configured_location", return_value=None):
                instance = gate.Gate(args)
                self.assertEqual(instance.run(), 1 if required else 0)
                self.assertEqual(instance.record["completed"], False)
                self.assertEqual(instance.record["outcome"], "failed" if required else "skipped")
        (self.data / "browser/ToolboxFiles.index").unlink()
        instance = gate.Gate(self.args(require_toolbox=False))
        self.assertEqual(instance.run(), 1)

    def test_existing_evidence_is_never_overwritten(self):
        instance = gate.Gate(self.args(inventory_only=True))
        instance.run()
        original = instance.path.read_bytes()
        with self.assertRaises(FileExistsError):
            gate.Gate(self.args())
        self.assertEqual(instance.path.read_bytes(), original)

    def test_checkpoint_failure_preserves_native_error_and_still_closes_owned_part(self):
        instance = gate.Gate(self.args())
        fake = FakeCLI("diagnose", self.data)
        checkpoint = instance.checkpoint
        def write():
            events = instance.record["events"]
            if events and any(event["state"] == "failed" for event in events):
                raise OSError("ENOSPC fixture")
            checkpoint()
        with patch.object(gate.subprocess, "run", side_effect=fake.run), \
                patch.object(instance, "checkpoint", side_effect=write):
            self.assertEqual(instance.run(), 1)
        self.assertIn("NativeFailure", instance.record["error"]["message"])
        self.assertTrue(instance.record["evidence_errors"])
        self.assertEqual(instance.record["cleanup_errors"], [])
        self.assertFalse(fake.open)
        self.assertEqual(sum(getattr(args, "document_command", None) == "close" for args in fake.calls), 1)

    def test_successful_inventory_cannot_pass_if_final_evidence_write_fails(self):
        instance = gate.Gate(self.args(inventory_only=True))
        checkpoint = instance.checkpoint
        def write():
            if instance.record["completed"]:
                raise OSError("final write fixture")
            checkpoint()
        with patch.object(instance, "checkpoint", side_effect=write):
            self.assertEqual(instance.run(), 1)
        self.assertFalse(instance.record["completed"])
        self.assertEqual(instance.record["error"]["type"], "EvidenceWriteFailed")

    def test_read_only_cli_sequence_preserves_sources_and_metadata_evidence(self):
        instance, fake = self.run_native_fake()
        self.assertEqual(instance.record["native_test"], "passed")
        self.assertEqual(instance.record["sample"]["sha256_before"], instance.record["sample"]["sha256_after"])
        self.assertEqual([args.document_command for args in fake.calls if args.command == "document"],
                         ["list", "open", "diagnose", "measure", "close", "list"])
        self.assertTrue(next(args for args in fake.calls if getattr(args, "document_command", None) == "open").read_only)
        self.assertTrue(all("request_id" in event["result"] for event in instance.record["events"]
                            if "ok" in event["result"]))
        self.assertEqual((self.data / "browser/GB/bolts/bolt.SLDPRT").read_bytes(), b"native sample")

    def run_native_fake(self, defect=None):
        instance = gate.Gate(self.args())
        fake = FakeCLI(defect, self.data)
        with patch.object(gate.subprocess, "run", side_effect=fake.run):
            status = instance.run()
        self.assertEqual(status, 1 if defect else 0, instance.record.get("error"))
        return instance, fake

    def test_refusals_keep_first_error_close_only_owned_part_and_do_not_retry(self):
        for defect in ("diagnose", "needs-rebuild", "zero-body", "changed-stamp", "unknown-field",
                       "host-replaced", "host-disconnected", "already-open", "alias-existing",
                       "close-failed", "source-change"):
            with self.subTest(defect=defect):
                self.root.joinpath("evidence").mkdir(exist_ok=True)
                self.root.joinpath("evidence/toolbox.json").unlink(missing_ok=True)
                model = self.data / "browser/GB/bolts/bolt.SLDPRT"
                model.write_bytes(b"native sample")
                instance, fake = self.run_native_fake(defect)
                self.assertFalse(instance.record["completed"])
                self.assertNotEqual(instance.record["native_test"], "passed")
                operations = [args.document_command for args in fake.calls if args.command == "document"]
                self.assertLessEqual(operations.count("open"), 1)
                self.assertLessEqual(operations.count("close"), 1)
                if defect in ("already-open", "alias-existing"):
                    self.assertNotIn("close", operations)
                if defect == "diagnose":
                    self.assertIn("NativeFailure", instance.record["error"]["message"])
                    self.assertIn("close", operations)


class FakeCLI:
    def __init__(self, defect, data):
        self.parser = build_parser()
        self.calls = []
        self.defect = defect
        self.data = data
        self.open = False
        self.health_calls = 0

    @staticmethod
    def document():
        return {"title": "bolt.SLDPRT", "path": r"Q:\Library with spaces\browser\GB\bolts\bolt.SLDPRT",
                "type": 1, "modified": False, "update_stamp": 10,
                "document_id": "d-123456", "active": True, "current": True}

    def run(self, command, **kwargs):
        args = self.parser.parse_args(command[command.index("--endpoint"):])
        self.calls.append(args)
        if args.command == "daemon":
            self.health_calls += 1
            payload = {"success": True, "result": {"host_connected": self.defect != "host-disconnected",
                "recovery_required": False, "host": {"process_id": 124 if self.defect == "host-replaced"
                                                          and self.health_calls > 1 else 123}}}
        else:
            action = args.document_command
            payload = {"ok": True, "document": self.document(),
                       "action": "document." + action,
                       "request_id": "unique-" + str(len(self.calls)), "replayed": False}
            if action == "list":
                documents = [self.document()] if self.open or self.defect in ("already-open", "alias-existing") else []
                if self.defect == "alias-existing":
                    documents[0]["path"] = r"Q:\LIBRAR~1\browser\GB\bolts\bolt.SLDPRT"
                payload.pop("document")
                payload.update(documents=documents, count=len(documents),
                               session_id=args.session, current_document_id="d-123456" if documents else None)
            elif action == "open":
                self.open = True
                payload.update(path=args.path, read_only=True, configuration=None, api_errors=0, api_warnings=0)
                if self.defect == "unknown-field":
                    payload["unexpected"] = True
            elif action == "diagnose":
                payload.update(needs_rebuild=1 if self.defect == "needs-rebuild" else 0,
                    diagnostics={"healthy": True, "issues": [], "issue_count": 0,
                                 "scanned_feature_count": 5, "truncated": False, "limit": 500})
                if self.defect == "diagnose":
                    payload = {"ok": False, "error": {"type": "NativeFailure", "message": "first error"}}
            elif action == "measure":
                metrics = {"solid_body_count": 0 if self.defect == "zero-body" else 1,
                           "volume_mm3": 100, "surface_area_mm2": 200, "centroid_mm": {"x": 0, "y": 0, "z": 0}}
                payload.update(scope="sum-of-solid-bodies", coordinate_system="part-model",
                               method="native-body-mass-properties", metrics=metrics,
                               bodies=[{"index": 0, **{k: v for k, v in metrics.items() if k != "solid_body_count"}}])
                if self.defect == "changed-stamp":
                    payload["document"]["update_stamp"] = 11
                if self.defect == "source-change":
                    (self.data / "browser/GB/bolts/bolt.SLDPRT").write_bytes(b"changed")
            elif action == "close":
                if self.defect == "close-failed":
                    payload = {"ok": False, "error": {"type": "CloseFailure", "message": "no close"}}
                else:
                    self.open = False
                    payload.update(closed=True, discard=True)
        return subprocess.CompletedProcess(command, 1 if payload.get("ok") is False else 0,
                                           json.dumps(payload).encode(), b"native diagnostic\n")


if __name__ == "__main__":
    unittest.main()
