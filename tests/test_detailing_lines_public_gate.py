"""Exercise the installed gate policy against a fake CLI, never a native host."""

import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from swcli.document_detailing_lines import DETAILING_LINE_FIELDS
from tests import test_detailing_public_gate as legacy

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("detailing_lines_public", ROOT / "scripts/ci/verify-detailing-lines-public.py")
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)


class LineDefaultsCLI(legacy.DetailingCLI):
    initial_detailing = {**public.GUARDS, **dict(zip(DETAILING_LINE_FIELDS, (False, True)))}
    read_command = "detailing-line-options"
    supports_write_enabled = True

    def dispatch(self, args):
        if (args.command == "document" and args.document_command == "inspect"
                and args.document_id not in self.documents):
            return self.failure("DocumentNotFound")
        result = super().dispatch(args)
        if args.command == "daemon":
            result["result"]["host"]["revision"] = "33.5.0"
        return result


class PublicDrawingLineTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        output = Path(tmp.name)
        path = output / "trace.jsonl"
        path.write_text("")
        self.fake = LineDefaultsCLI(output, path)
        self.gate = public.PublicGate(directory=output, host_directory=str(output), endpoint="127.0.0.1:1")
        self.gate.record["writes"] = []
        self.gate.capture_process = mock.Mock()
        self.trace = public.legacy.DetailingTrace(path, snapshot_width=4)

    def run_plan(self):
        with mock.patch.object(public.support.modeling.subprocess, "run", side_effect=self.fake.run), \
                mock.patch.object(public, "contracts") as contracts, mock.patch("sys.stdout", new=io.StringIO()):
            try:
                public.run(self.gate, self.trace, "C:/fixture/gb.drwdot")
            finally:
                self.gate.cleanup()
        return contracts

    def test_eight_directional_changes_save_and_reopen_through_installed_gate(self):
        contracts = self.run_plan()
        contracts.assert_called_once()
        self.assertEqual(self.fake.setter_attempts, 8)
        self.assertEqual(len(self.gate.record["writes"]), 8)
        used = set()
        for row in self.gate.record["writes"]:
            for access in ("readonly", "writable"):
                self.assertEqual(row[access + "_read"]["options"], row["after"])
                identity = row[access + "_read"]["document"]["document_id"]
                self.assertNotIn(identity, used)
                used.add(identity)
            self.assertEqual(row["save"]["sha256"], public.digest(row["save"]["path"]))
            self.assertFalse(row["readonly_refusal"]["mutation"]["attempted"])
            self.assertFalse(row["noop"]["changed"])
        self.assertEqual([row["getters"] for row in self.trace.proofs if row["setters"]], [12] * 8)
        self.assertEqual(self.fake.documents, {})

    def test_missing_trace_and_failed_reopen_stop_at_first_write(self):
        for fault in ("missing-trace", "persistence-lost"):
            with self.subTest(fault=fault):
                self.setUp()
                self.fake.detailing_defect = fault
                with self.assertRaises(RuntimeError):
                    self.run_plan()
                self.assertEqual(self.fake.setter_attempts, 1)
                self.assertEqual(self.fake.documents, {})


if __name__ == "__main__":
    unittest.main()
