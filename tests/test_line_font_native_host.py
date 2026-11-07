"""Strict native Windows/Wine/unknown policy; mock OS probes, never DLLs/CAD."""
from types import SimpleNamespace
from unittest import mock
import unittest
import test_document_line_font as fixtures
from swcli.hosts import windows_document_line_font as adapter

REAL_PROBE = adapter._native_windows


class KernelProbe:
    def __init__(self, *, module=0x1000, known=0x2000, wine=0, error=127):
        self.current_error = 0
        self.GetModuleHandleW = mock.Mock(return_value=module)
        def lookup(handle, name):
            assert handle == module
            if name == b"NtClose":
                return known
            assert name == b"wine_get_version"
            self.current_error = error
            return wine
        self.GetProcAddress = mock.Mock(side_effect=lookup)

    def set_error(self, value):
        self.current_error = value

    def get_error(self):
        return self.current_error


class LineFontNativeHostTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.LineFontTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.fx = self.case.fx
        self.fx.app.RevisionNumber = "33.5.0"
        self.saves = [mock.Mock() for _ in range(4)]
        self.fx.document.Save3, self.fx.document.SaveAs3 = self.saves[:2]
        self.fx.extension.SaveAs, self.fx.extension.SaveAs3 = self.saves[2:]

    def edit(self, value, internal):
        return adapter.set_document_line_font_windows(app=self.fx.app, document=self.fx.document,
            field="visible_edges.style", value=value, expected_options=self.case.before,
            _internal_calibration=internal)

    def probe_context(self, kernel, platform="win32", loader_error=None):
        from contextlib import ExitStack
        context = ExitStack()
        context.enter_context(mock.patch.object(adapter, "_native_windows", side_effect=REAL_PROBE))
        context.enter_context(mock.patch.object(adapter.sys, "platform", platform))
        load = context.enter_context(mock.patch.object(adapter.ctypes, "WinDLL", return_value=kernel,
                                                       side_effect=loader_error, create=True))
        context.enter_context(mock.patch.object(adapter.ctypes, "set_last_error", side_effect=kernel.set_error, create=True))
        context.enter_context(mock.patch.object(adapter.ctypes, "get_last_error", side_effect=kernel.get_error, create=True))
        return context, load

    def assert_unmutated(self):
        self.fx.assert_no_setters()
        for saved in self.saves:
            saved.assert_not_called()
        self.assertFalse(self.fx.modified)
        self.assertEqual(self.fx.native, {101:0,102:1,103:1,104:0})
        self.assertIs(self.fx.app.ActiveDoc, self.fx.foreground)
        self.assertEqual(self.fx.foreground.GetUpdateStamp(), 8)
        self.assertFalse(self.fx.foreground.GetSaveFlag())

    def test_non_windows_platform_never_loads_dll(self):
        for platform in ("darwin", "linux", "unknown", None):
            context, load = self.probe_context(KernelProbe(), platform)
            with self.subTest(platform=platform), context:
                self.assertIs(REAL_PROBE(), False)
                load.assert_not_called()

    def test_native_requires_known_export_then_missing_wine_with_error_127(self):
        kernel = KernelProbe()
        context, load = self.probe_context(kernel)
        with context:
            self.assertIs(REAL_PROBE(), True)
        load.assert_called_once_with("kernel32.dll", use_last_error=True)
        kernel.GetModuleHandleW.assert_called_once_with("ntdll.dll")
        self.assertEqual(kernel.GetProcAddress.call_args_list,
                         [mock.call(0x1000,b"NtClose"), mock.call(0x1000,b"wine_get_version")])
        self.assertEqual(kernel.GetProcAddress.restype, adapter.ctypes.c_void_p)

    def test_missing_module_or_known_export_cannot_look_like_native(self):
        for kernel in (KernelProbe(module=0), KernelProbe(known=0)):
            context, _ = self.probe_context(kernel)
            with context:
                self.assertIs(REAL_PROBE(), False)
            self.assertFalse(any(call.args[1] == b"wine_get_version" for call in kernel.GetProcAddress.call_args_list))

    def test_wine_and_unknown_results_refuse_write_noop_and_internal_calibration(self):
        scenarios = (("darwin", KernelProbe(), None),
                     ("win32", KernelProbe(wine=0x3000,error=127), None),
                     ("win32", KernelProbe(module=0), None),
                     ("win32", KernelProbe(known=0), None),
                     ("win32", KernelProbe(error=0), None),
                     ("win32", KernelProbe(error=5), None),
                     ("win32", KernelProbe(error=126), None),
                     ("win32", KernelProbe(), OSError("probe load failed")))
        for platform, kernel, error in scenarios:
            for value in (0,1):
                for internal in (False,True):
                    context, _ = self.probe_context(kernel, platform, error)
                    with self.subTest(platform=platform,error=error,value=value,internal=internal), context:
                        result = self.edit(value, internal)
                        self.assertFalse(result["ok"], result)
                        self.assertEqual(result["error"]["type"], "DocumentLineFontUncalibrated")
                        self.assertEqual(result["mutation"], dict(attempted=False,may_have_changed=False))
        self.fx.extension.GetUserPreferenceInteger.assert_not_called()
        self.assert_unmutated()

    def test_export_query_or_error_probe_exceptions_are_closed(self):
        kernel = KernelProbe()
        kernel.GetProcAddress.side_effect = RuntimeError("lookup unavailable")
        context, _ = self.probe_context(kernel)
        with context:
            self.assertFalse(self.edit(1,False)["ok"])
        kernel = KernelProbe()
        kernel.get_error = mock.Mock(side_effect=RuntimeError("last error unavailable"))
        context, _ = self.probe_context(kernel)
        with context:
            self.assertFalse(self.edit(1,False)["ok"])
        self.assert_unmutated()

    def test_native_positive_retains_calibrated_write_and_existing_state_guards(self):
        context, _ = self.probe_context(KernelProbe())
        with context:
            result = self.edit(1,False)
        self.assertTrue(result["ok"], result)
        self.fx.extension.SetUserPreferenceInteger.assert_called_once_with(101,0,1)
        self.assertIs(self.fx.app.ActiveDoc, self.fx.foreground)
        for saved in self.saves:
            saved.assert_not_called()

    def test_non_boolean_probe_result_is_unknown(self):
        for unknown in (None,1,"win32"):
            with mock.patch.object(adapter,"_native_windows",return_value=unknown):
                self.assertFalse(self.edit(1,False)["ok"])
        self.assert_unmutated()

    def test_reads_do_not_probe_host_and_remain_available(self):
        with mock.patch.object(adapter,"_native_windows",side_effect=RuntimeError("must not probe reads")) as probe:
            result = adapter.read_document_line_font_windows(app=self.fx.app,document=self.fx.document)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["options"],self.case.before)
        probe.assert_not_called()
        self.assert_unmutated()
