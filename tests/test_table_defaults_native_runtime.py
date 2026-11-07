"""Strict native-runtime admission before table mutation, with no CAD process."""

import ctypes
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts import windows_document_tables as adapter
from swcli.daemon import operations
from swcli.result_schemas import validate_operation_result
from tests import test_document_tables as fixtures


class TableNativeRuntimeTests(unittest.TestCase):
    def fixture(self):
        fixture = fixtures.DocumentTableTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.kind = 2
        fixture.native[200] = True
        fixture.register()
        fixture.document.Save3 = mock.Mock()
        fixture.extension.SaveAs3 = mock.Mock()
        return fixture, fixture.read()['options']

    def kernel(self, *, module=0x1000, known=0x2000, wine=None):
        return SimpleNamespace(GetModuleHandleW=mock.Mock(return_value=module),
            GetProcAddress=mock.Mock(side_effect=[known, wine]))

    def call(self, fixture, expected, *, value=False):
        return adapter.set_document_table_option_windows(app=fixture.app, document=fixture.document,
            field='all.use_template_settings', value=value, expected_options=expected)

    def unchanged(self, fixture, result, *, before=True):
        validate_operation_result('document.table-option-set', result)
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['type'], 'DocumentTableCalibrationRequired')
        self.assertEqual(result['mutation'], {'attempted': False, 'may_have_changed': False})
        fixture.no_setters()
        fixture.document.Save3.assert_not_called()
        fixture.extension.SaveAs3.assert_not_called()
        self.assertIs(fixture.native[200], before)
        self.assertFalse(fixture.modified)

    def test_non_windows_refuses_real_public_profile_without_loading_native_api(self):
        for platform in ('darwin', 'linux'):
            with self.subTest(platform=platform):
                fixture, expected = self.fixture()
                with mock.patch.object(adapter.sys, 'platform', platform), \
                     mock.patch.object(ctypes, 'WinDLL', create=True) as library, \
                     mock.patch.object(adapter, '_capture') as capture:
                    result = self.call(fixture, expected)
                self.unchanged(fixture, result)
                library.assert_not_called()
                capture.assert_not_called()

    def test_wine_unknown_module_control_export_and_error_fail_closed_even_for_noop(self):
        cases = [dict(module=None), dict(module=0), dict(known=None), dict(known=0), dict(wine=0x3000),
                 dict(error=0), dict(error=5), dict(error=126), dict(error=None), dict(error=127.0)]
        for case in cases:
            for before, value in ((True, False), (False, False)):
                with self.subTest(case=case, before=before, value=value):
                    fixture, expected = self.fixture()
                    fixture.native[200] = before
                    expected = fixture.read()['options']
                    kernel = self.kernel(**{key: value for key, value in case.items() if key != 'error'})
                    with mock.patch.object(adapter.sys, 'platform', 'win32'), \
                         mock.patch.object(ctypes, 'WinDLL', return_value=kernel, create=True), \
                         mock.patch.object(ctypes, 'set_last_error', create=True), \
                         mock.patch.object(ctypes, 'get_last_error', return_value=case.get('error', 127), create=True), \
                         mock.patch.object(adapter, '_capture') as capture:
                        result = self.call(fixture, expected, value=value)
                    self.unchanged(fixture, result, before=before)
                    capture.assert_not_called()

    def test_probe_load_lookup_and_last_error_exceptions_all_refuse(self):
        for failure in ('load', 'module', 'lookup', 'clear-error', 'read-error'):
            with self.subTest(failure=failure):
                fixture, expected = self.fixture()
                kernel = self.kernel()
                if failure == 'module': kernel.GetModuleHandleW.side_effect = OSError('module unavailable')
                if failure == 'lookup': kernel.GetProcAddress.side_effect = RuntimeError('lookup unavailable')
                with mock.patch.object(adapter.sys, 'platform', 'win32'), \
                     mock.patch.object(ctypes, 'WinDLL', return_value=kernel, create=True,
                         side_effect=OSError('library unavailable') if failure == 'load' else None), \
                     mock.patch.object(ctypes, 'set_last_error', create=True,
                         side_effect=OSError('cannot clear error') if failure == 'clear-error' else None), \
                     mock.patch.object(ctypes, 'get_last_error', return_value=127, create=True,
                         side_effect=OSError('cannot read error') if failure == 'read-error' else None):
                    result = self.call(fixture, expected)
                self.unchanged(fixture, result)

    def test_known_ntclose_then_missing_wine_export_with_error_127_admits_exact_native_profile(self):
        fixture, expected = self.fixture()
        kernel = self.kernel()
        with mock.patch.object(adapter.sys, 'platform', 'win32'), \
             mock.patch.object(ctypes, 'WinDLL', return_value=kernel, create=True) as library, \
             mock.patch.object(ctypes, 'set_last_error', create=True) as clear, \
             mock.patch.object(ctypes, 'get_last_error', return_value=127, create=True) as error:
            result = operations.execute_operation(fixture.app, 'document.table-option-set',
                dict(field='all.use_template_settings', value=False, expected_options=expected),
                documents=fixture.documents, session_id='writer', document_id=fixture.entry.document_id,
                expected_update_stamp=7, lease_id=fixture.lease)
        validate_operation_result('document.table-option-set', result)
        self.assertTrue(result['ok'])
        self.assertTrue(result['changed'])
        self.assertEqual(result['mutation'], {'attempted': True, 'may_have_changed': True})
        fixture.extension.SetUserPreferenceToggle.assert_called_once_with(200, 0, False)
        fixture.document.SetSaveFlag.assert_called_once()
        fixture.document.Save3.assert_not_called()
        fixture.extension.SaveAs3.assert_not_called()
        library.assert_called_once_with('kernel32', use_last_error=True)
        kernel.GetModuleHandleW.assert_called_once_with('ntdll.dll')
        self.assertEqual(kernel.GetProcAddress.call_args_list, [mock.call(0x1000, b'NtClose'), mock.call(0x1000, b'wine_get_version')])
        clear.assert_called_once_with(0)
        error.assert_called_once()
        self.assertEqual(kernel.GetProcAddress.argtypes, [ctypes.c_void_p, ctypes.c_char_p])
        self.assertIs(kernel.GetProcAddress.restype, ctypes.c_void_p)
        self.assertEqual(kernel.GetModuleHandleW.argtypes, [ctypes.c_wchar_p])
        self.assertIs(kernel.GetModuleHandleW.restype, ctypes.c_void_p)


if __name__ == '__main__':
    unittest.main()
