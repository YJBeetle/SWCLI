"""Zero-CAD portable traps for the root-only fixed-input metadata probe."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN=('LoadFile4','OpenDoc6','OpenDoc7','NewDocument','NewPart','SaveAs','SaveAs3','Save3',
           'SelectByID2','Select2','ClearSelection2','SetUserPreferenceToggle','SetUserPreferenceIntegerValue')


def load():
    spec=importlib.util.spec_from_file_location('step_data_only',ROOT/'scripts/ci/diagnose-step-import-data.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class ComError(Exception):
    def __init__(self,message='no active host',hresult=0x800401E3-2**32):
        super().__init__(message);self.hresult=hresult


class Data:
    def __init__(self,qi_failure=None,mapping_failure=None):
        self._oleobj_=SimpleNamespace(QueryInterface=mock.Mock(side_effect=qi_failure,return_value=object()))
        self.mapping_reads=0;self.mapping_failure=mapping_failure
    @property
    def MapConfigurationData(self):
        self.mapping_reads+=1
        if self.mapping_failure:raise self.mapping_failure
        return False
    @MapConfigurationData.setter
    def MapConfigurationData(self,value):
        raise AssertionError('MapConfigurationData setter reached')


class StepImportDataOnlyTests(unittest.TestCase):
    def run_worker(self,*,qi_failure=None,mapping_failure=None,data_failure=None,bad_preference=False,
                   existing=False,rot_failure=None,configure_failure=None,exit_failure=None,bad_library=False,wrong_iid=False,input_failure=None,wrong_library_name=False):
        module=load();events=[];data=Data(qi_failure,mapping_failure)
        app=SimpleNamespace(GetDocumentCount=mock.Mock(spec=lambda:None,return_value=0),GetProcessID=42,RevisionNumber='33.5.0',
                            StartupProcessCompleted=True,Visible=False,
                            GetUserPreferenceToggle=mock.Mock(return_value='unknown' if bad_preference else False),
                            GetUserPreferenceIntegerValue=mock.Mock(return_value=0),
                            GetImportFileData=mock.Mock(side_effect=data_failure,return_value=data))
        for name in FORBIDDEN:setattr(app,name,mock.Mock(side_effect=AssertionError('forbidden '+name)))
        def exit_host():
            events.append('ExitApp')
            if exit_failure:raise exit_failure
        app.ExitApp=mock.Mock(spec=lambda:None,side_effect=exit_host)
        client=SimpleNamespace(GetActiveObject=mock.Mock(side_effect=rot_failure or ComError()),DispatchEx=mock.Mock(return_value=app))
        info=SimpleNamespace(GetDocumentation=lambda index:('WrongData' if wrong_iid else 'IImportStepData',),GetTypeAttr=lambda:(module.STEP_IID,))
        library=SimpleNamespace(GetTypeInfoOfGuid=mock.Mock(return_value=info))
        pythoncom=SimpleNamespace(CoInitialize=mock.Mock(),CoUninitialize=mock.Mock(side_effect=lambda:events.append('CoUninitialize')),
                                 LoadTypeLib=mock.Mock(return_value=library),IID_IUnknown='safe-IUnknown',com_error=ComError)
        handle=SimpleNamespace(Close=mock.Mock())
        metadata=dict(path=module.INPUT,sha256=module.INPUT_SHA,readonly=True,metadata={'attributes':1},original_source=module.SOURCE)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();output=root/'out';output.mkdir();swconst=root/'swconst.tlb';swconst.write_bytes(b'constants')
            (root/'sldworks.tlb').write_bytes(b'library')
            hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (swconst,root/'sldworks.tlb')}
            if bad_library:hashes['sldworks.tlb']='0'*64
            with mock.patch.object(module,'_native_windows_runtime',return_value=True), \
                    mock.patch.object(module.importlib.metadata,'version',return_value='312'), \
                    mock.patch.object(module,'input_metadata',return_value=metadata,side_effect=input_failure), \
                    mock.patch.object(module,'LIBRARY_HASHES',hashes), \
                    mock.patch.object(module,'native_pids',return_value=[999] if existing else []), \
                    mock.patch.object(module,'_read_native_enum_constants',return_value={n:i for i,n in enumerate(module.TOGGLES+module.INTEGERS)}), \
                    mock.patch.object(module.harness,'capture_process',return_value=handle), \
                    mock.patch.object(module.harness,'wait_process',side_effect=lambda h:events.append('WaitForOwnedProcess')), \
                    mock.patch.dict('sys.modules',{'pythoncom':pythoncom,'win32com':SimpleNamespace(client=client),'win32com.client':client}), \
                    mock.patch('swcli.daemon.server.configure_resident_app',side_effect=configure_failure):
                code=module.worker(SimpleNamespace(output_dir=output,swconst=swconst.with_name('other.tlb') if wrong_library_name else swconst))
            report=json.loads((output/'report.json').read_text())
            if configure_failure:
                self.assertEqual(json.loads((output/'partial-owned-host.json').read_text()),{'process_id':42,'owned_by_probe':True})
            trace=[json.loads(x) for filename in ('trace.jsonl','observation-trace.jsonl','partial-acquisition-trace.jsonl') if (output/filename).exists() for x in (output/filename).read_text().splitlines()]
        for name in FORBIDDEN:getattr(app,name).assert_not_called()
        self.assertFalse(report['production_public_acceptance'])
        return code,report,app,data,client,pythoncom,events,trace,library

    def test_success_has_exact8_reads_one_data_one_step_qi_one_mapping_and_owned_exit(self):
        code,r,app,data,client,com,events,trace,library=self.run_worker()
        self.assertEqual(code,0);self.assertTrue(r['success'])
        self.assertEqual(app.GetUserPreferenceToggle.call_count,6);self.assertEqual(app.GetUserPreferenceIntegerValue.call_count,2)
        app.GetImportFileData.assert_called_once_with(load().INPUT)
        data._oleobj_.QueryInterface.assert_called_once_with(load().STEP_IID,'safe-IUnknown')
        self.assertEqual(data.mapping_reads,1)
        client.GetActiveObject.assert_called_once();client.DispatchEx.assert_called_once()
        library.GetTypeInfoOfGuid.assert_called_once_with(load().STEP_IID)
        app.ExitApp.assert_called_once();com.CoUninitialize.assert_called_once()
        self.assertEqual(events,['ExitApp','WaitForOwnedProcess','CoUninitialize'])
        self.assertEqual(r['input_final'],r['input']);self.assertEqual(r['remaining_native_pids'],[])
        self.assertEqual(r['cleanup_errors'],[])
        self.assertEqual(len([x for x in trace if x['phase']=='begin' and x['call']=='GetImportFileData']),1)

    def test_unknown_preference_stops_before_other_preferences_or_data(self):
        code,r,app,data,client,com,*_=self.run_worker(bad_preference=True)
        self.assertEqual(code,1);self.assertIn('unknown/invalid',r['failure']['message'])
        self.assertEqual(app.GetUserPreferenceToggle.call_count,1);app.GetUserPreferenceIntegerValue.assert_not_called()
        app.GetImportFileData.assert_not_called();data._oleobj_.QueryInterface.assert_not_called()
        self.assertEqual(data.mapping_reads,0);app.ExitApp.assert_called_once()

    def test_first_data_error_is_preserved_without_query_or_retry(self):
        code,r,app,data,*_=self.run_worker(data_failure=ComError('first factory error',-1))
        self.assertEqual(code,1);self.assertEqual(r['failure']['message'],'first factory error')
        app.GetImportFileData.assert_called_once();data._oleobj_.QueryInterface.assert_not_called()
        self.assertEqual(data.mapping_reads,0);app.ExitApp.assert_called_once()

    def test_qi_refusal_or_unknown_stops_before_mapping_and_cleanup_cannot_cover_it(self):
        for failure in (ComError('QI refused',-2147467262),TypeError('unregistered wrapper')):
            with self.subTest(failure=str(failure)):
                code,r,app,data,*_=self.run_worker(qi_failure=failure,exit_failure=RuntimeError('cleanup failure'))
                self.assertEqual(code,1);self.assertEqual(r['failure']['message'],str(failure))
                app.GetImportFileData.assert_called_once();data._oleobj_.QueryInterface.assert_called_once()
                self.assertEqual(data.mapping_reads,0);app.ExitApp.assert_called_once()
                self.assertEqual(r['cleanup_errors'][0]['stage'],'ExitApp')
                self.assertEqual(r['cases'][0]['IImportStepData.QueryInterface']['status'],'observed' if isinstance(failure,ComError) else 'unknown')

    def test_mapping_unknown_is_single_read_and_stops_without_native_work(self):
        code,r,app,data,*_=self.run_worker(mapping_failure=RuntimeError('unknown mapping'))
        self.assertEqual(code,1);self.assertEqual(r['failure']['message'],'unknown mapping')
        self.assertEqual(data.mapping_reads,1);data._oleobj_.QueryInterface.assert_called_once()
        app.GetImportFileData.assert_called_once();app.ExitApp.assert_called_once()

    def test_process_or_unknown_rot_guard_prevents_activation(self):
        for kwargs in ({'existing':True},{'rot_failure':ComError('unknown ROT',-1)}):
            with self.subTest(kwargs=kwargs):
                code,r,app,data,client,com,*_=self.run_worker(**kwargs)
                self.assertEqual(code,1);client.DispatchEx.assert_not_called()
                app.GetImportFileData.assert_not_called();data._oleobj_.QueryInterface.assert_not_called();app.ExitApp.assert_not_called()
                if 'rot_failure' in kwargs:self.assertEqual(r['failure']['message'],'unknown ROT')

    def test_partial_acquisition_configuration_error_is_cleaned_before_com_uninitialize(self):
        code,r,app,data,client,com,events,trace,_=self.run_worker(configure_failure=RuntimeError('first config failure'))
        self.assertEqual(code,1);self.assertEqual(r['failure']['message'],'first config failure')
        app.GetImportFileData.assert_not_called();client.DispatchEx.assert_called_once();app.ExitApp.assert_called_once()
        self.assertEqual(events,['ExitApp','WaitForOwnedProcess','CoUninitialize'])
        self.assertEqual(r['partial_acquisition_first_failure']['message'],'first config failure')
        self.assertTrue(any(x['call']=='partial-acquire.WaitForOwnedProcess' and x['phase']=='end' for x in trace))

    def test_readonly_proxy_denies_import_save_open_new_selection_and_setters(self):
        module=load();raw=mock.Mock();proxy=module.ReadOnlyApp(raw)
        for name in FORBIDDEN:
            with self.subTest(name=name),self.assertRaisesRegex(RuntimeError,'Forbidden'):getattr(proxy,name)
        self.assertEqual(raw.mock_calls,[])
        with self.assertRaises(RuntimeError):proxy.Visible=True

    def test_input_requires_existing_readonly_attribute_hash_and_original_metadata(self):
        module=load()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory).resolve()/'ap203-wireframe.step';path.write_bytes(b'fixed fixture')
            original_stat=type(path).stat
            for attributes,expected_hash,success in ((1,hashlib.sha256(path.read_bytes()).hexdigest(),True),(0,'bad',False),(1,'bad',False)):
                def metadata_stat(item,*args,**kwargs):
                    st=original_stat(item,*args,**kwargs)
                    if item!=path:return st
                    return SimpleNamespace(st_mode=st.st_mode,st_size=st.st_size,st_dev=st.st_dev,st_ino=st.st_ino,
                                           st_mtime_ns=st.st_mtime_ns,st_ctime_ns=st.st_ctime_ns,st_file_attributes=attributes)
                with self.subTest(attributes=attributes,hash=expected_hash),mock.patch.object(module,'INPUT',str(path)), \
                        mock.patch.object(module,'INPUT_SHA',expected_hash),mock.patch.object(type(path),'stat',metadata_stat):
                    if success:
                        value=module.input_metadata();self.assertTrue(value['readonly']);self.assertEqual(value['original_source'],module.SOURCE)
                    else:
                        with self.assertRaises(RuntimeError):module.input_metadata()

    def test_unchanged600_and1800_watchdogs_record_timeout_without_replacing_first_failure(self):
        for group,channel in ((True,'trace.jsonl'),(False,'trace.jsonl'),(False,'observation-trace.jsonl'),(False,'partial-acquisition-trace.jsonl')):
            module=load()
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory).resolve();output=root/'new'
                process=SimpleNamespace(poll=mock.Mock(return_value=None),kill=mock.Mock(),wait=mock.Mock())
                def start(*args,**kwargs):
                    (output/'report.json').write_text('{"failure":{"message":"original failure"}}')
                    (output/channel).write_text('' if group else '{"call":"GetImportFileData","phase":"begin","time":100}\n')
                    return process
                with mock.patch.object(module,'EVIDENCE_ROOT',str(root)),mock.patch.object(module.subprocess,'Popen',side_effect=start), \
                        mock.patch.object(module.time,'monotonic',side_effect=[0,1800 if group else 1]), \
                        mock.patch.object(module.time,'time',return_value=701),mock.patch.object(module.time,'sleep'):
                    self.assertEqual(module.main(['--output-dir',str(output)]),124)
                self.assertEqual(json.loads((output/'report.json').read_text())['failure']['message'],'original failure')
                self.assertEqual(json.loads((output/'timeout.json').read_text())['owned_exit'],'unknown; root cleanup required')
                process.kill.assert_called_once();process.wait.assert_called_once()

    def test_metadata_library_or_iid_failure_prevents_any_host_activation(self):
        for kwargs in ({'bad_library':True},{'wrong_iid':True},{'input_failure':RuntimeError('readonly guard failed')},{'wrong_library_name':True}):
            with self.subTest(kwargs=kwargs):
                code,r,app,data,client,*_=self.run_worker(**kwargs)
                self.assertEqual(code,1)
                client.GetActiveObject.assert_not_called();client.DispatchEx.assert_not_called()
                app.GetImportFileData.assert_not_called();data._oleobj_.QueryInterface.assert_not_called()
                app.ExitApp.assert_not_called()
