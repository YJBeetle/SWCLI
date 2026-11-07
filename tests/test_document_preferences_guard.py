"""Portable regression faults; no native Windows proof is produced."""
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from swcli.hosts import windows_document_preferences_guard as guard
from swcli.hosts import windows_document_annotation_fonts as fonts
from swcli.hosts import windows_document_display_options as display
from swcli.hosts import windows_document_drafting_standard as standards
import test_document_annotation_fonts as font_tests
import test_document_display_options as display_tests
import test_document_drafting_standard as standard_tests

class PreferenceGuards(unittest.TestCase):
    def fixture(self, kind):
        cls={'fonts':font_tests.DocumentAnnotationFontTests,'display':display_tests.DocumentDisplayOptionsTests,
             'standards':standard_tests.DocumentDraftingStandardTests}[kind]
        f=cls();f.setUp();self.addCleanup(f.doCleanups)
        adapter={'fonts':fonts,'display':display,'standards':standards}[kind]
        if kind=='fonts':
            call=lambda:fonts.set_document_annotation_font_windows(app=f.app,document=f.document,field='bold',value=True,expected_font=f.expected)
            reader='_read_font';setter=f.extension.SetUserPreferenceTextFormat
        elif kind=='display':
            call=lambda:display.set_document_display_option_windows(app=f.app,document=f.document,field='grid.display',value=True,expected_value=False)
            reader='_read_options';setter=f.extension.SetUserPreferenceToggle
        else:
            expected=f.expected();call=lambda:standards.set_document_drafting_standard_windows(app=f.app,document=f.document,value='iso',expected_snapshot=expected)
            reader='_read_snapshot';setter=f.extension.SetUserPreferenceInteger
        return f,adapter,call,reader,setter

    def test_unknown_host_zero_setter_and_dirty_for_all_three(self):
        for kind in ('fonts','display','standards'):
            with self.subTest(kind=kind):
                f,a,call,_,setter=self.fixture(kind)
                with patch.object(a,'_require_calibrated_native_host',side_effect=ValueError('unknown native host')):
                    result=call()
                self.assertFalse(result['ok']);self.assertEqual(result['mutation'],{'attempted':False,'may_have_changed':False})
                setter.assert_not_called();f.document.SetSaveFlag.assert_not_called()

    def test_peer_drift_before_mutation_and_after_setter_keeps_partial_receipt(self):
        for kind in ('fonts','display','standards'):
            for field in ('stamp','dirty','title','path','Extension','configuration'):
                for after in (False,True):
                    with self.subTest(kind=kind,field=field,after=after):
                        f,a,call,reader,setter=self.fixture(kind)
                        def drift():
                            peer=f.foreground
                            setattr(peer,field,{'stamp':99,'dirty':True,'title':'other','path':'other','Extension':object(),'configuration':'other'}[field])
                        if after:
                            original=setter.side_effect
                            def effect(*args):
                                result=original(*args);drift();return result
                            setter.side_effect=effect
                        actual=getattr(a,reader)
                        def read(*args):
                            result=actual(*args)
                            if not after:drift()
                            return result
                        with patch.object(a,'_require_calibrated_native_host',return_value=None),patch.object(a,reader,side_effect=read):result=call()
                        self.assertFalse(result['ok'],result)
                        self.assertEqual(result['mutation']['attempted'],after)
                        self.assertEqual(setter.call_count,int(after));f.document.SetSaveFlag.assert_not_called()

    def test_kernel_export_proof_requires_known_export_and_exact_missing_error(self):
        for handle,known,wine,error,allowed in ((1,1,0,127,True),(0,1,0,127,False),(1,0,0,127,False),
                                              (1,1,1,127,False),(1,1,0,0,False),(1,1,0,5,False)):
            with self.subTest(handle=handle,known=known,wine=wine,error=error):
                kernel=SimpleNamespace(GetModuleHandleW=Mock(return_value=handle),GetProcAddress=Mock(side_effect=lambda h,n: known if n==b'NtClose' else wine))
                with patch.object(guard.sys,'platform','win32'),patch.object(guard.ctypes,'WinDLL',create=True,return_value=kernel),patch.object(guard.ctypes,'set_last_error',create=True),patch.object(guard.ctypes,'get_last_error',create=True,return_value=error):
                    if allowed:guard.require_native_windows()
                    else:
                        with self.assertRaises(ValueError):guard.require_native_windows()

    def test_peer_drift_during_target_state_check_never_marks_dirty(self):
        f,a,call,reader,setter=self.fixture('standards')
        before=guard._state(f.document);foreground=guard.capture_foreground(f.app,f.document)
        actual=guard._state
        def state(doc):
            value=actual(doc)
            if doc is f.document:f.foreground.stamp+=1
            return value
        with patch.object(guard,'_state',side_effect=state),self.assertRaisesRegex(RuntimeError,'peer'):
            guard.verify_metadata_state(f.app,f.document,before,foreground,changed=True,require_writable=True)
        f.document.SetSaveFlag.assert_not_called()

    def test_setter_first_error_survives_secondary_peer_drift(self):
        for kind in ('fonts','display','standards'):
            with self.subTest(kind=kind):
                f,a,call,reader,setter=self.fixture(kind)
                def fail(*args):f.foreground.stamp+=1;raise RuntimeError('first native cause')
                setter.side_effect=fail
                with patch.object(a,'_require_calibrated_native_host',return_value=None):result=call()
                self.assertFalse(result['ok']);self.assertTrue(result['mutation']['may_have_changed'])
                self.assertIn('first native cause',result['error']['message']);f.document.SetSaveFlag.assert_not_called()
