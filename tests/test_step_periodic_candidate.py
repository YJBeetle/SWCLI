"""No CAD: three-preference transaction and public refusal through actual export routing."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace, ModuleType
import sys
import tempfile
import unittest
from unittest import mock

from swcli.hosts import windows_step_export as step, windows_step_periodic as periodic, windows_documents as docs
from swcli.operation_schemas import validate_operation_request
from swcli.result_schemas import validate_operation_result, OperationResultInvalid
from swcli.cli import build_parser, _typed_operation
from save_as_fixture import save_as_fixture
from test_step_export_options import CONSTANTS, payload


class PeriodicTests(unittest.TestCase):
    def setUp(self):
        self.values = {999: 203, 777: 1, 555: False}
        self.writes = []
        self.doc = SimpleNamespace(GetType=1, GetUpdateStamp=7, GetSaveFlag=False, GetTitle='source',
            GetPathName='source.SLDPRT', ConfigurationManager=SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name='Default')),
            IsOpenedReadOnly=False, IsOpenedViewOnly=False, SketchManager=SimpleNamespace(ActiveSketch=None))
        self.peer = SimpleNamespace(GetType=1, GetUpdateStamp=2, GetSaveFlag=False, GetTitle='peer',
            GetPathName='peer.SLDPRT', ConfigurationManager=SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name='Default')))
        self.app = SimpleNamespace(Visible=False, RevisionNumber='33.5.0', ActiveDoc=self.peer, IsSame=lambda a,b:1 if a is b else 0)
        self.app.GetUserPreferenceIntegerValue = self.read
        self.app.GetUserPreferenceToggle = self.read
        self.app.SetUserPreferenceIntegerValue = self.set
        self.app.SetUserPreferenceToggle = self.toggle
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(step, 'resolve_step_swconst', return_value=Path('installed/swconst.tlb')))
        self.stack.enter_context(mock.patch.object(step, 'read_step_constants', return_value=CONSTANTS))
        self.native = self.stack.enter_context(mock.patch.object(step, '_native_windows_runtime', return_value=True))
        self.constant = self.stack.enter_context(mock.patch.object(periodic, 'read_periodic_constant', return_value=555))

    def read(self, key):return self.values[key]

    def set(self, key, value):
        self.writes.append((key, value)); self.values[key] = value; return True

    def toggle(self, key, value):
        self.set(key, value)
        return None

    def scope(self, result, value=True, *, calibration=True, isolated=True, protocol='ap214', geometry='solid-surface'):
        self.stack.enter_context(step.step_host_scope(self.app, isolated=isolated, calibration=calibration))
        return step.step_preferences(self.app, self.doc, protocol, geometry, result, split_periodic_faces=value)

    def test_three_value_full_cas_both_boolean_directions_and_protocols(self):
        for protocol in ('ap203', 'ap214'):
            for value in (True, False):
                with self.subTest(protocol=protocol,value=value):
                    self.values={999:203,777:1,555:not value}; before=dict(self.values); self.writes.clear();r={}
                    with self.scope(r,value,protocol=protocol):self.assertEqual(self.values,{999:int(protocol[2:]),777:0,555:value})
                    self.assertEqual(self.values,before);self.assertTrue(r['step_preferences']['restored'])
                    self.assertEqual(self.writes[-1],(999,203) if protocol=='ap214' else (777,1))
                    self.assertTrue(all(set(s['values'])=={'swStepAP','swStepExportPreference',periodic.TOGGLE} for s in r['step_preferences']['stages']))
                    self.assertIs(type(r['step_preferences']['before'][periodic.TOGGLE]),bool)

    def test_noop_uses_no_setter_and_keeps_full_context_and_cas(self):
        self.values={999:214,777:0,555:True};r={}
        with self.scope(r):pass
        self.assertEqual(self.writes,[]);self.assertTrue(r['step_preferences']['restored']);self.assertFalse(self.doc.GetSaveFlag)

    def test_public_unconfirmed_language_refuses_before_constants_or_writes(self):
        for value in (True,False):
            with self.subTest(value=value),self.assertRaises(step.StepExportError) as e:
                with self.scope({},value,calibration=False):self.fail('unaccepted option allowed')
            self.assertEqual(e.exception.code,'StepSplitLanguageUnsupported')
        self.constant.assert_not_called();self.assertEqual(self.writes,[])

    def test_private_scope_still_requires_native_2025_hidden_owned_host(self):
        for mode in ('wine','revision','visible','shared'):
            with self.subTest(mode=mode):
                self.native.return_value=mode!='wine';self.app.RevisionNumber='33.5.1' if mode=='revision' else '33.5.0';self.app.Visible=mode=='visible'
                with self.assertRaises(step.StepExportError):
                    with self.scope({},isolated=mode!='shared'):self.fail('unsupported host')
        self.constant.assert_not_called();self.assertEqual(self.writes,[])

    def test_readonly_viewonly_nonpart_or_active_sketch_refused_without_writes(self):
        for field,value in (('IsOpenedReadOnly',True),('IsOpenedViewOnly',True),('GetType',2)):
            old=getattr(self.doc,field);setattr(self.doc,field,value)
            with self.subTest(field=field),self.assertRaises((ValueError,step.StepExportError)):
                with self.scope({}):self.fail('invalid source')
            setattr(self.doc,field,old)
        self.doc.SketchManager.ActiveSketch=object()
        with self.assertRaises(step.StepExportError):
            with self.scope({}):self.fail('editing source')
        self.assertEqual(self.writes,[])

    def test_unknown_or_untyped_original_value_never_writes(self):
        for key,value in ((999,242),(777,99),(555,None),(555,1),(999,True),(777,False)):
            before=dict(self.values);self.values[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(step.StepExportError):
                with self.scope({}):self.fail('unknown original')
            self.assertEqual(self.writes,[]);self.values=before

    def test_installed_toggle_enum_unavailable_stops_without_writes(self):
        self.constant.side_effect=step.StepExportError('StepTypeLibraryUnavailable','missing installed toggle')
        with self.assertRaises(step.StepExportError):
            with self.scope({}):self.fail('missing native constant')
        self.assertEqual(self.writes,[])

    def test_initial_and_each_setter_full_cas_detects_non_target_drift(self):
        def setter(key,value):
            accepted=self.set(key,value)
            if key==999 and value==214:self.values[555]=True
            return accepted
        self.app.SetUserPreferenceIntegerValue=setter;r={}
        with self.assertRaises(step.StepExportError):
            with self.scope(r):self.fail('full readback drift')
        self.assertNotIn((777,0),self.writes);self.assertEqual(self.values[999],203)
        self.assertTrue(self.values[555]);self.assertFalse(r['step_preferences']['restored'])

    def test_partial_false_or_throwing_toggle_restores_all_attempted_preferences(self):
        for throws in (False,True):
            def setter(key,value):
                self.set(key,value)
                if value:
                    if throws:raise RuntimeError('first partial toggle')
                    return False
                return None
            self.app.SetUserPreferenceToggle=setter;self.values={999:203,777:1,555:False};r={};self.writes.clear()
            with self.subTest(throws=throws),self.assertRaises((step.StepExportError,RuntimeError)):
                with self.scope(r):self.fail('partial setter allowed')
            self.assertEqual(self.values,{999:203,777:1,555:False});self.assertTrue(r['step_preferences']['restored'])
            self.assertEqual(self.writes,[(999,214),(777,0),(555,True),(555,False),(777,1),(999,203)])

    def test_export_preference_or_source_drift_cannot_succeed(self):
        for mode in ('toggle','source','peer'):
            self.values={999:203,777:1,555:False};r={}
            with self.subTest(mode=mode),self.assertRaises((step.StepExportError,RuntimeError)):
                with self.scope(r):
                    if mode=='toggle':self.values[555]=False
                    elif mode=='source':self.doc.GetUpdateStamp+=1
                    else:self.peer.GetSaveFlag=True
            self.assertTrue(r['step_preferences']['restored'])
            self.doc.GetUpdateStamp=7;self.peer.GetSaveFlag=False

    def test_foreign_integer_value_is_left_untouched_but_other_owned_preferences_restore(self):
        r={}
        with self.assertRaises(step.StepExportError):
            with self.scope(r):self.values[999]=242
        self.assertEqual(self.values,{999:242,777:1,555:False});self.assertFalse(r['step_preferences']['restored'])
        self.assertNotIn((999,203),self.writes);self.assertIn('foreign value',str(r['preference_restore_errors']))

    def test_business_exception_or_numeric_error_survives_restore_failure(self):
        def setter(key,value):
            if value is False:raise RuntimeError('restore toggle failure')
            return self.toggle(key,value)
        self.app.SetUserPreferenceToggle=setter;r={};first=RuntimeError('first native save failure')
        with self.assertRaises(RuntimeError) as e:
            with self.scope(r):raise first
        self.assertIs(e.exception,first);self.assertTrue(r['preference_restore_errors']);self.assertEqual(self.values[999],203)
        self.values={999:203,777:1,555:False};r={}
        with self.scope(r):r['error']=dict(type='ExportFailed',message='first numeric save',save_errors=8)
        self.assertEqual(r['error']['save_errors'],8);self.assertFalse(r['step_preferences']['restored'])

    def test_success_then_restore_failure_raises_and_keeps_mutation_receipt(self):
        def setter(key,value):return False if value is False else self.toggle(key,value)
        self.app.SetUserPreferenceToggle=setter;r={}
        with self.assertRaises(step.StepExportError) as e:
            with self.scope(r):pass
        self.assertEqual(e.exception.code,'StepPreferenceRestoreFailed');self.assertFalse(r['ok']);self.assertTrue(r['mutation']['may_have_changed'])

    def adapter(self,target,value,*,calibration=False,save_error=0,restore_fail=False,raw=None,save_flag_change=False):
        modules={'pythoncom':ModuleType('pythoncom'),'win32com':ModuleType('win32com'),'win32com.client':ModuleType('win32com.client')}
        modules['win32com'].client=modules['win32com.client']
        def save(path, version, options, export_data, advanced_options, errors, warnings):
            Path(path).write_bytes(payload() if raw is None else raw)
            errors.value, warnings.value = save_error, 0
            if save_flag_change:
                self.doc.GetSaveFlag = True
            return save_error == 0

        self.doc.Extension = SimpleNamespace()
        self.doc.SaveAs3 = mock.Mock(side_effect=save)
        self.doc.ClearSelection2 = mock.Mock()
        before={'document':dict(type=1,path='source.SLDPRT',title='source',modified=False,update_stamp=7),'needs_rebuild':0}
        if restore_fail:self.app.SetUserPreferenceToggle=lambda key,v:False if v is False else self.toggle(key,v)
        with mock.patch.object(docs.sys,'platform','win32'),mock.patch.dict(sys.modules,modules), \
                mock.patch.object(docs,'_export_source_state',return_value=deepcopy(before)), \
                mock.patch.object(docs, 'save_as3', side_effect=save_as_fixture), \
                step.step_host_scope(self.app,isolated=True,calibration=calibration):
            return docs.export_active_windows_document(str(target),app=self.app,document=self.doc,overwrite=True,
                step_protocol='ap214',step_geometry='solid-surface',step_split_periodic_faces=value)

    def test_actual_adapter_public_false_preserves_existing_file_with_zero_save(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'out.step';p.write_bytes(b'original')
            r=self.adapter(p,False)
            self.assertEqual(r['error']['type'],'StepSplitLanguageUnsupported');self.assertEqual(p.read_bytes(),b'original')
            self.doc.SaveAs3.assert_not_called();self.assertEqual(self.writes,[]);self.assertEqual(list(Path(d).iterdir()),[p])
            validate_operation_result('document.export',r)

    def test_production_refuses_non_english_or_untyped_language_before_preference_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "out.step"
            target.write_bytes(b"existing target")
            self.app.GetUserPreferenceIntegerValue = mock.Mock(wraps=self.read)
            self.app.GetUserPreferenceToggle = mock.Mock(wraps=self.read)
            for language in ("chinese-simplified", "English", "", None, False):
                self.app.GetCurrentLanguage = mock.Mock(spec=lambda: None, return_value=language)
                for split in (True, False):
                    with self.subTest(language=language, split=split):
                        result = self.adapter(target, split)
                        self.assertEqual(result["error"]["type"], "StepSplitLanguageUnsupported")
                        self.assertEqual(result["mutation"], dict(attempted=False, may_have_changed=False))
                        self.assertNotIn("step_preferences", result)
                        self.doc.SaveAs3.assert_not_called()
                        self.assertEqual(target.read_bytes(), b"existing target")
            self.app.GetUserPreferenceIntegerValue.assert_not_called()
            self.app.GetUserPreferenceToggle.assert_not_called()
            self.assertEqual(self.writes, [])

    def test_production_refuses_failed_language_read_before_settings_or_save(self):
        self.app.GetCurrentLanguage = mock.Mock(spec=lambda: None, side_effect=RuntimeError("language unavailable"))
        self.app.GetUserPreferenceIntegerValue = mock.Mock(wraps=self.read)
        self.app.GetUserPreferenceToggle = mock.Mock(wraps=self.read)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "out.step"
            result = self.adapter(target, False)
            self.assertEqual(result["error"]["type"], "StepSplitLanguageUnsupported")
            self.assertFalse(target.exists())
            self.doc.SaveAs3.assert_not_called()
        self.app.GetCurrentLanguage.assert_called_once_with()
        self.app.GetUserPreferenceIntegerValue.assert_not_called()
        self.app.GetUserPreferenceToggle.assert_not_called()

    def test_production_english_owned_route_accepts_both_explicit_values(self):
        self.app.GetCurrentLanguage = mock.Mock(spec=lambda: None, return_value="english")
        for split in (False, True):
            with self.subTest(split=split), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "out.step"
                result = self.adapter(target, split)
                self.assertTrue(result["ok"], result)
                self.assertIs(result["step_preferences"]["requested"][periodic.TOGGLE], split)
                self.assertEqual(result["step_preferences"]["before"], result["step_preferences"]["after"])
                self.assertTrue(result["step_preferences"]["restored"])
                self.assertEqual(target.read_bytes(), payload())
                self.doc.SaveAs3.assert_called_once()
                validate_operation_result("document.export", result)
        self.assertEqual(self.app.GetCurrentLanguage.call_count, 2)

    def test_production_omitted_periodic_option_keeps_legacy_preference_path(self):
        self.app.GetCurrentLanguage = mock.Mock(side_effect=AssertionError("legacy route read language"))
        self.app.GetUserPreferenceToggle = mock.Mock(side_effect=AssertionError("legacy route read periodic toggle"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "out.step"
            with mock.patch.object(docs, "verify_periodic_step_output",
                                   side_effect=AssertionError("legacy route used strict periodic parser")), \
                    mock.patch.object(docs, "verify_step_output", wraps=step.verify_step_output) as legacy:
                result = self.adapter(target, None)
            legacy.assert_called_once()
            self.assertTrue(result["ok"], result)
            self.assertEqual(target.read_bytes(), payload())
            self.doc.SaveAs3.assert_called_once()
            self.assertEqual(set(result["step_preferences"]["before"]), {"swStepAP", "swStepExportPreference"})
            self.assertEqual(result["step_preferences"]["before"], result["step_preferences"]["after"])
        self.app.GetCurrentLanguage.assert_not_called()
        self.app.GetUserPreferenceToggle.assert_not_called()

    def test_actual_adapter_candidate_success_validates_output_and_full_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'out.step';r=self.adapter(p,True,calibration=True)
            self.assertTrue(r['ok'],r);self.assertEqual(p.read_bytes(),payload());self.doc.SaveAs3.assert_called_once()
            self.assertEqual(self.values,{999:203,777:1,555:False});validate_operation_result('document.export',r)

    def test_periodic_save_flag_drift_refuses_publication_after_preference_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.step"
            path.write_bytes(b"old output")
            result = self.adapter(path, True, calibration=True, save_flag_change=True)
            self.assertFalse(result["ok"])
            self.assertIs(result["api_saved"], True)
            self.assertIs(self.doc.GetSaveFlag, True)
            self.assertEqual(result["error"]["type"], "RuntimeError")
            self.assertIn("document state or foreground changed", result["error"]["message"])
            self.assertEqual(path.read_bytes(), b"old output")
            self.assertEqual(list(path.parent.iterdir()), [path])
            self.assertTrue(result["step_preferences"]["restored"])
            self.assertEqual(self.values, {999: 203, 777: 1, 555: False})
            validate_operation_result("document.export", result)

    def test_invalid_public_periodic_utf8_never_replaces_existing_output(self):
        self.app.GetCurrentLanguage = "english"
        raw = payload().replace(b"MANIFOLD_SOLID_BREP", b"MANIFOLD_SOLID_BREP\xe6")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "out.step"
            target.write_bytes(b"old published file")
            result = self.adapter(target, False, raw=raw)
            self.assertFalse(result["ok"])
            self.assertIs(result["api_saved"], True)
            self.assertTrue(result["step_preferences"]["restored"])
            self.assertEqual(result["error"]["type"], "StepOutputMismatch")
            self.assertEqual(target.read_bytes(), b"old published file")
            self.assertEqual(set(target.parent.iterdir()), {target})
            validate_operation_result("document.export", result)

    def test_actual_adapter_restore_failure_or_numeric_error_never_publishes(self):
        for save_error in (0,8):
            self.values={999:203,777:1,555:False}
            with self.subTest(save_error=save_error),tempfile.TemporaryDirectory() as d:
                p=Path(d)/'out.step';p.write_bytes(b'original');r=self.adapter(p,True,calibration=True,save_error=save_error,restore_fail=True)
                self.assertFalse(r['ok']);self.assertEqual(p.read_bytes(),b'original');self.assertEqual(list(Path(d).iterdir()),[p])
                self.assertTrue(r['preference_restore_errors']);self.assertTrue(r['mutation']['may_have_changed'])
                self.assertEqual(r['error']['type'],'ExportFailed' if save_error else 'StepPreferenceRestoreFailed')
                if save_error:self.assertEqual(r['error']['save_errors'],8)
                validate_operation_result('document.export',r)


    def test_success_receipt_cannot_drop_toggle_after_or_full_readback_stages(self):
        with tempfile.TemporaryDirectory() as d:
            result=self.adapter(Path(d)/'out.step',True,calibration=True)
        self.assertTrue(result['ok'])
        for key in ('after','requested','stages'):
            changed=deepcopy(result)
            if key=='stages':changed['step_preferences']['stages']=[]
            else:changed['step_preferences'][key].pop(periodic.TOGGLE)
            with self.subTest(key=key),self.assertRaises(OperationResultInvalid):validate_operation_result('document.export',changed)


    def test_toggle_requires_documented_void_and_integer_requires_true(self):
        for unknown in (True,False,0,1,'ok'):
            self.values={999:203,777:1,555:False};r={}
            def unexpected(key,value):
                self.set(key,value)
                return unknown if value is True else None
            self.app.SetUserPreferenceToggle=unexpected
            with self.subTest(value=unknown),self.assertRaises(step.StepExportError):
                with self.scope(r):self.fail('unexpected toggle return accepted')
            self.assertEqual(self.values,{999:203,777:1,555:False})
            self.assertTrue(r['step_preferences']['restored'])
            row=next(x for x in r['step_preferences']['setter_returns'] if x['preference']==periodic.TOGGLE)
            self.assertEqual(row['return_type'],type(unknown).__name__)


    def test_integer_setter_still_rejects_none_after_toggle_void_correction(self):
        def integer(key,value):
            self.set(key,value)
            return None if key==999 and value==214 else True
        self.app.SetUserPreferenceIntegerValue=integer;r={}
        with self.assertRaises(step.StepExportError):
            with self.scope(r):self.fail('integer None accepted')
        self.assertEqual(self.values,{999:203,777:1,555:False});self.assertTrue(r['step_preferences']['restored'])


class PeriodicContractTests(unittest.TestCase):
    def test_pair_solid_only_bool_extension_lease_and_stamp_are_required(self):
        good=dict(output='part.STP',step_protocol='ap214',step_geometry='solid-surface',step_split_periodic_faces=False)
        context=dict(lease_id='l-ab12cd34ef56',expected_update_stamp=5)
        validate_operation_request('document.export',good,**context)
        for key,value in (('step_protocol','ap242'),('step_geometry','wireframe'),('step_geometry','wireframe-sketches'),
                          ('step_split_periodic_faces',0),('step_split_periodic_faces','false'),('output','out.stl')):
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):validate_operation_request('document.export',{**good,key:value},**context)
        for field in ('step_protocol','step_geometry'):
            bad=dict(good);bad.pop(field)
            with self.assertRaises(ValueError):validate_operation_request('document.export',bad,**context)
        for incomplete in ({},{'lease_id':context['lease_id']},{'expected_update_stamp':5}):
            with self.assertRaises(ValueError):validate_operation_request('document.export',good,**incomplete)

    def test_cli_false_and_omission_are_distinct_and_daemon_forwards_false(self):
        from swcli.daemon import operations
        argv=['document','export','out.step','--step-protocol','ap214','--step-geometry','solid-surface']
        for option,value in (('--step-split-periodic-faces',True),('--no-step-split-periodic-faces',False)):
            args=build_parser().parse_args(argv+[option]);params=_typed_operation(args)[1]
            self.assertIs(params['step_split_periodic_faces'],value)
            context=SimpleNamespace(app=object(),entry=SimpleNamespace(document=object()))
            with mock.patch.object(operations,'export_active_windows_document',return_value={}) as export:
                operations.document_export(context,params)
            self.assertIs(export.call_args.kwargs['step_split_periodic_faces'],value)
        self.assertNotIn('step_split_periodic_faces',_typed_operation(build_parser().parse_args(argv))[1])

    def test_sdk_and_generic_mcp_preserve_false_without_a_calibration_parameter(self):
        from swcli.sdk import Client
        from swcli.mcp import DaemonBridge
        values=dict(output='periodic.step',step_protocol='ap214',step_geometry='solid-surface',step_split_periodic_faces=False,include_content=False)
        client=Client()
        with mock.patch.object(client,'_execute') as execute:
            client.document.export(**values)
        self.assertIs(execute.call_args.args[1]['step_split_periodic_faces'],False)
        with mock.patch('swcli.mcp.call_daemon',return_value=dict(api_version='swcli/v1',request_id='periodic',success=False,duration_ms=1,error=dict(code='StepSplitLanguageUnsupported',message='unsupported language'))) as wire:
            result=DaemonBridge().call('execute',dict(operation='document.export',parameters=values,lease_id='l-ab12cd34ef56',expected_update_stamp=5))
        self.assertFalse(result['success']);self.assertIs(wire.call_args.args[1]['step_split_periodic_faces'],False)
        with self.assertRaises(ValueError):
            validate_operation_request('document.export',{**values,'calibration':True},lease_id='l-ab12cd34ef56',expected_update_stamp=5)
