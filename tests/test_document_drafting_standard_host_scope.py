"""Portable host-scope faults; no Windows/Wine instance or native call occurs."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from swcli.hosts import windows_document_drafting_standard as adapter
from swcli.hosts import windows_document_preferences_guard as guard
import test_document_drafting_standard as portable


class StandardNativeScope(unittest.TestCase):
    def check(self, platform='win32', revision='33.5.0', *, wine=False, loader_error=False):
        app = SimpleNamespace(RevisionNumber=Mock(spec=lambda: None, return_value=revision))
        kernel = SimpleNamespace(GetModuleHandleW=Mock(return_value=1),
            GetProcAddress=Mock(side_effect=lambda handle,name: 1 if name==b'NtClose' or wine else 0))
        with patch.object(guard.sys, 'platform', platform), patch.object(
                guard.ctypes, 'WinDLL', create=True, return_value=kernel,
                side_effect=OSError('loader unavailable') if loader_error else None), patch.object(
                guard.ctypes, 'set_last_error', create=True), patch.object(
                guard.ctypes, 'get_last_error', create=True, return_value=127), patch.object(
                guard, 'CALIBRATED_DRAFTING_WINDOWS_REVISIONS', ('33.5.0',)):
            adapter._require_calibrated_native_host(app)
        return app

    def test_only_exact_simulated_native_windows_revision_is_eligible(self):
        app = self.check()
        app.RevisionNumber.assert_called_once_with()
        for revision in ('33.5.1', '34.0.0', '33.5', 33, None):
            with self.subTest(revision=revision), self.assertRaisesRegex(ValueError, 'native'):
                self.check(revision=revision)

    def test_wine_nonwindows_and_unreadable_detection_are_closed(self):
        for options in ({'wine': True}, {'platform': 'darwin'}, {'platform': 'linux'}, {'loader_error': True}):
            with self.subTest(options=options), self.assertRaisesRegex(ValueError, 'native'):
                self.check(**options)

    def test_transition_allowlist_alone_cannot_enable_unproven_host_mutation(self):
        fixture = portable.DocumentDraftingStandardTests(); fixture.setUp()
        expected = fixture.expected()
        with patch.object(adapter, 'CALIBRATED_DRAFTING_TRANSITIONS', ((1, 7, 2, 'drafting-defaults-v1'),)), patch.object(
                adapter.sys, 'platform', 'darwin'):
            result = adapter.set_document_drafting_standard_windows(
                app=fixture.app, document=fixture.document, value='iso', expected_snapshot=expected)
        self.assertFalse(result['ok']); self.assertEqual(result['mutation'], {'attempted': False, 'may_have_changed': False})
        fixture.assert_no_mutation()

    def test_complete_cas_noop_does_not_call_host_scope_or_setter(self):
        fixture = portable.DocumentDraftingStandardTests(); fixture.setUp()
        with patch.object(adapter, '_require_calibrated_native_host', side_effect=AssertionError('no-op must not probe scope')):
            result = adapter.set_document_drafting_standard_windows(
                app=fixture.app, document=fixture.document, value='gb', expected_snapshot=fixture.expected())
        self.assertTrue(result['ok']); self.assertFalse(result['changed']); fixture.assert_no_mutation()

    def test_revision_guard_keeps_flat_single_call_trace(self):
        import io
        import json
        import os
        from contextlib import redirect_stderr
        from swcli.hosts.native_trace import trace_native_request
        stream = io.StringIO()
        with patch.dict(os.environ, {'SWCLI_TRACE_NATIVE_CALLS': '1'}), redirect_stderr(stream):
            with trace_native_request('portable-only', 'document.drafting-standard-set'):
                self.check()
        rows = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual([(row['sequence'], row['phase']) for row in rows],
                         [(0, 'begin'), (1, 'begin'), (1, 'end'), (0, 'end')])
        self.assertEqual(rows[1]['call'], 'RevisionNumber')
