"""No CAD: explicit sketch representation, error checks and complete roundtrip traps."""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/ci'))
from gate_support import step_sketch_readback_candidate as candidate
from gate_support.step_fixture_checks import wire_expected_lengths
from test_step_wire_import_once import Failure,App,load as load_once
from test_step_null_binding import Variant,Endpoint


def load():
    spec=importlib.util.spec_from_file_location('sketch_readback_fixture',ROOT/'scripts/ci/verify-step-export-calibration.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def call(name,fn):return fn()


def native_modules():
    return {'pythoncom':SimpleNamespace(VT_BYREF=16384,VT_I4=3,VT_BOOL=11,IID_IDispatch='dispatch',TypeIIDs={'dispatch':Endpoint}),
            'win32com.client':SimpleNamespace(VARIANT=Variant)}


def document(lengths=None,*,code=0,warning=False,kind='3DProfileFeature'):
    values=wire_expected_lengths('wireframe') if lengths is None else lengths
    segment_reads=mock.Mock(return_value=[SimpleNamespace(GetLength=v/1000) for v in values])
    def health(carrier):
        assert carrier.varianttype==16395 and carrier.value is False
        carrier.value=warning;return code
    feature=SimpleNamespace(GetID=17,Name='ImportedSketch',GetTypeName2=kind,GetErrorCode2=mock.Mock(side_effect=health),
        GetSpecificFeature2=SimpleNamespace(GetSketchSegments=lambda:segment_reads()),GetNextFeature=None,GetFirstSubFeature=None,GetNextSubFeature=None)
    return SimpleNamespace(FirstFeature=feature,GetBodies2=lambda *a:(),GetTitle='imported.SLDPRT',GetType=1,GetPathName='',GetSaveFlag=False),feature,segment_reads


def pref_fixture():
    m=load_once();app=App(m)
    app.before['swImportCurvePreference']=1;app.values=dict(app.before)
    return app,{**app.ids,'swGeneralImportAsSketches':0,'swGeneralImportAs3dCurves':1}


class SketchCandidateTests(unittest.TestCase):
    def test_exact_12_and_18_vectors_preselected_sketch_and_zero_feature_codes(self):
        reader=load()
        with mock.patch.dict(sys.modules,native_modules()):
            for geometry in ('wireframe','wireframe-sketches'):
                doc,feature,segments=document(wire_expected_lengths(geometry));e={}
                result=candidate.read_wireframe(reader,doc,e,call,geometry)
                self.assertTrue(result['complete']);self.assertEqual(result['method'],'native-explicit-sketches-checked')
                self.assertEqual(result['lengths_mm'],wire_expected_lengths(geometry));feature.GetErrorCode2.assert_called_once()
                segments.assert_called_once();self.assertEqual(result['feature_inventory'][0]['feature_health']['code'],0)

    def test_sketch_error_warning_unknown_and_boolean_code_reject_before_segments(self):
        with mock.patch.dict(sys.modules,native_modules()):
            for code,warning in ((1,False),(2,True),(None,False),(False,False)):
                doc,feature,segments=document(code=code,warning=warning);e={}
                with self.subTest(code=code,warning=warning),self.assertRaisesRegex(RuntimeError,'feature error code'):
                    candidate.read_wireframe(load(),doc,e,call,'wireframe')
                self.assertFalse(e['complete']);segments.assert_not_called()
                self.assertEqual(e['feature_inventory'][0]['feature_health']['code'],code)

    def test_missing_feature_error_api_is_unknown_failure_without_repair_or_length_fallback(self):
        doc,feature,segments=document();feature.GetErrorCode2.side_effect=Failure('health unavailable');e={}
        with mock.patch.dict(sys.modules,native_modules()),self.assertRaisesRegex(Failure,'health unavailable'):
            candidate.read_wireframe(load(),doc,e,call,'wireframe')
        self.assertFalse(e['complete']);segments.assert_not_called();self.assertEqual(e['first_error']['message'],'health unavailable')

    def test_reference_unknown_and_mixed_representations_never_fall_back(self):
        with mock.patch.dict(sys.modules,native_modules()):
            for kind in ('ImportedCurve','RefCurve','UnknownWire','3DSplineCurve','CompositeCurve'):
                doc,feature,segments=document(kind=kind);e={}
                with self.subTest(kind=kind),self.assertRaisesRegex(RuntimeError,'unexpected feature type'):
                    candidate.read_wireframe(load(),doc,e,call,'wireframe')
                segments.assert_not_called();feature.GetErrorCode2.assert_not_called();self.assertFalse(e['complete'])
            doc,feature,_=document();other,ref,_=document(kind='RefCurve');ref.GetID=18;feature.GetNextFeature=ref;e={}
            with self.assertRaises(RuntimeError):candidate.read_wireframe(load(),doc,e,call,'wireframe')
            self.assertEqual(e['segment_count'],12);self.assertFalse(e['complete'])

    def test_actual_9_260_missing_diagonals_wrong_length_and_nonfinite_are_rejected(self):
        with mock.patch.dict(sys.modules,native_modules()):
            vectors=([10]*4+[30]*2+[40]*3,wire_expected_lengths('wireframe-sketches')[:-2],
                     [10]*4+[30]*4+[41]*4,[10]*4+[30]*4+[float('nan')]*4)
            for values in vectors:
                doc,_,_=document(values);e={}
                with self.subTest(count=len(values)),self.assertRaises(RuntimeError):
                    candidate.read_wireframe(load(),doc,e,call,'wireframe-sketches' if len(values)==16 else 'wireframe')
                self.assertFalse(e['complete']);self.assertIn('first_error',e)

    def test_empty_error_free_sketch_is_rejected_even_with_other_complete_12(self):
        doc,feature,_=document();_,empty,_=document([]);empty.GetID=18;feature.GetNextFeature=empty;e={}
        with mock.patch.dict(sys.modules,native_modules()),self.assertRaisesRegex(RuntimeError,'empty sketch'):
            candidate.read_wireframe(load(),doc,e,call,'wireframe')
        self.assertEqual(e['segment_count'],12);self.assertFalse(e['complete'])

    def test_nested_sketches_deduplicate_by_native_id_and_cycles_still_fail(self):
        reader=load();doc,top,_=document(wire_expected_lengths('wireframe')[:6]);_,child,_=document(wire_expected_lengths('wireframe')[6:])
        child.GetID=18;top.GetFirstSubFeature=child;top.GetNextFeature=child;e={}
        with mock.patch.dict(sys.modules,native_modules()):
            candidate.read_wireframe(reader,doc,e,call,'wireframe')
            self.assertEqual(e['segment_count'],12);child.GetErrorCode2.assert_called_once()
            child.GetNextSubFeature=child
            with self.assertRaisesRegex(RuntimeError,'sibling cycle'):candidate.read_wireframe(reader,doc,{},call,'wireframe')

    def test_explicit_zero_profile_full_eight_cas_and_reverse_owned_restore(self):
        app,constants=pref_fixture();case={}
        with candidate.preferences(app,constants,call,case,lambda:None) as verify:
            verify();self.assertEqual(app.values['swImportCurvePreference'],0)
            self.assertEqual(app.values['swImportNeutral_CurvesAndPointsOption'],app.before['swImportNeutral_CurvesAndPointsOption'])
        p=case['sketch_observer_preferences'];self.assertTrue(p['restored']);self.assertEqual(app.values,app.before)
        self.assertEqual([x['name'] for x in p['restore']],list(reversed([x['name'] for x in p['writes']])))
        self.assertTrue(all(len(x['values'])==8 for x in p['stages'] if x['status']=='observed'))

    def test_native_document_count_property_does_not_require_method_shape(self):
        app,constants=pref_fixture();app.GetDocumentCount=0;case={}
        with candidate.preferences(app,constants,call,case,lambda:None) as verify:verify()
        self.assertEqual(app.values,app.before);self.assertTrue(case['sketch_observer_preferences']['restored'])

    def test_unknown_enum_and_original_preference_stops_before_setters(self):
        for change in ('enum','value'):
            app,constants=pref_fixture();case={}
            if change=='enum':constants['swGeneralImportAsSketches']=False
            else:app.values['swImportCurvePreference']=2
            with self.subTest(change=change),self.assertRaises(RuntimeError):
                with candidate.preferences(app,constants,call,case,lambda:None):self.fail('unexpected import')
            self.assertEqual(app.writes,[])

    def test_full_vector_drift_before_load_stops_and_preserves_unowned_third_value(self):
        app,constants=pref_fixture();case={}
        with self.assertRaisesRegex(RuntimeError,'CAS changed before LoadFile4'):
            with candidate.preferences(app,constants,call,case,lambda:None) as verify:
                app.values['swImportStepConfigData']=True;verify()
        self.assertTrue(app.values['swImportStepConfigData']);self.assertFalse(case['sketch_observer_preferences']['restored'])
        self.assertEqual(app.loads,[])

    def test_partial_setter_failure_restores_owned_attempt_without_retry(self):
        app,constants=pref_fixture();app.partial_set='swImportFreeCurves';case={}
        with self.assertRaisesRegex(Failure,'first partial setter error'):
            with candidate.preferences(app,constants,call,case,lambda:None):self.fail('unexpected import')
        self.assertEqual(app.values,app.before);self.assertTrue(case['sketch_observer_preferences']['restored'])
        self.assertEqual([x for x in app.writes if x==('swImportFreeCurves',True)],[('swImportFreeCurves',True)])

    def test_native_first_error_preserved_separately_from_restore_failure(self):
        app,constants=pref_fixture();app.restore_fail='swImportFreeCurves';case={};first=Failure('first import error')
        with self.assertRaises(Failure) as caught:
            with candidate.preferences(app,constants,call,case,lambda:None):raise first
        self.assertIs(caught.exception,first);p=case['sketch_observer_preferences']
        self.assertTrue(p['restore_errors']);self.assertEqual(p['first_error']['message'],'first import error')

    def test_foreign_owned_integer_is_never_overwritten_on_restore(self):
        app,constants=pref_fixture();case={}
        with self.assertRaises(RuntimeError):
            with candidate.preferences(app,constants,call,case,lambda:None):app.values['swImportCurvePreference']=2
        self.assertEqual(app.values['swImportCurvePreference'],2)
        self.assertEqual([v for k,v in app.writes if k=='swImportCurvePreference'],[0])

    def test_old_head_incomplete_or_mismatched_eight_file_public_report_rejected(self):
        head='a'*40;good=dict(source_commit=head,success=True,cleanup_errors=[],outputs=[dict(protocol=p,geometry=g,surface=s,path=str(i),sha256='b'*64) for i,(p,g,s) in enumerate(candidate.EXPECTED_OUTPUTS)])
        candidate.verify_fresh_public_report(good,head)
        for key,value in [('source_commit','c'*40),('outputs',good['outputs'][:-1]),('success',False),('cleanup_errors',[{}])]:
            bad=deepcopy(good);bad[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):candidate.verify_fresh_public_report(bad,head)
        for index,field,value in [(1,'geometry','solid-surface'),(1,'path','0'),(0,'sha256','unknown')]:
            bad=deepcopy(good);bad['outputs'][index][field]=value
            with self.assertRaises(RuntimeError):candidate.verify_fresh_public_report(bad,head)

    def test_candidate_requires_public_report_and_cannot_select_internal_calibration(self):
        m=load()
        with mock.patch.object(m,'worker') as worker,self.assertRaisesRegex(RuntimeError,'requires --export-report'):
            m.main(['--output-dir','unused','--swconst','unused','--sketch-readback-candidate','--worker'])
        worker.assert_not_called()

    def test_parent_forwards_candidate_flag_once_and_retains_1800_deadline(self):
        m=load();process=mock.Mock();process.poll.return_value=None
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);lib=root/'swconst.tlb';lib.write_bytes(b'fake lib')
            with mock.patch.object(m.subprocess,'Popen',return_value=process) as start,mock.patch.object(m.time,'monotonic',side_effect=[0,1800]),mock.patch.object(m.time,'sleep'):
                self.assertEqual(m.main(['--output-dir',str(root/'out'),'--swconst',str(lib),'--export-report',str(root/'source.json'),'--sketch-readback-candidate']),124)
            command=start.call_args.args[0];self.assertEqual(command.count('--sketch-readback-candidate'),1)
            self.assertEqual(command.count('--export-report'),1);process.kill.assert_called_once();process.wait.assert_called_once()

    def test_worker_selects_eight_same_head_cases_only_and_rejects_old_report_before_host(self):
        import swcli.hosts.windows as windows
        import swcli.hosts.windows_step_export as step
        m=load();head='a'*40
        report=dict(source_commit=head,success=True,cleanup_errors=[],outputs=[dict(protocol=p,geometry=g,surface=s,path=str(i),sha256='b'*64) for i,(p,g,s) in enumerate(candidate.EXPECTED_OUTPUTS)])
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'writer.json';source.write_text(json.dumps(report))
            args=SimpleNamespace(output_dir=root,swconst=root/'swconst.tlb',export_report=source,sketch_readback_candidate=True)
            with mock.patch.object(windows,'_com_value',windows._com_value),mock.patch.object(step,'_native_windows_runtime',return_value=True),mock.patch.dict('os.environ',{'GITHUB_SHA':head}),mock.patch.object(m.harness,'run',return_value=0) as run:
                self.assertEqual(m.worker(args),0)
                self.assertEqual(run.call_args.kwargs['diagnostic_case'],'step-public-explicit-sketch-readback-candidate')
                self.assertEqual(len(run.call_args.kwargs['case_plan']),8)
            report['source_commit']='c'*40;source.write_text(json.dumps(report))
            with mock.patch.object(windows,'_com_value',windows._com_value),mock.patch.object(step,'_native_windows_runtime',return_value=True),mock.patch.dict('os.environ',{'GITHUB_SHA':head}),mock.patch.object(m.harness,'run') as run:
                with self.assertRaisesRegex(RuntimeError,'fresh same-head'):m.worker(args)
                run.assert_not_called()

    def test_candidate_non_native_platform_rejects_before_owned_host(self):
        import swcli.hosts.windows as windows
        import swcli.hosts.windows_step_export as step
        m=load()
        with tempfile.TemporaryDirectory() as d,mock.patch.object(windows,'_com_value',windows._com_value),mock.patch.object(step,'_native_windows_runtime',return_value=False),mock.patch.object(m.harness,'run') as run:
            args=SimpleNamespace(output_dir=Path(d),swconst=Path(d)/'swconst.tlb',export_report=Path(d)/'never-read.json',sketch_readback_candidate=True)
            with self.assertRaisesRegex(RuntimeError,'native Windows'):m.worker(args)
            run.assert_not_called()

    def test_successful_geometry_cannot_stay_green_if_preference_restore_fails(self):
        app,constants=pref_fixture();app.restore_fail='swImportFreeCurves';case={}
        with self.assertRaisesRegex(RuntimeError,'could not be restored'):
            with candidate.preferences(app,constants,call,case,lambda:None):case['success']=True
        self.assertFalse(case['success']);self.assertFalse(case['sketch_observer_preferences']['restored'])


class SketchRoundtripTests(unittest.TestCase):
    def run_roundtrip(self,*,kind='wireframe',load_error=0,save_error=0,reopen_error=0,reopen_readonly=True,
                      reopen_dirty=False,mutate_native=False,mutate_step=False,reopened_health=0,reopened_lengths=None,
                      null_candidate=False,null_dispid=227,neutral_free=False,initial_health=0,expected_loads=1,null_document=False,neutral_free_candidate=False,restore_fail=None):
        reader=load();app,constants=pref_fixture();app.LoadFile4=mock.Mock();app.CloseDoc=mock.Mock();app.GetDocumentCount=lambda:0
        values=wire_expected_lengths('wireframe' if kind=='solid-surface' else kind)
        first,_,_=document(values,code=initial_health);second,_,_=document(reopened_lengths or values,code=reopened_health)
        app.before['swImportNeutral_FreeCurvesAndPoints']=neutral_free;app.values=dict(app.before);app.restore_fail=restore_fail
        def load_file(path,arg,data,errors):errors.value=load_error;return None if null_document else first
        app.LoadFile4.side_effect=load_file
        observed=[];case={};live={'document':None}
        with tempfile.TemporaryDirectory() as d,ExitStack() as patches:
            output=Path(d);step=output/'wire.step';step.write_bytes(b'original STEP')
            saved=output/'wire-imported.SLDPRT'
            def save(path,document):Path(path).write_bytes(b'original native');return dict(ok=save_error==0,save_errors=save_error,save_warnings=None)
            def reopen(path,read_only,app):
                self.assertTrue(read_only)
                if mutate_native:saved.write_bytes(b'changed native')
                if mutate_step:step.write_bytes(b'changed STEP')
                return dict(ok=reopen_error==0,api_errors=reopen_error,api_warnings=0,read_only=reopen_readonly,document={'modified':reopen_dirty}),second
            patches.enter_context(mock.patch.dict(sys.modules,native_modules()))
            patches.enter_context(mock.patch.object(reader,'observe_dispatch',return_value=dict(returned=True,
                interfaces={'IImportStepData':dict(status='observed',value=True)},map_configuration_data=dict(status='observed',value=False))))
            raw_app=app;loader=None
            if null_candidate:
                from gate_support import step_null_sketch_readback_candidate as null_mode
                from test_step_null_binding import environment
                from test_step_explicit_null_binding import contract
                raw_app,mods,package=environment(null_mode.step_null_binding,target=app,unknown=True,wrapper='client')
                raw_app._lazydata_=None;raw_app._oleobj_.dispid=null_dispid;app.binding_raw=raw_app
                patches.enter_context(mock.patch.object(null_mode.step_null_binding,'modules',return_value=mods))
                proof=dict(binding_package=package,installed_invocation_contract=contract(),neutral_free_candidate=neutral_free_candidate)
                loader=lambda host,path,arg,data,errors:null_mode.load_model(host,path,arg,data,errors,call,case,lambda:None,verify,proof,neutral_free_candidate=neutral_free_candidate)
                case['public_output']=dict(path=str(step),sha256=hashlib.sha256(step.read_bytes()).hexdigest())
            if kind=='solid-surface':
                metrics=dict(solid_body_count=1,volume_mm3=12000.0,surface_area_mm2=3800.0,centroid_mm=dict(x=0.0,y=0.0,z=5.0))
                mass=dict(ok=True,method='native-body-mass-properties',metrics=metrics,bodies=[dict(index=0,**{k:v for k,v in metrics.items() if k!='solid_body_count'})])
                patches.enter_context(mock.patch.object(reader,'check_box',return_value=mass))
            patches.enter_context(mock.patch.object(reader,'save_as_native_windows',side_effect=save))
            patches.enter_context(mock.patch.object(reader,'open_windows_document_with_handle',side_effect=reopen))
            def wire(doc,e):observed.append(doc);return candidate.read_wireframe(reader,doc,e,call,kind)
            exception=None
            try:
                with candidate.preferences(raw_app,constants,call,case,lambda:None,neutral_free_candidate=neutral_free_candidate) as verify:
                    reader._verify_imported_geometry(raw_app,step,output,'wire',kind,constants,call,case,live,wire_reader=wire,before_load=verify,load_model=loader)
            except BaseException as exc:exception=exc
            self.assertEqual(app.LoadFile4.call_count,expected_loads)
            if restore_fail is None:
                self.assertEqual(app.values,app.before);self.assertTrue(case['sketch_observer_preferences']['restored'])
            return case,exception,len(observed),app,live

    def test_native_save_readonly_reopen_exact_vector_both_profiles_and_hashes(self):
        for kind in ('wireframe','wireframe-sketches'):
            with self.subTest(kind=kind):
                c,exc,reads,app,live=self.run_roundtrip(kind=kind)
                self.assertIsNone(exc);self.assertTrue(c['success']);self.assertEqual(reads,2)
                self.assertEqual(app.CloseDoc.call_count,2);self.assertIsNone(live['document'])
                self.assertEqual(c['imported_native_sha256'],hashlib.sha256(b'original native').hexdigest())
                self.assertIsNone(c['imported_save']['save_warnings'])

    def test_nonzero_import_save_reopen_error_and_not_readonly_stop_without_success(self):
        for options in ({'load_error':1},{'save_error':1},{'reopen_error':1},{'reopen_readonly':False},{'reopen_dirty':True}):
            with self.subTest(options=options):
                c,exc,reads,app,live=self.run_roundtrip(**options)
                self.assertIsNotNone(exc);self.assertFalse(c.get('success',False))
                self.assertIsNotNone(live['document'])  # Existing owned harness retains cleanup responsibility.

    def test_native_or_step_hash_change_on_reopen_is_rejected(self):
        for options in ({'mutate_native':True},{'mutate_step':True}):
            with self.subTest(options=options):
                c,exc,reads,app,live=self.run_roundtrip(**options)
                self.assertIsNotNone(exc);self.assertFalse(c.get('success',False));self.assertEqual(reads,2)

    def test_sketch_error_or_length_change_after_readonly_reopen_is_not_accepted(self):
        for options in ({'reopened_health':1},{'reopened_lengths':[10]*4+[30]*4+[41]*4}):
            with self.subTest(options=options):
                c,exc,reads,app,live=self.run_roundtrip(**options)
                self.assertIsNotNone(exc);self.assertFalse(c.get('success',False));self.assertEqual(reads,2)
                self.assertFalse(c['reopened_imported_geometry']['complete'])


if __name__=='__main__':unittest.main()
