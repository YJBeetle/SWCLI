"""Portable traps for a proposed local diagnostic; no native acceptance."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from zipfile import ZipFile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'scripts/diagnostics/glb-visible-host-control.py'
if not DRIVER.exists():
    DRIVER = Path(__file__).with_name('glb-visible-host-control.py')
spec = importlib.util.spec_from_file_location('glb_visible_control', DRIVER)
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class Document:
    def __init__(self, path):
        self.path = str(path)
        self.stamp = 7
        self.ConfigurationManager = SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name='默认'))
        self.SketchManager = SimpleNamespace(ActiveSketch=None)
    def GetType(self): return 1
    def GetUpdateStamp(self): return self.stamp
    def GetSaveFlag(self): return False
    def GetPathName(self): return self.path
    def GetTitle(self): return 'component.SLDPRT'
    def IsOpenedReadOnly(self): return False


class ReadOnlyApp:
    def __init__(self, document):
        object.__setattr__(self, 'ActiveDoc', document)
        object.__setattr__(self, 'Visible', True)
        object.__setattr__(self, 'CommandInProgress', False)
        object.__setattr__(self, 'UserControl', True)
        object.__setattr__(self, 'UserControlBackground', False)
    def __setattr__(self, name, value): raise AssertionError('native setter forbidden: ' + name)
    def GetProcessID(self): return 700
    def IsSame(self, first, second): return int(first is second)
    def SetUserPreferenceToggle(self, *args): raise AssertionError('preference setter forbidden')
    def SetUserPreferenceIntegerValue(self, *args): raise AssertionError('preference setter forbidden')
    def SetUserPreferenceDoubleValue(self, *args): raise AssertionError('preference setter forbidden')


class VisibleControlTests(unittest.TestCase):
    def setup_case(self, temporary):
        source = Path(temporary) / 'component.SLDPRT';source.write_bytes(b'original native source')
        doc = Document(source);app = ReadOnlyApp(doc)
        return source, doc, app, hashlib.sha256(source.read_bytes()).hexdigest()

    def test_positive_observations_are_read_only_and_keep_original_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            source,doc,app,digest=self.setup_case(temporary);row={};calls=[]
            exporter=mock.Mock(return_value={'ok':True,'original_receipt':1})
            result=control.observe_export(app,doc,source,digest,control.host_snapshot(app),'GLB',exporter,
                                          lambda name,fn:(calls.append(name),fn())[1],row)
            self.assertEqual(result,{'ok':True,'original_receipt':1})
            exporter.assert_called_once_with()
            self.assertEqual(calls,['observe-before-GLB','export-GLB','observe-after-GLB'])
            self.assertEqual(row['before'],row['after'])
            self.assertFalse(row['before']['host']['CommandInProgress'])
            self.assertEqual(row['before']['document']['metadata'],[1,7,False,'默认'])
            self.assertEqual(source.read_bytes(),b'original native source')

    def test_bad_preconditions_stop_before_export_without_native_setters(self):
        for kind in ('hidden','bad-bool','wrong-pid','unknown-identity','foreground','hash','active-sketch'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                source,doc,app,digest=self.setup_case(temporary);expected=control.host_snapshot(app)
                if kind=='hidden': object.__setattr__(app,'Visible',False)
                elif kind=='bad-bool': object.__setattr__(app,'CommandInProgress',0)
                elif kind=='wrong-pid': expected['process_id']=701
                elif kind=='unknown-identity': object.__setattr__(app,'IsSame',lambda a,b:2)
                elif kind=='foreground': object.__setattr__(app,'ActiveDoc',object())
                elif kind=='hash': source.write_bytes(b'intervening work')
                elif kind=='active-sketch': doc.SketchManager.ActiveSketch=object()
                exporter=mock.Mock()
                with self.assertRaises(RuntimeError):
                    control.observe_export(app,doc,source,digest,expected,'GLB',exporter,lambda name,fn:fn(),{})
                exporter.assert_not_called()

    def test_post_export_state_drift_refuses_once_without_retry_or_repair(self):
        for kind in ('visible','CIP','pid','document','configuration','hash'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                source,doc,app,digest=self.setup_case(temporary);expected=control.host_snapshot(app);row={}
                def changed():
                    if kind=='visible':object.__setattr__(app,'Visible',False)
                    elif kind=='CIP':object.__setattr__(app,'CommandInProgress',True)
                    elif kind=='pid':object.__setattr__(app,'GetProcessID',lambda:701)
                    elif kind=='document':doc.stamp+=1
                    elif kind=='configuration':doc.ConfigurationManager.ActiveConfiguration.Name='Other'
                    else:source.write_bytes(b'changed by export')
                    return {'ok':True}
                exporter=mock.Mock(side_effect=changed)
                with self.assertRaises(RuntimeError):
                    control.observe_export(app,doc,source,digest,expected,'GLB',exporter,lambda name,fn:fn(),row)
                exporter.assert_called_once_with()
                self.assertEqual(row['result'],{'ok':True})

    def test_first_native_or_content_failure_has_no_post_failure_CAD_reads(self):
        for kind in ('native-exception','content-rejection'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                source,doc,app,digest=self.setup_case(temporary);calls=[];row={};error=ValueError('first native failure')
                exporter=mock.Mock(side_effect=error if kind=='native-exception' else None,
                                   return_value={'ok':False,'api_saved':True,'error':'empty BIN'})
                with self.assertRaises(ValueError if kind=='native-exception' else RuntimeError) as caught:
                    control.observe_export(app,doc,source,digest,control.host_snapshot(app),'GLB',exporter,
                                           lambda name,fn:(calls.append(name),fn())[1],row)
                if kind=='native-exception':self.assertIs(caught.exception,error)
                else:self.assertEqual(row['result']['error'],'empty BIN')
                exporter.assert_called_once_with()
                self.assertEqual(calls,['observe-before-GLB','export-GLB'])
                self.assertNotIn('after',row)

    def test_visible_startup_is_honestly_a_mode_bundle(self):
        from swcli.daemon.server import configure_resident_app
        app=mock.Mock()
        configure_resident_app(app,visible=control.VISIBLE_STARTUP)
        self.assertEqual(app.UserControl,True)
        self.assertEqual(app.Visible,True)
        self.assertNotIn('UserControlBackground',app.__dict__)
        self.assertNotIn('CommandInProgress',app.__dict__)
        self.assertIn('UserControl and Visible',control.CONTROL_KIND)

    def test_worker_uses_one_pinned_visible_case_and_fixed_fixture_arguments(self):
        harness=SimpleNamespace(run=mock.Mock(return_value=0));module=SimpleNamespace(harness=harness)
        with mock.patch.object(control,'verify_pinned_source'), mock.patch.object(control,'load_pinned_module',return_value=module):
            self.assertEqual(control.worker(),0)
        self.assertEqual(control.HEAD,'70d8c9ecf3c02b099ca9c2cc64fe1880061cea44')
        self.assertEqual(harness.run.call_args.args,(control.OUT,control.SWCONST,True))
        self.assertEqual(harness.run.call_args.kwargs['case_plan'],[('part','front',False)])
        tree=ast.parse(DRIVER.read_text())
        loops=[n for n in ast.walk(tree) if isinstance(n,ast.For) and isinstance(n.iter,ast.Tuple)]
        self.assertTrue(any(ast.literal_eval(n.iter)==('STL','3MF','AMF','GLB') for n in loops))
        calls={n.func.id:n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
        rectangle={k.arg:ast.literal_eval(k.value) for k in calls['create_rectangle_sketch_windows_with_handle'].keywords if k.arg in ('plane','width_mm','height_mm')}
        self.assertEqual(rectangle,{'plane':'front','width_mm':40,'height_mm':30})
        extrude=calls['extrude_sketch_windows_with_handle'];self.assertEqual(next(ast.literal_eval(k.value) for k in extrude.keywords if k.arg=='depth_mm'),10)
        self.assertFalse(any(isinstance(n,ast.Attribute) and n.attr.startswith('SetUserPreference') for n in ast.walk(tree)))
        self.assertFalse(any(isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr in ('Visible','CommandInProgress','UserControl','UserControlBackground') for t in n.targets) for n in ast.walk(tree)))

    def test_source_archive_and_extraction_must_both_match_before_loading_native_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);source=base/'source-70d8c9e';source.mkdir();(source/'fixture.py').write_bytes(b'pinned source')
            archive=base/'getter-source-70d8c9e.zip'
            with ZipFile(archive,'w') as packed:packed.writestr('fixture.py',b'pinned source')
            digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            with mock.patch.object(control,'BASE',base), mock.patch.object(control,'SOURCE',source), mock.patch.object(control,'SOURCE_ZIP_SHA256',digest):
                self.assertEqual(control.verify_pinned_source(),digest)
                (source/'fixture.py').write_bytes(b'intervening source')
                with self.assertRaisesRegex(RuntimeError,'extracted source changed'):control.verify_pinned_source()
                archive.write_bytes(b'changed archive')
                with self.assertRaisesRegex(RuntimeError,'archive changed'):control.verify_pinned_source()
        with mock.patch.object(control,'verify_pinned_source',side_effect=ValueError('source pin failed')), \
                mock.patch.object(control,'load_pinned_module') as load:
            with self.assertRaisesRegex(ValueError,'source pin failed'):control.worker()
            load.assert_not_called()

    def test_native_trace_requires_one_modern_save_per_format_and_zero_preference_CIP_writes(self):
        rows=[dict(event='swcli.native-call',request_id='local-export-'+fmt,worker_pid=71,
                   call='IModelDocExtension.SaveAs3',phase=phase)
              for fmt in ('STL','3MF','AMF','GLB') for phase in ('begin','end')]
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'worker.stderr.log'
            def write(items):path.write_text(''.join(json.dumps(row)+'\n' for row in items))
            write(rows);proof=control.audit_control_trace(path,71,complete=True)
            self.assertEqual(set(proof['exports']),{'STL','3MF','AMF','GLB'})
            self.assertEqual(proof['preference_setters'],0);self.assertEqual(proof['CommandInProgress_setters'],0)
            for call in ('ISldWorks.SetUserPreferenceToggle','IModelDocExtension.SetUserPreferenceDouble',
                         'SldWorks.CommandInProgress.enter','SldWorks.CommandInProgress.restore'):
                write(rows+[dict(event='swcli.native-call',call=call,phase='begin')])
                with self.assertRaisesRegex(RuntimeError,'writes'):control.audit_control_trace(path,71,complete=True)
            for changed in (rows[:-1],rows+[rows[0]], [dict(row,worker_pid=72) for row in rows]):
                write(changed)
                with self.assertRaises(RuntimeError):control.audit_control_trace(path,71,complete=True)
            write(rows[:6]);self.assertNotIn('GLB',control.audit_control_trace(path,71,complete=False)['exports'])
            with self.assertRaises(RuntimeError):control.audit_control_trace(path,71,complete=True)

    def test_offline_raw_BIN_and_manifest_are_retained_including_invalid_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary);tree=json.dumps({'buffers':[{'byteLength':720}]}).encode();tree+=b' '*((-len(tree))%4)
            data=struct.pack('<4sII',b'glTF',2,28+len(tree))+struct.pack('<I4s',len(tree),b'JSON')+tree+struct.pack('<I4s',0,b'BIN\x00')
            (output/'rejected.glb').write_bytes(data);(output/'broken.GLB').write_bytes(b'broken');(output/'manifest.json').write_text('{"preserved":true}')
            rows={r['path']:r for r in control.collect_glb_artifacts(output)}
            self.assertEqual(rows['rejected.glb']['chunks'][-1],{'kind':'BIN\x00','bytes':0})
            self.assertEqual(rows['rejected.glb']['declared_buffers'],[{'byteLength':720}])
            self.assertEqual(rows['rejected.glb']['sha256'],hashlib.sha256(data).hexdigest())
            self.assertIn('parse_error',rows['broken.GLB'])
            self.assertEqual(rows['manifest.json']['manifest'],{'preserved':True})


if __name__=='__main__':unittest.main()
