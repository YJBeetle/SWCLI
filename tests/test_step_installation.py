"""Offline STEP type-library provenance and adapter wiring."""
import hashlib
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from swcli.hosts import windows_step_export as step, windows_step_periodic as periodic
from test_step_export_options import CONSTANTS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'ci'))
from gate_support.step_periodic_driver import DriverFailure
from gate_support.step_periodic_native import NativeAPI


class StepInstallationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.ci = self.create_installation('Program Files/SOLIDWORKS')
        self.vm = self.create_installation('Program Files/SOLIDWORKS Corp/SOLIDWORKS')

    def create_installation(self, path):
        folder = self.root / path
        folder.mkdir(parents=True)
        for name in ('SLDWORKS.exe', 'swconst.tlb', 'sldworks.tlb'):
            (folder / name).write_bytes(name.encode())
        return folder

    def test_both_layouts_and_both_executable_path_shapes(self):
        for directory in (self.ci, self.vm):
            for value in (str(directory), str(directory / 'SLDWORKS.exe')):
                with self.subTest(value=value):
                    app = SimpleNamespace(GetExecutablePath=lambda: value)
                    self.assertEqual(step.resolve_step_swconst(app), directory / 'swconst.tlb')

    def test_incomplete_or_relative_host_refuses_without_falling_back(self):
        (self.vm / 'swconst.tlb').unlink()
        for value in ('relative/SOLIDWORKS', str(self.vm), str(self.ci / 'Other.exe'), None):
            with self.subTest(value=value), self.assertRaises(step.StepExportError) as caught:
                step.resolve_step_swconst(SimpleNamespace(GetExecutablePath=value))
            self.assertEqual(caught.exception.code, 'StepTypeLibraryUnavailable')

    @unittest.skipIf(sys.platform == 'win32', 'creating Windows symlinks can require privileges')
    def test_redirected_type_library_refused(self):
        library = self.vm / 'swconst.tlb'
        library.unlink()
        library.symlink_to(self.ci / 'swconst.tlb')
        with self.assertRaises(step.StepExportError):
            step.resolve_step_swconst(SimpleNamespace(GetExecutablePath=str(self.vm)))

    def test_only_explicit_periodic_preferences_resolve_the_host_library(self):
        document = SimpleNamespace(SketchManager=SimpleNamespace(ActiveSketch=None))
        app = SimpleNamespace(
            GetExecutablePath=str(self.vm), Visible=False, RevisionNumber='33.5.0', ActiveDoc=None, GetCurrentLanguage='chinese-simplified',
            GetUserPreferenceIntegerValue=lambda key: {999:203,777:0}[key],
            GetUserPreferenceToggle=lambda key: False,
            SetUserPreferenceIntegerValue=Mock(),
            SetUserPreferenceToggle=Mock(),
        )
        with patch.object(step, 'read_step_constants', return_value=CONSTANTS) as integers, \
             patch.object(periodic, 'read_periodic_constant', return_value=555) as toggle, \
             patch.object(step, 'resolve_step_swconst', wraps=step.resolve_step_swconst) as resolved, \
             patch.object(step, '_native_windows_runtime', return_value=True), \
             patch.object(step, '_require_writable'), \
             patch.object(step, '_state', return_value=(1, 0, False, 'Default')), \
             patch.object(step, '_verify_metadata_state'):
            with step.step_host_scope(app, isolated=True):
                with step.step_preferences(app, document, 'ap203', 'solid-surface', {}):
                    pass
                integers.assert_called_once_with()
                resolved.assert_not_called()
                toggle.assert_not_called()
                with self.assertRaises(step.StepExportError) as caught:
                    with step.step_preferences(app, document, 'ap203', 'solid-surface', {},
                                               split_periodic_faces=False):
                        self.fail('Chinese periodic write reached preferences')
                self.assertEqual(caught.exception.code, 'StepSplitLanguageUnsupported')
                resolved.assert_not_called()
                toggle.assert_not_called()

                app.GetCurrentLanguage = 'english'
                with step.step_preferences(app, document, 'ap203', 'solid-surface', {},
                                           split_periodic_faces=False):
                    pass
            resolved.assert_called_once_with(app)
            self.assertEqual(integers.call_count, 2)
            integers.assert_called_with(self.vm / 'swconst.tlb')
            toggle.assert_called_once_with(self.vm / 'swconst.tlb')

    def native_api(self):
        api = NativeAPI.__new__(NativeAPI)
        api.step = step
        api.recorder = SimpleNamespace(report={})
        api.fingerprints = {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (self.vm / 'swconst.tlb', self.vm / 'sldworks.tlb')
        }
        return api

    def test_driver_rejects_same_bytes_from_another_installation(self):
        api = self.native_api()
        app = SimpleNamespace(GetExecutablePath=str(self.ci))
        with self.assertRaisesRegex(DriverFailure, 'path differs'):
            api.verify_installation(app, self.vm / 'swconst.tlb')
        self.assertEqual(api.recorder.report['host_installation']['host_swconst_path'],
                         str(self.ci / 'swconst.tlb'))

    def test_driver_verifies_both_inspected_files_and_rejects_drift(self):
        api = self.native_api()
        app = SimpleNamespace(GetExecutablePath=str(self.vm))
        self.assertEqual(api.verify_installation(app, self.vm/'swconst.tlb'), self.vm/'swconst.tlb')
        self.assertTrue(api.recorder.report['host_installation']['verified'])
        for name in ('swconst.tlb', 'sldworks.tlb'):
            path = self.vm/name
            previous = path.read_bytes()
            path.write_bytes(b'changed')
            with self.subTest(name=name), self.assertRaisesRegex(DriverFailure, 'changed after preflight'):
                api.verify_installation(app, self.vm/'swconst.tlb')
            self.assertNotIn('verified', api.recorder.report['host_installation'])
            self.assertEqual(api.recorder.report['source_fingerprint_conflict']['file'], str(path))
            path.write_bytes(previous)

    def test_driver_loads_all_constants_and_interfaces_from_verified_directory(self):
        api = self.native_api()
        api.pythoncom = object()
        api.reader = SimpleNamespace(read_import_constants=Mock(return_value={'import': 1}))
        api.periodic = SimpleNamespace(read_periodic_constant=Mock(return_value=555))
        app = SimpleNamespace(GetExecutablePath=str(self.vm))
        path = api.verify_installation(app, self.vm/'swconst.tlb')
        sibling = self.vm/'sldworks.tlb'
        interface = {'path': str(sibling), 'sha256': api.fingerprints[str(sibling)],
                     'interfaces': {'IImportStepData': 'step', 'IImportIgesData': 'iges'}}
        with patch.object(step, 'read_step_constants', return_value={'export': 2}) as integers, \
             patch('gate_support.step_periodic_native.read_interface_contract',
                   return_value=interface) as imports:
            self.assertEqual(api.read_constants(path), {
                'export': 2, 'import': 1, 'swStepExportSplitPeriodic': 555,
            })
        imports.assert_called_once_with(sibling, api.pythoncom)
        integers.assert_called_once_with(path)
        api.reader.read_import_constants.assert_called_once_with(path)
        api.periodic.read_periodic_constant.assert_called_once_with(path)
        self.assertEqual(api.recorder.report['host_import_interfaces'], interface)
