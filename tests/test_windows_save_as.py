"""Regression coverage for the single modern COM save boundary."""
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts import windows_save_as as adapter
from tests.save_as_fixture import com_arguments


class SaveAs3Tests(unittest.TestCase):
    def invoke(self, behavior):
        extension = SimpleNamespace(_FlagAsMethod=mock.Mock(), SaveAs3=mock.Mock(side_effect=behavior))
        document = SimpleNamespace(Extension=extension)
        receipt = {}
        with com_arguments():
            returned = adapter.save_as3(document, 'target.SLDPRT', receipt=receipt)
        return returned, receipt, extension

    def test_explicit_null_dispatch_and_i4_byref_outputs_one_method_call(self):
        def save(path, version, options, export_data, advanced, errors, warnings):
            self.assertEqual((path, version, options), ('target.SLDPRT', 0, 1))
            for null in (export_data, advanced):
                self.assertEqual(null.varianttype, 9)
                self.assertIsNone(null.value)
            self.assertIsNot(export_data, advanced)
            for output in (errors, warnings):
                self.assertEqual(output.varianttype, 0x4000 | 3)
                self.assertEqual(output.value, -2147483648)
            errors.value, warnings.value = 0, 8
            return True
        with mock.patch.object(adapter, 'native_call', side_effect=lambda stage, name, call: call()) as trace:
            returned, receipt, extension = self.invoke(save)
        self.assertTrue(returned)
        self.assertEqual(receipt, dict(save_attempted=True, api_saved=True, save_errors=0, save_warnings=8))
        extension._FlagAsMethod.assert_called_once_with('SaveAs3')
        extension.SaveAs3.assert_called_once()
        self.assertEqual(trace.call_args.args[:2], ('save-as', 'IModelDocExtension.SaveAs3'))

    def test_false_and_error_codes_are_retained_without_coercion(self):
        for error in (0, 32):
            with self.subTest(error=error):
                def save(*args):
                    args[-2].value, args[-1].value = error, 4
                    return False
                returned, receipt, extension = self.invoke(save)
                self.assertFalse(returned)
                self.assertEqual(receipt['save_errors'], error)
                self.assertEqual(receipt['save_warnings'], 4)
                self.assertIs(receipt['api_saved'], False)
                extension.SaveAs3.assert_called_once()

    def test_first_native_exception_keeps_written_outputs_and_attempted_state(self):
        original = RuntimeError('first native failure')
        def save(*args):
            args[-2].value, args[-1].value = 32, 4
            raise original
        extension = SimpleNamespace(_FlagAsMethod=mock.Mock(), SaveAs3=mock.Mock(side_effect=save))
        receipt = {}
        with com_arguments(), self.assertRaises(RuntimeError) as caught:
            adapter.save_as3(SimpleNamespace(Extension=extension), 'target.GLB', receipt=receipt)
        self.assertIs(caught.exception, original)
        self.assertEqual(receipt, dict(save_attempted=True, save_errors=32, save_warnings=4))
        extension.SaveAs3.assert_called_once()

    def test_unwritten_outputs_and_nonboolean_returns_fail_after_one_attempt(self):
        for defect in ('unwritten', 'nonboolean'):
            with self.subTest(defect=defect):
                def save(*args):
                    if defect == 'nonboolean':
                        args[-2].value, args[-1].value = 0, 0
                        return 1
                    return True
                extension = SimpleNamespace(_FlagAsMethod=mock.Mock(), SaveAs3=mock.Mock(side_effect=save))
                receipt = {}
                with com_arguments(), self.assertRaises(RuntimeError):
                    adapter.save_as3(SimpleNamespace(Extension=extension), 'target.GLB', receipt=receipt)
                extension.SaveAs3.assert_called_once()
                self.assertTrue(receipt['save_attempted'])
