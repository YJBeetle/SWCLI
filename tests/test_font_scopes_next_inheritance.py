"""Portable tests for the bounded drawing inheritance witness."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import test_document_font_scopes as fixture

Format = fixture.Format

ROOT = Path(__file__).resolve().parents[1]


def load(relative):
    spec = importlib.util.spec_from_file_location("font_next_test_" + Path(relative).stem, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


witness = load("scripts/ci/gate_support/font_inheritance.py")


class FontDrawingWitnessTests(unittest.TestCase):
    def setUp(self):
        self.font = fixture.FontScopeTests()
        self.font.setUp()
        self.addCleanup(self.font.doCleanups)
        self.base = self.font.native["dimensions"]
        self.local = dict(self.base, TypeFaceName="Courier New", IsHeightSpecifiedInPts=True, CharHeightInPts=20)
        self.changed = dict(self.base, TypeFaceName="Times New Roman", CharHeight=0.005,
                            Bold=True, Italic=True, Underline=True, Strikeout=True)

    def dimension(self, name, use_doc, font, next_annotation=None):
        return SimpleNamespace(GetType=4, GetName=name, GetTextFormatCount=1,
                               GetUseDocTextFormat=Mock(return_value=use_doc),
                               GetTextFormat=Mock(return_value=Format(font)), GetNext3=next_annotation)

    def test_dimension_observes_explicit_flags_and_all_font_changes(self):
        local = self.dimension("D2", False, self.local)
        baseline = witness.collect_dimensions(
            SimpleNamespace(GetFirstAnnotation3=self.dimension("D1", True, self.base, local)), 4)
        inherited = self.dimension("D1", True, self.changed, local)
        observed = witness.collect_dimensions(SimpleNamespace(GetFirstAnnotation3=inherited), 4)
        witness.verify_observation("dimensions", observed, observed["inherited"]["font"], baseline)
        self.assertEqual(len(observed["local"]["native_font"]), 17)
        inherited.GetUseDocTextFormat.assert_called_once_with(0)
        inherited.GetTextFormat.assert_called_once_with(0)

    def test_equal_default_without_observed_change_and_changed_local_raw_fail(self):
        local = self.dimension("D2", False, self.local)
        baseline = witness.collect_dimensions(
            SimpleNamespace(GetFirstAnnotation3=self.dimension("D1", True, self.base, local)), 4)
        with self.assertRaisesRegex(RuntimeError, "five face/style changes"):
            witness.verify_observation("dimensions", baseline, baseline["inherited"]["font"], baseline)
        changed_local = self.dimension("D2", False, dict(self.local, WidthFactor=1.2))
        changed = witness.collect_dimensions(SimpleNamespace(
            GetFirstAnnotation3=self.dimension("D1", True, self.changed, changed_local)), 4)
        with self.assertRaisesRegex(RuntimeError, "local native"):
            witness.verify_observation("dimensions", changed, changed["inherited"]["font"], baseline)

    def test_general_reads_whole_table_and_each_cells_actual_flag(self):
        annotation = SimpleNamespace(GetName="General1")
        table = SimpleNamespace(Type=0, RowCount=1, ColumnCount=2, GetNext=None, GetAnnotation=annotation,
            GetUseDocTextFormat=True, GetTextFormat=lambda: Format(self.base),
            GetCellUseDocTextFormat=Mock(side_effect=[True, False]),
            GetCellTextFormat=Mock(side_effect=[Format(self.base), Format(self.local)]))
        baseline = witness.collect_table(SimpleNamespace(GetFirstTableAnnotation2=table), 0)
        table.GetTextFormat = lambda: Format(self.changed)
        table.GetCellUseDocTextFormat.side_effect = [True, False]
        table.GetCellTextFormat.side_effect = [Format(self.changed), Format(self.local)]
        observed = witness.collect_table(SimpleNamespace(GetFirstTableAnnotation2=table), 0)
        witness.verify_observation("tables", observed, observed["table"]["font"], baseline)
        self.assertEqual([row.args for row in table.GetCellTextFormat.call_args_list], [(0, 0), (0, 1)] * 2)
        broken = deepcopy(observed)
        broken["table"]["use_document_font"] = False
        with self.assertRaisesRegex(RuntimeError, "document font flag"):
            witness.verify_observation("tables", broken, observed["table"]["font"], baseline)
        table.Type = 2
        with self.assertRaisesRegex(RuntimeError, "General table"):
            witness.collect_table(SimpleNamespace(GetFirstTableAnnotation2=table), 0)

    def test_hash_mismatch_and_existing_staging_path_fail_before_native(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "fixture.SLDDRW"
            source.write_bytes(b"owned fixture")
            digest = sha256(source.read_bytes()).hexdigest()
            witness.validate_drawing_input("tables", source, digest)
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                witness.validate_drawing_input("tables", source, "1" * 64)
            staged = witness.stage_drawing(source, digest, root)
            self.assertEqual(staged.read_bytes(), source.read_bytes())
            with self.assertRaises(FileExistsError):
                witness.stage_drawing(source, digest, root)

    def test_worker_preflights_digest_and_sends_fixture_only_to_drawing_case(self):
        worker = load("scripts/ci/verify-font-scopes-calibration.py")
        runner = load("scripts/ci/run-font-scopes-calibration.py")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "fixture.SLDDRW"
            source.write_bytes(b"owned fixture")
            digest = sha256(source.read_bytes()).hexdigest()
            library, template = root / "swconst.tlb", root / "GB.drwdot"
            library.touch()
            template.touch()
            args = SimpleNamespace(profile="internal", scope="dimensions", swconst=library,
                drawing_template=template, inheritance_drawing=source, inheritance_sha256=digest)
            (root / "out").mkdir()
            command = runner.worker_command(args, root / "out")
            self.assertEqual(command[-4:], ["--inheritance-drawing", str(source.resolve()), "--inheritance-sha256", digest])
            with patch.object(worker.harness, "run", return_value=0) as run, \
                    patch.object(worker.harness, "read_constants"), \
                    patch.object(worker.adapter, "_native_windows_runtime", return_value=True), \
                    patch.object(worker, "calibrate_case") as case:
                with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                    worker.main(command[3:-1] + ["0" * 64])
                run.assert_not_called()
                self.assertEqual(worker.main(command[3:]), 0)
                app = SimpleNamespace(RevisionNumber="33.5.0")
                for kind, expected in (("part", None), ("drawing", (source.resolve(), digest))):
                    run.call_args.kwargs["case_runner"](app, root, {}, profile_kind=kind)
                    self.assertEqual(case.call_args.kwargs["inheritance_input"], expected)
