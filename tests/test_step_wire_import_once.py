"""Portable single-import hypothesis traps. Never a native acceptance claim."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
TRAPS=('OpenDoc6','OpenDoc7','NewDocument','NewPart','SaveAs','SaveAs3','Save3','ExportToDWG2',
       'SelectByID2','Select2','ClearSelection2')


def load():
    spec=importlib.util.spec_from_file_location('step_once_test',ROOT/'scripts/ci/diagnose-step-wire-import-once.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


class Failure(Exception):
    def __init__(self,message='no host',hresult=0x800401E3-2**32):super().__init__(message);self.hresult=hresult


class Data:
    def __init__(self,failure=None,mapping_failure=None):
        self._oleobj_=SimpleNamespace(QueryInterface=mock.Mock(return_value=object(),side_effect=failure))
        self.mapping_reads=0;self.mapping_failure=mapping_failure
    @property
    def MapConfigurationData(self):
        self.mapping_reads+=1
        if self.mapping_failure:raise self.mapping_failure
        return False
    @MapConfigurationData.setter
    def MapConfigurationData(self,value):raise AssertionError('mapping write reached')


def document(kind='reference',lengths=None):
    lengths=[10]*4+[30]*4+[40]*4 if lengths is None else lengths
    if kind=='sketch':
        specific=SimpleNamespace(GetSketchSegments=[SimpleNamespace(GetLength=lambda value=value:value/1000) for value in lengths])
        type_name='3DProfileFeature'
    else:
        edges=[SimpleNamespace(GetCurve=SimpleNamespace(GetLength3=lambda low,high:high-low),
                GetCurveParams3=SimpleNamespace(UMinValue=0.0,UMaxValue=value/1000,Sense=True)) for value in lengths]
        specific=SimpleNamespace(GetSegmentCount=len(lengths),GetSegments=edges);type_name='ImportedCurve'
    feature=SimpleNamespace(GetID=1,GetTypeName2=type_name,Name='curve',GetSpecificFeature2=specific,
                            GetNextFeature=None,GetFirstSubFeature=None,GetNextSubFeature=None)
    doc=SimpleNamespace(GetType=1,GetTitle='ap203-wireframe.SLDPRT',GetPathName='',FirstFeature=feature,GetBodies2=lambda *args:())
    for name in TRAPS:setattr(doc,name,mock.Mock(side_effect=AssertionError(name)))
    return doc


class App:
    def __init__(self,module,*,partial_set=None,restore_fail=None,cas_drift=False,unowned_drift=False,
                 unknown_read=False,qi_failure=None,map_failure=None,load_failure=None,
                 load_error=0,null_document=False,kind='reference',lengths=None,close_failure=None,
                 refused_set=None,baseline_mismatch=False,foreign_restore=False):
        self.module=module;self.names=module.TOGGLES+module.INTEGERS
        self.ids={name:index for index,name in enumerate(self.names)}
        values=[True,True,False,True,False,False,0,0]
        self.before=dict(zip(self.names,values))
        if baseline_mismatch:self.before['swImportNeutral_CurvesAndPointsOption']=1
        self.values=dict(self.before)
        self.refused_set=refused_set;self.foreign_restore=foreign_restore
        self.partial_set=partial_set;self.restore_fail=restore_fail;self.cas_drift=cas_drift
        self.unowned_drift=unowned_drift;self.unknown_read=unknown_read;self.load_failure=load_failure
        self.load_error=load_error;self.null_document=null_document;self.close_failure=close_failure
        self.data=Data(qi_failure,map_failure);self.doc=document(kind,lengths);self.live=None
        self.reads=[];self.writes=[];self.data_calls=0;self.loads=[];self.closes=[];self.exits=0
        self.GetProcessID=73;self.RevisionNumber='33.5.0';self.StartupProcessCompleted=True;self.Visible=False
        for name in TRAPS:setattr(self,name,mock.Mock(side_effect=AssertionError('forbidden '+name)))
    def GetDocumentCount(self):return 1 if self.live is not None else 0
    def get(self,code):
        name=self.names[code];self.reads.append(name)
        if self.unknown_read:return None
        if self.cas_drift and len(self.reads)==17:self.values['swImportSolidSurface']=False
        return self.values[name]
    def GetUserPreferenceToggle(self,code):return self.get(code)
    def GetUserPreferenceIntegerValue(self,code):return self.get(code)
    def set(self,code,value):
        name=self.names[code];self.writes.append((name,value))
        if self.restore_fail==name and value==self.before[name]:raise Failure('restore failure',-2)
        self.values[name]=value
        if self.unowned_drift and name=='swImportFreeCurves' and value is True:self.values['swImportStepConfigData']=True
        if self.partial_set==name and value!=self.before[name]:raise Failure('first partial setter error',-3)
    def SetUserPreferenceToggle(self,code,value):self.set(code,value)
    def SetUserPreferenceIntegerValue(self,code,value):
        self.set(code,value)
        return False if self.names[code]==self.refused_set and value!=self.before[self.names[code]] else True
    def GetImportFileData(self,path):self.data_calls+=1;return self.data
    def LoadFile4(self,path,args,data,errors):
        self.loads.append((path,args,data));errors.value=self.load_error
        if self.foreign_restore:
            key=self.foreign_restore if isinstance(self.foreign_restore,str) else 'swImportCurvePreference'
            self.values[key]=2
        if self.load_failure:raise self.load_failure
        self.live=None if self.null_document else self.doc
        return self.live
    def CloseDoc(self,title):
        self.closes.append(title)
        if self.close_failure:raise self.close_failure
        self.live=None
    def ExitApp(self):self.exits+=1;self.live=None


class StepWireImportOnceTests(unittest.TestCase):
    def run_case(self,**options):
        neutral_3d_candidate=options.pop('neutral_3d_candidate',False)
        neutral_enum_values=options.pop('neutral_enum_values',(0,1))
        m=load();app=App(m,**options)
        const={**app.ids,'swGeneralImportAsSketches':0,'swGeneralImportAs3dCurves':1,
               'swImportNeutralCurvesAndPointsOptions_AsSketches':neutral_enum_values[0],
               'swImportNeutralCurvesAndPointsOptions_As3DCurves':neutral_enum_values[1]}
        class Variant:
            def __init__(self,kind,value):self.value=value
        client=SimpleNamespace(GetActiveObject=mock.Mock(side_effect=Failure()),DispatchEx=mock.Mock(return_value=app),VARIANT=Variant)
        info=SimpleNamespace(GetDocumentation=lambda *args:('IImportStepData',),GetTypeAttr=lambda:(m.STEP_IID,))
        com=SimpleNamespace(CoInitialize=mock.Mock(),CoUninitialize=mock.Mock(),LoadTypeLib=lambda path:SimpleNamespace(GetTypeInfoOfGuid=lambda iid:info),
                            IID_IUnknown='safe-wrapper',VT_BYREF=1,VT_I4=2,com_error=Failure)
        meta=dict(path=m.INPUT,sha256=m.INPUT_SHA,readonly=True,metadata={'attributes':1},original_source=m.SOURCE)
        handle=SimpleNamespace(Close=mock.Mock())
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();output=root/'out';output.mkdir();swconst=root/'swconst.tlb';swconst.write_bytes(b'constants');(root/'sldworks.tlb').write_bytes(b'library')
            hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (swconst,root/'sldworks.tlb')}
            with mock.patch.object(m,'_native_windows_runtime',return_value=True),mock.patch.object(m.importlib.metadata,'version',return_value='312'), \
                    mock.patch.object(m,'input_metadata',return_value=meta),mock.patch.object(m,'LIBRARY_HASHES',hashes), \
                    mock.patch.object(m,'native_pids',return_value=[]),mock.patch.object(m,'_read_native_enum_constants',return_value=const), \
                    mock.patch.object(m.harness,'capture_process',return_value=handle),mock.patch.object(m.harness,'wait_process') as wait, \
                    mock.patch.dict('sys.modules',{'pythoncom':com,'win32com':SimpleNamespace(client=client),'win32com.client':client}):
                result=m.worker(SimpleNamespace(output_dir=output,swconst=swconst,neutral_3d_candidate=neutral_3d_candidate))
            report=json.loads((output/'report.json').read_text());trace=[json.loads(x) for x in (output/'trace.jsonl').read_text().splitlines()]
            waits=wait.call_count
        for name in TRAPS:getattr(app,name).assert_not_called();getattr(app.doc,name).assert_not_called()
        self.assertEqual(app.exits,1);self.assertEqual(waits,1);handle.Close.assert_called_once();com.CoUninitialize.assert_called_once()
        self.assertFalse(report['production_public_acceptance']);self.assertFalse(report['full_acceptance_eligible'])
        return m,app,result,report,trace

    def test_success_exact_staged_profile_single_bit_load_and_only_owned_restore(self):
        m,app,code,r,trace=self.run_case()
        self.assertEqual(code,0);self.assertTrue(r['success']);self.assertEqual(app.values,app.before)
        c=r['cases'][0];p=c['preferences'];self.assertTrue(p['restored'])
        ci=p['ci_general_readback'];candidate=p['candidate_readback']
        self.assertEqual([k for k in ci if ci[k]!=candidate[k]],['swImportNeutral_FreeCurvesAndPoints'])
        self.assertEqual((ci['swMultiCAD_Enable3DInterconnect'],ci['swImportFreeCurves'],ci['swImportCurvePreference'],ci['swImportNeutral_CurvesAndPointsOption']),(False,True,1,0))
        owned=[x['name'] for x in p['writes']]
        self.assertEqual(owned,['swMultiCAD_Enable3DInterconnect','swImportFreeCurves','swImportCurvePreference','swImportNeutral_FreeCurvesAndPoints'])
        self.assertEqual([x['name'] for x in p['restore']],list(reversed(owned)))
        self.assertTrue(all(x['status']=='verified' and 'readback' in x for x in p['writes']+p['restore']))
        self.assertEqual(len(app.loads),1);self.assertEqual(app.data_calls,1)
        self.assertEqual(app.loads[0],(m.INPUT,'r',app.data));self.assertEqual(app.data.mapping_reads,1)
        app.data._oleobj_.QueryInterface.assert_called_once_with(m.STEP_IID,'safe-wrapper')
        self.assertEqual(c['geometry']['value']['segment_count'],12);self.assertEqual(c['geometry']['value']['total_length_mm'],320)
        self.assertEqual(len(app.closes),1)
        self.assertEqual(len([x for x in trace if x['phase']=='begin' and x['call']=='LoadFile4']),1)

    def test_partial_setter_exception_restores_attempted_field_and_preserves_first_error(self):
        m,app,code,r,_=self.run_case(partial_set='swMultiCAD_Enable3DInterconnect')
        self.assertEqual(code,1);self.assertEqual(r['failure']['message'],'first partial setter error')
        self.assertEqual(app.values,app.before);self.assertEqual(app.loads,[]);self.assertEqual(app.data_calls,0)
        p=r['cases'][0]['preferences'];self.assertEqual(len(p['writes']),1);self.assertEqual(p['writes'][0]['status'],'failed')
        self.assertTrue(p['writes'][0]['possible_mutation']);self.assertTrue(p['restored'])
        self.assertEqual(app.writes,[('swMultiCAD_Enable3DInterconnect',False),('swMultiCAD_Enable3DInterconnect',True)])

    def test_original_unknown_and_complete_cas_conflict_do_not_write_or_import(self):
        for kwargs in ({'unknown_read':True},{'cas_drift':True}):
            with self.subTest(kwargs=kwargs):
                m,app,code,r,_=self.run_case(**kwargs)
                self.assertEqual(code,1);self.assertEqual(app.writes,[]);self.assertEqual(app.loads,[]);self.assertEqual(app.data_calls,0)
                self.assertIsNone(r['cases'][0]['preferences']['restored'])
                if kwargs.get('unknown_read'):
                    self.assertEqual(len(app.reads),1)
                    self.assertIsNone(r['cases'][0]['preferences']['reads'][0]['value'])

    def test_unowned_readback_drift_is_retained_never_repaired(self):
        m,app,code,r,_=self.run_case(unowned_drift=True)
        self.assertEqual(code,1);self.assertIn('readback mismatch',r['failure']['message'])
        self.assertTrue(app.values['swImportStepConfigData']);self.assertFalse(r['cases'][0]['preferences']['restored'])
        self.assertNotIn('swImportStepConfigData',[x[0] for x in app.writes]);self.assertEqual(app.loads,[])
        self.assertTrue(r['cases'][0]['preferences']['restore_errors'])

    def test_qi_or_mapping_unknown_stops_and_restores_without_load_retry(self):
        for options in ({'qi_failure':TypeError('unknown QI')},{'map_failure':Failure('unknown map',-5)}):
            with self.subTest(options=options):
                m,app,code,r,_=self.run_case(**options)
                self.assertEqual(code,1);self.assertEqual(app.loads,[]);self.assertEqual(app.data_calls,1)
                app.data._oleobj_.QueryInterface.assert_called_once();self.assertEqual(app.values,app.before)
                self.assertEqual(app.data.mapping_reads,0 if 'qi_failure' in options else 1)
                self.assertIsNone(r['cases'][0]['geometry']['value']);self.assertEqual(r['cases'][0]['geometry']['status'],'unavailable')

    def test_none_error1_keeps_native_values_and_geometry_unavailable(self):
        m,app,code,r,_=self.run_case(load_error=1,null_document=True)
        self.assertEqual(code,1);self.assertEqual(r['failure']['message'],'STEP geometry readback failed')
        c=r['cases'][0];self.assertFalse(c['load_return']['document_returned']);self.assertEqual(c['load_return']['errors'],1)
        self.assertEqual(c['geometry'],{'status':'unavailable','value':None});self.assertEqual(len(app.loads),1)
        self.assertEqual(app.closes,[]);self.assertEqual(app.values,app.before)

    def test_returned_model_with_error_and_close_error_preserves_first_failure(self):
        m,app,code,r,_=self.run_case(load_error=1,close_failure=Failure('close failed',-7))
        self.assertEqual(code,1);self.assertEqual(r['failure']['message'],'STEP geometry readback failed')
        self.assertEqual(len(app.loads),1);self.assertEqual(len(app.closes),1);self.assertEqual(app.values,app.before)
        self.assertTrue(r['cases'][0]['load_return']['document_returned'])
        self.assertEqual(r['cleanup_errors'][0]['stage'],'CloseDoc')

    def test_native_exception_and_restore_failure_do_not_replace_original_error(self):
        m,app,code,r,_=self.run_case(load_failure=Failure('first LoadFile4 failure',-8),restore_fail='swImportCurvePreference')
        self.assertEqual(code,1);self.assertEqual(r['failure']['message'],'first LoadFile4 failure')
        c=r['cases'][0];self.assertEqual(c['load_return']['state'],'raised');self.assertEqual(len(app.loads),1)
        self.assertIsNone(c['geometry']['value']);self.assertFalse(c['preferences']['restored']);self.assertTrue(c['preferences']['restore_errors'])
        restores=[value for name,value in app.writes if name=='swImportCurvePreference' and value==0]
        self.assertEqual(len(restores),1)

    def test_wrong_representation_or_geometry_is_strict_failure_with_raw_partial_evidence(self):
        for options in ({'kind':'sketch'},{'lengths':[10]*4+[30]*3+[40]*2},{'lengths':[10]*4+[30]*4+[41]*4}):
            with self.subTest(options=options):
                m,app,code,r,_=self.run_case(**options)
                self.assertEqual(code,1);g=r['cases'][0]['geometry'];self.assertEqual(g['status'],'unavailable');self.assertIsNone(g['value'])
                self.assertIn('segment_count',g['raw_observation']);self.assertEqual(len(app.loads),1);self.assertEqual(app.values,app.before)
                self.assertEqual(len(app.closes),1)
                if options.get('kind')=='sketch':
                    self.assertEqual(g['raw_observation']['segment_count'],12);self.assertEqual(g['raw_observation']['total_length_mm'],320)
                    self.assertTrue(g['raw_observation']['representation_mismatches'])

    def test_controller_blocks_unowned_setters_duplicate_data_load_and_foreign_close(self):
        m=load();raw=mock.Mock();const={n:i for i,n in enumerate(m.TOGGLES+m.INTEGERS)};app=m.ImportOnceApp(raw,const)
        with self.assertRaises(RuntimeError):app.SetUserPreferenceIntegerValue(const['swImportNeutral_CurvesAndPointsOption'],1)
        with self.assertRaises(RuntimeError):app.SetUserPreferenceToggle(const['swImportStepConfigData'],True)
        raw.SetUserPreferenceIntegerValue.assert_not_called();raw.SetUserPreferenceToggle.assert_not_called()
        data=app.GetImportFileData(m.INPUT)
        with self.assertRaises(RuntimeError):app.GetImportFileData(m.INPUT)
        with self.assertRaises(RuntimeError):app.LoadFile4(m.INPUT,'',data,object())
        with self.assertRaises(RuntimeError):app.LoadFile4(m.INPUT,'r',None,object())
        raw.LoadFile4.assert_not_called()
        with self.assertRaises(RuntimeError):app.CloseDoc('foreign document')
        app.LoadFile4(m.INPUT,'r',data,object())
        with self.assertRaises(RuntimeError):app.LoadFile4(m.INPUT,'r',data,object())
        raw.LoadFile4.assert_called_once()
        for name in TRAPS:
            with self.assertRaises(RuntimeError):getattr(app,name)


    def test_last_candidate_partial_setter_and_refused_integer_restore_without_load(self):
        for options in ({'partial_set':'swImportNeutral_FreeCurvesAndPoints'},
                        {'refused_set':'swImportCurvePreference'}):
            with self.subTest(options=options):
                _,app,code,r,_=self.run_case(**options)
                self.assertEqual(code,1);self.assertEqual(app.loads,[]);self.assertEqual(app.data_calls,0)
                self.assertEqual(app.values,app.before)
                p=r['cases'][0]['preferences'];self.assertTrue(p['restored'])
                self.assertEqual(p['writes'][-1]['status'],'failed')
                self.assertTrue(p['writes'][-1]['possible_mutation'])

    def test_unreviewed_initial_neutral_mode_stops_without_normalization(self):
        _,app,code,r,_=self.run_case(baseline_mismatch=True)
        self.assertEqual(code,1);self.assertEqual(app.writes,[]);self.assertEqual(app.data_calls,0)
        self.assertIn('no normalization',r['failure']['message'])
        self.assertIsNone(r['cases'][0]['preferences']['restored'])

    def test_foreign_owned_value_is_retained_without_overwriting_on_restore(self):
        _,app,code,r,_=self.run_case(foreign_restore=True,load_error=1,null_document=True)
        self.assertEqual(code,1);self.assertEqual(r['failure']['message'],'STEP geometry readback failed')
        self.assertEqual(app.values['swImportCurvePreference'],2)
        self.assertEqual([v for n,v in app.writes if n=='swImportCurvePreference'],[1])
        p=r['cases'][0]['preferences'];self.assertFalse(p['restored'])
        self.assertTrue(any('changed externally' in e['message'] for e in p['restore_errors']))
        self.assertEqual(len(app.loads),1)

    def test_supervisor_preserves_first_report_and_bounds_all_trace_channels(self):
        for channel,group in [('trace.jsonl',False),('observation-trace.jsonl',False),
                              ('partial-acquisition-trace.jsonl',False),('trace.jsonl',True)]:
            with self.subTest(channel=channel,group=group), tempfile.TemporaryDirectory() as directory:
                m=load();root=Path(directory).resolve();output=root/'new'
                process=mock.Mock();process.poll.return_value=None
                def start(*args,**kwargs):
                    (output/channel).write_text(json.dumps(dict(call='blocked-native',phase='begin',time=1))+'\n')
                    (output/'report.json').write_text(json.dumps({'failure':{'message':'original failure'}}))
                    return process
                with mock.patch.object(m,'EVIDENCE_ROOT',str(root)),mock.patch.object(m.subprocess,'Popen',side_effect=start), \
                        mock.patch.object(m.time,'monotonic',side_effect=[0,1800 if group else 1]), \
                        mock.patch.object(m.time,'time',return_value=701),mock.patch.object(m.time,'sleep'):
                    self.assertEqual(m.main(['--output-dir',str(output)]),124)
                self.assertEqual(json.loads((output/'report.json').read_text())['failure']['message'],'original failure')
                self.assertEqual(json.loads((output/'timeout.json').read_text())['owned_exit'],'unknown; root cleanup required')
                process.kill.assert_called_once();process.wait.assert_called_once()


    def test_neutral_3d_candidate_changes_only_official_enum_without_importing_previous_vector(self):
        m,app,code,r,trace=self.run_case(neutral_3d_candidate=True)
        self.assertEqual(code,0);self.assertEqual(r['diagnostic_case'],'step-wire-neutral-3d-once')
        self.assertTrue(r['neutral_3d_candidate']);self.assertEqual(app.values,app.before)
        p=r['cases'][0]['preferences'];before=p['d232e35_vector_readback'];after=p['candidate_readback']
        key='swImportNeutral_CurvesAndPointsOption'
        self.assertEqual(p['changed_from_d232e35'],[key]);self.assertEqual([k for k in before if before[k]!=after[k]],[key])
        self.assertEqual((before[key],after[key]),(0,1));self.assertTrue(before['swImportNeutral_FreeCurvesAndPoints'])
        self.assertEqual(after[key],r['constants']['swImportNeutralCurvesAndPointsOptions_As3DCurves'])
        self.assertEqual([x['name'] for x in p['writes']],['swMultiCAD_Enable3DInterconnect','swImportFreeCurves',
            'swImportCurvePreference','swImportNeutral_FreeCurvesAndPoints',key])
        self.assertEqual([x['name'] for x in p['restore']],[x['name'] for x in p['writes']][::-1])
        self.assertTrue(p['restored']);self.assertEqual(app.loads,[(m.INPUT,'r',app.data)])
        self.assertEqual(app.data_calls,1);self.assertEqual(app.data.mapping_reads,1)
        app.data._oleobj_.QueryInterface.assert_called_once()
        begin=[x['call'] for x in trace if x['phase']=='begin']
        self.assertLess(begin.index('set-owned-option.'+key),begin.index('GetImportFileData'))
        self.assertEqual(begin.count('LoadFile4'),1)
        self.assertEqual(r['cases'][0]['geometry']['value']['segment_count'],12)

    def test_neutral_3d_candidate_partial_refusal_and_restore_failure_keep_first_error(self):
        key='swImportNeutral_CurvesAndPointsOption'
        for options in ({'partial_set':key},{'refused_set':key},
                        {'restore_fail':key,'load_failure':Failure('original load error',-8)}):
            with self.subTest(options=options):
                _,app,code,r,_=self.run_case(neutral_3d_candidate=True,**options)
                self.assertEqual(code,1);p=r['cases'][0]['preferences']
                self.assertEqual(p['writes'][-1]['name'],key)
                if 'restore_fail' in options:
                    self.assertFalse(p['restored']);self.assertEqual(len(app.loads),1)
                    self.assertEqual(r['failure']['message'],'original load error')
                else:
                    self.assertTrue(p['restored']);self.assertEqual(app.values,app.before)
                    self.assertEqual(app.data_calls,0);self.assertEqual(app.loads,[])
                self.assertEqual(len([x for x in app.writes if x==(key,0)]),1)

    def test_neutral_3d_candidate_keeps_sketch_and_bad_geometry_strictly_rejected(self):
        for options in ({'kind':'sketch'},{'lengths':[10]*4+[30]*3+[40]*2},
                        {'lengths':[10]*4+[30]*4+[41]*4},{'null_document':True,'load_error':1}):
            with self.subTest(options=options):
                _,app,code,r,_=self.run_case(neutral_3d_candidate=True,**options)
                self.assertEqual(code,1);self.assertEqual(len(app.loads),1)
                self.assertEqual(app.values,app.before);g=r['cases'][0]['geometry']
                self.assertEqual(g['status'],'unavailable');self.assertIsNone(g['value'])
                if options.get('kind')=='sketch':
                    self.assertEqual(g['raw_observation']['segment_count'],12)
                    self.assertEqual(g['raw_observation']['total_length_mm'],320)
                    self.assertTrue(g['raw_observation']['representation_mismatches'])

    def test_candidate_supervisor_forwards_explicit_mode_with_new_evidence_root(self):
        with tempfile.TemporaryDirectory() as directory:
            m=load();root=Path(directory).resolve();output=root/'new'
            process=mock.Mock();process.poll.return_value=None
            def start(command,**kwargs):
                self.assertEqual(command.count('--neutral-3d-candidate'),1)
                self.assertIn('--worker',command)
                return process
            with mock.patch.object(m,'NEUTRAL_3D_EVIDENCE_ROOT',str(root)), \
                    mock.patch.object(m.subprocess,'Popen',side_effect=start), \
                    mock.patch.object(m.time,'monotonic',side_effect=[0,1800]),mock.patch.object(m.time,'sleep'):
                self.assertEqual(m.main(['--output-dir',str(output),'--neutral-3d-candidate']),124)
            process.kill.assert_called_once();process.wait.assert_called_once()


    def test_candidate_unknown_official_enum_stops_before_any_setter_or_data(self):
        for values in ((0,2),(False,True),(0,None)):
            with self.subTest(values=values):
                _,app,code,r,_=self.run_case(neutral_3d_candidate=True,neutral_enum_values=values)
                self.assertEqual(code,1);self.assertEqual(app.writes,[]);self.assertEqual(app.data_calls,0)
                self.assertEqual(app.loads,[]);self.assertIn('enum contract differs',r['failure']['message'])

    def test_candidate_does_not_overwrite_foreign_neutral_enum_on_cleanup(self):
        key='swImportNeutral_CurvesAndPointsOption'
        _,app,code,r,_=self.run_case(neutral_3d_candidate=True,foreign_restore=key,load_error=1,null_document=True)
        self.assertEqual(code,1);self.assertEqual(app.values[key],2)
        self.assertEqual([v for n,v in app.writes if n==key],[1])
        self.assertEqual(r['failure']['message'],'STEP geometry readback failed')
        self.assertFalse(r['cases'][0]['preferences']['restored'])
        self.assertEqual(len(app.loads),1)
