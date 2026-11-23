"""Portable fixture construction and persistence checks with synthetic handles."""
from hashlib import sha256
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location("font_fixture_test_" + name,
        ROOT / "scripts" / "ci" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call(_name, operation):
    return operation()


class FontFixturePreparationTests(unittest.TestCase):
    def setUp(self):
        self.worker = load("prepare-font-scopes-next-fixture")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name)
        self.template = self.output / "GB.drwdot"
        self.template.write_bytes(b"synthetic template")
        self.enums = {"swTableAnnotation_General": 0}
        self.case = {}
        self.live = {"document": None}

    def test_table_seed_uses_only_two_cells_and_detaches_right_before_font_edits(self):
        inherited = SimpleNamespace(TypeFaceName="Arial", CharHeightInPts=12)
        detached = SimpleNamespace(TypeFaceName="Arial", CharHeightInPts=12)
        dispatch = Mock()
        dispatch.GetIDsOfNames.return_value = 80
        dispatch.Invoke.side_effect = [None, "Fixture inherited", None, "Fixture local"]
        table = SimpleNamespace(Type=0, RowCount=1, ColumnCount=2, _oleobj_=dispatch,
            GetUseDocTextFormat=True, GetCellUseDocTextFormat=Mock(side_effect=[True, False]),
            GetCellTextFormat=Mock(side_effect=[inherited, detached]),
            SetCellTextFormat=Mock(return_value=True))
        make = Mock(return_value=table)
        with patch.dict(sys.modules, {"pythoncom": SimpleNamespace(DISPATCH_PROPERTYPUT=4, DISPATCH_PROPERTYGET=2)}):
            self.worker.seed_table(SimpleNamespace(InsertTableAnnotation2=make), self.enums, call)
        make.assert_called_once_with(False, 0.05, 0.12, 1, "", 1, 2)
        self.assertEqual([entry.args for entry in dispatch.Invoke.call_args_list], [
            (80, 0, 4, False, 0, 0, False, "Fixture inherited"),
            (80, 0, 2, True, 0, 0, False),
            (80, 0, 4, False, 0, 1, False, "Fixture local"),
            (80, 0, 2, True, 0, 1, False),
        ])
        self.assertEqual([entry.args for entry in table.SetCellTextFormat.call_args_list],
                         [(0, 1, False, inherited), (0, 1, False, detached)])
        self.assertEqual((inherited.TypeFaceName, inherited.CharHeightInPts), ("Arial", 12))
        self.assertEqual((detached.TypeFaceName, detached.CharHeightInPts), ("Courier New", 20))

    def test_rejected_right_font_detachment_never_edits_source_format(self):
        font = SimpleNamespace(TypeFaceName="Arial", CharHeightInPts=12)
        table = SimpleNamespace(Type=0, RowCount=1, ColumnCount=2, GetUseDocTextFormat=True,
            GetCellUseDocTextFormat=lambda *_: True, GetCellTextFormat=Mock(return_value=font),
            SetCellTextFormat=Mock(return_value=False))
        with patch.object(self.worker, "cell_text"):
            with self.assertRaisesRegex(RuntimeError, "establish a local right"):
                self.worker.seed_table(SimpleNamespace(InsertTableAnnotation2=lambda *_: table), self.enums, call)
        table.GetCellTextFormat.assert_called_once_with(0, 1)
        table.SetCellTextFormat.assert_called_once_with(0, 1, False, font)
        self.assertEqual((font.TypeFaceName, font.CharHeightInPts), ("Arial", 12))

    def test_manual_dimensions_stage_exact_copy_without_save_or_opening_original(self):
        original = self.output / "manual.SLDDRW"
        original.write_bytes(b"synthetic drawing")
        digest = sha256(original.read_bytes()).hexdigest()
        staged = self.output / "inheritance-source.SLDDRW"
        document = SimpleNamespace(GetPathName=str(staged), IsOpenedReadOnly=True, GetSaveFlag=False, GetTitle="Fixture")
        app = SimpleNamespace(RevisionNumber="33.5.0", GetDocumentCount=0, CloseDoc=Mock())
        receipt = dict(ok=True, api_errors=0, api_warnings=0, read_only=True)
        worker = self.worker
        with patch.object(worker, "open_windows_document_with_handle", return_value=(receipt, document)) as opened, \
                patch.object(worker, "inspect_fixture", return_value={"objects": "mock"}), \
                patch.object(worker, "save_as_native_windows") as saved:
            worker.run_case(app, self.output, self.enums, call, self.case, self.live,
                            scope="dimensions", template=self.template, manual=(original, digest))
        opened.assert_called_once_with(str(staged), app=app, read_only=True)
        saved.assert_not_called()
        app.CloseDoc.assert_called_once_with("Fixture")
        self.assertEqual(staged.read_bytes(), original.read_bytes())
        self.assertEqual(self.case["file_sha256"], digest)
        self.assertTrue(self.case["success"])
        self.assertFalse(self.case["save_verified"])
        self.assertFalse(self.case["inheritance_acceptance"])

    def test_created_fixture_save_receipt_and_reopen_drift_fail_independently(self):
        worker = self.worker
        document = SimpleNamespace(GetType=3, GetPathName="")
        app = SimpleNamespace(RevisionNumber="33.5.0", GetDocumentCount=1, ActiveDoc=document)
        made = dict(ok=True, views=[], template={"path": str(self.template)})
        baseline = dict(native_defaults={"four": "original"}, linked_defaults={"five": "original"})

        warning = 0

        def save(path, **context):
            Path(path).write_bytes(b"synthetic" * 100)
            return dict(ok=True, api_saved=True, save_errors=0, save_warnings=warning,
                        document=dict(modified=False, path=path))

        def changed(app, path, digest, constants, scope, call, case, live, *, generated):
            case["reopened_observation"] = dict(baseline, linked_defaults={"five": "changed"})

        with patch.object(worker, "create_drawing_windows_with_handle", return_value=(made, document)), \
                patch.object(worker, "_same", return_value=True), \
                patch.object(worker.fonts, "_read_fonts", return_value=({}, {}, baseline["native_defaults"])), \
                patch.object(worker, "read_guarded_linked_font_defaults", return_value=baseline["linked_defaults"]), \
                patch.object(worker, "seed_table"), patch.object(worker, "inspect_fixture", return_value=baseline), \
                patch.object(worker, "close"), patch.object(worker, "read_saved", side_effect=changed) as reopen, \
                patch.object(worker, "save_as_native_windows", side_effect=save) as saved:
            with self.assertRaisesRegex(RuntimeError, "preserve full saved baseline"):
                worker.run_case(app, self.output, self.enums, call, self.case, self.live,
                                scope="tables", template=self.template, manual=None)
            saved.assert_called_once()
            reopen.assert_called_once()
            self.assertTrue(self.case["save_verified"])
            self.assertFalse(self.case["success"])
            self.assertEqual(self.case["save"]["document"]["path"], self.case["path"])

            for warning in (None, 1):
                with self.subTest(save_warnings=warning):
                    output = self.output / ("warning-" + str(warning))
                    output.mkdir()
                    case = {}
                    reopen.reset_mock()
                    with self.assertRaisesRegex(RuntimeError, "native fixture save did not produce a clean file"):
                        worker.run_case(app, output, self.enums, call, case, {},
                                        scope="tables", template=self.template, manual=None)
                    reopen.assert_not_called()
                    self.assertFalse(case["save_verified"])

    def test_unexpected_writable_reopen_cannot_qualify_a_fixture(self):
        original = self.output / "manual.SLDDRW"
        original.write_bytes(b"synthetic drawing")
        digest = sha256(original.read_bytes()).hexdigest()
        staged = self.output / "inheritance-source.SLDDRW"
        document = SimpleNamespace(GetPathName=str(staged), IsOpenedReadOnly=False, GetSaveFlag=False)
        app = SimpleNamespace(RevisionNumber="33.5.0")
        receipt = dict(ok=True, api_errors=0, api_warnings=0, read_only=True)
        with patch.object(self.worker, "open_windows_document_with_handle", return_value=(receipt, document)), \
                patch.object(self.worker, "inspect_fixture") as inspected:
            with self.assertRaisesRegex(RuntimeError, "exact clean path"):
                self.worker.run_case(app, self.output, self.enums, call, self.case, self.live,
                                     scope="dimensions", template=self.template, manual=(original, digest))
        inspected.assert_not_called()
        self.assertIs(self.live["document"], document)
        self.assertFalse(self.case["success"])
        self.assertEqual(sha256(original.read_bytes()).hexdigest(), digest)

    def test_watchdog_routes_fixture_stage_without_widening_legacy_profiles(self):
        runner = load("run-font-scopes-calibration")
        options = dict(profile="next-fixture", scope="tables", swconst=self.output / "swconst.tlb",
                       drawing_template=self.template)
        command = runner.worker_command(SimpleNamespace(**options), self.output)
        self.assertTrue(command[2].endswith("prepare-font-scopes-next-fixture.py"))
        self.assertEqual(command[-2:], ["--scope", "tables"])
        options["scope"] = "dimensions"
        with self.assertRaisesRegex(ValueError, "manually generated"):
            runner.worker_command(SimpleNamespace(**options), self.output)
        options.update(inheritance_drawing=self.output / "manual.SLDDRW", inheritance_sha256="a" * 64)
        command = runner.worker_command(SimpleNamespace(**options), self.output)
        self.assertEqual(command[-2:], ["--inheritance-sha256", "a" * 64])
        options["profile"] = "inheritance-seed"
        with self.assertRaises(ValueError):
            runner.worker_command(SimpleNamespace(**options), self.output)
