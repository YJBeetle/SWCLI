import hashlib
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest import mock

P=Path(__file__).with_name('markingjig_control.py')
spec=importlib.util.spec_from_file_location('markingjig_tested',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def value(obj,name):
    result=getattr(obj,name)
    return result() if callable(result) else result

class Model:
    def __init__(self,path,kind):
        self.path=str(path);self.kind=kind;self.modified=False;self.readonly=True;self.lightweight=0;self.unloaded=False
        self.ConfigurationManager=NS(ActiveConfiguration=NS(Name='Default'))
        self.SketchManager=NS(ActiveSketch=None);self.Extension=NS(NeedsRebuild2=0)
        self.GetType=lambda:self.kind;self.GetPathName=lambda:self.path;self.GetTitle=lambda:Path(self.path).name
        self.GetUpdateStamp=lambda:144;self.GetSaveFlag=lambda:self.modified;self.IsOpenedReadOnly=lambda:self.readonly
        self.IsOpenedViewOnly=lambda:False;self.GetConfigurationNames=lambda:('Default',)
        self.GetEditTarget=lambda:self;self.HasUnloadedComponents=lambda:self.unloaded
        self.GetLightWeightComponentCount=lambda:self.lightweight
        self.GetNumDependencies=lambda *args:0;self.GetDependencies2=lambda *args:None
        body=NS(GetBodyBox=lambda:(0.,0.,0.,1.,1.,1.),GetMassProperties=lambda density:(0.,0.,0.,1.,1.,0.,0.,0.,0.,0.,0.,0.),
                GetType=lambda:0,GetFaceCount=lambda:6,GetEdgeCount=lambda:12)
        self.GetBodies2=lambda *args:(body,)

class Case(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.names=[m.SOURCE,'Spirit_Level.SLDPRT'];files={}
        for i,name in enumerate(self.names):
            p=self.root/name;p.write_bytes(('native-'+str(i)).encode());files[name]=m.stable_file(p);p.chmod(0o444)
        self.patch=mock.patch.object(m,'SOURCE_SHA',files[m.SOURCE]['sha256']);self.patch.start()
        self.inventory=dict(schema='swcli.markingjig-inventory.v1',source=m.SOURCE,files=files)
        self.copy=m.WorkingCopy(self.inventory,self.root,self.names)
        self.top=Model(self.root/m.SOURCE,2);self.child=Model(self.root/self.names[1],1)
        self.component=NS(Name2='component-1',GetPathName=lambda:self.child.path,IsVirtual=False,
             GetSuppression2=lambda:2,IsSuppressed=lambda:False,HasUnloadedComponents=lambda:False,
             GetModelDoc2=lambda:self.child,ReferencedConfiguration='Default',GetParent=lambda:None,
             Transform2=NS(ArrayData=(1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.)))
        self.top.GetComponents=lambda flag:(self.component,);self.top.GetComponentCount=lambda flag:1
        self.top.GetNumDependencies=lambda *args:2
        self.top.GetDependencies2=lambda *args:('Spirit_Level',r'C:\old\Spirit_Level.SLDPRT')
        self.spec=NS(Error=0,Warning=0);self.opens=[];self.calls=[];self.exports=[]
        def open7(s):self.opens.append(s);return self.top
        self.app=NS(GetOpenDocSpec=lambda path:self.spec,OpenDoc7=open7,GetProcessID=lambda:17,RevisionNumber=lambda:'33.5.0',
                    Visible=False,CommandInProgress=False,UserControl=True,UserControlBackground=True,
                    ActiveDoc=self.top,IsSame=lambda a,b:1 if a is b else 2,
                    GetDocuments=lambda:(self.top,self.child),GetDocumentCount=lambda:2,
                    GetOpenDocumentByName=lambda path:self.child if path==self.child.path else self.top if path==self.top.path else None)
        self.report={};self.live={};self.constants=dict(swComponentFullyResolved=2,swComponentResolved=3)
    def tearDown(self):self.patch.stop();self.temp.cleanup()
    def call(self,name,fn):self.calls.append(name);return fn()
    def export(self,*args,**kwargs):self.exports.append((args,kwargs));return dict(ok=True)
    def run_case(self,mode='invoke',exporter=None):
        m.one_case(self.app,self.copy,mode,self.root/'new-output',value,self.call,self.live,self.report,self.constants,17,
                   exporter or self.export,lambda pid:dict(created_filetime=123,exe_path='raw8.3',exe_sha256='fixed'))
    def stopped(self):
        with self.assertRaises(RuntimeError):self.run_case()
        self.assertEqual(len(self.exports),0)
    def test_one_modern_export_after_readonly_complete_graph(self):
        self.run_case();self.assertEqual(len(self.opens),1);self.assertEqual(len(self.exports),1)
        self.assertEqual(self.report['actual_spec'],m.SPEC)
        self.assertTrue(self.exports[0][1]['strict']);self.assertIs(self.exports[0][1]['document'],self.top)
        self.assertTrue(self.report['success']);self.assertEqual(self.report['observations'][0],self.report['observations'][1])
    def test_probe_has_zero_save(self):
        self.run_case('probe');self.assertEqual(self.report['export_attempts'],0);self.assertFalse(self.exports)
    def test_initial_lightweight_stops_without_resolving(self):
        self.top.lightweight=1;self.stopped()
        self.assertFalse(any('Resolve' in x for x in self.calls))
    def test_suppression_unknown_or_lightweight_stops(self):
        for state in (0,1,4,5,None,True):
            with self.subTest(state=state):
                self.component.GetSuppression2=lambda:state;self.stopped()
    def test_unloaded_or_missing_model_stops(self):
        self.component.GetModelDoc2=lambda:None;self.stopped()
    def test_missing_dependency_does_not_expand_copy_list(self):
        self.top.GetDependencies2=lambda *a:('Missing',r'C:\elsewhere\Missing.SLDPRT');self.stopped()
        self.assertEqual(list(self.copy.files),self.names)
    def test_dependency_count_mismatch_stops(self):
        self.top.GetNumDependencies=lambda *a:4;self.stopped()
    def test_external_clone_same_bytes_is_not_private_file(self):
        elsewhere=self.root/'outside';elsewhere.mkdir();p=elsewhere/self.names[1];p.write_bytes((self.root/self.names[1]).read_bytes())
        self.child.path=str(p);self.stopped()
    def test_readonly_or_dirty_unknown_stops(self):
        self.top.readonly=False;self.stopped();self.top.readonly=True;self.top.modified=True;self.stopped()
    def test_warning_stops_but_retains_document_for_cleanup(self):
        self.spec.Warning=1;self.stopped();self.assertIs(self.live['document'],self.top)
    def test_configuration_mismatch_stops_without_activation(self):
        self.component.ReferencedConfiguration='Other';self.stopped()
    def test_foreground_bool_cannot_replace_int_identity(self):
        self.app.IsSame=lambda a,b:True;self.stopped()
    def test_incomplete_catalog_stops(self):
        self.app.GetDocumentCount=lambda:3;self.stopped()
    def test_source_geometry_failure_retains_partial_observation(self):
        self.child.GetBodies2=lambda *a:None;self.stopped()
        self.assertFalse(self.report['observations'][0]['complete'])
        self.assertIn('model',self.report['observations'][0]['components'][0])
    def test_export_failure_stops_without_postfailure_CAD_reads(self):
        def failed(*a,**k):self.exports.append((a,k));return dict(ok=False,error='native/content first')
        with self.assertRaisesRegex(RuntimeError,'first export'):self.run_case(exporter=failed)
        self.assertEqual(len(self.exports),1);self.assertEqual(len(self.report['observations']),1)
    def test_export_state_change_is_not_retried(self):
        def changed(*a,**k):self.exports.append((a,k));self.child.modified=True;return dict(ok=True)
        with self.assertRaises(RuntimeError):self.run_case(exporter=changed)
        self.assertEqual(len(self.exports),1)
    def test_saved_embedded_virtual_has_pinned_owner_not_guessed_external_file(self):
        self.component.IsVirtual=True;self.child.path=str(self.root/'Virtual^MarkingJig.SLDPRT');self.child.readonly=False
        self.top.GetNumDependencies=lambda *a:0;self.top.GetDependencies2=lambda *a:None
        self.run_case('probe');row=self.report['observations'][0]['components'][0]
        self.assertEqual(row['owner_file'],m.SOURCE);self.assertTrue(row['virtual']);self.assertFalse(self.exports)
    def test_unknown_virtual_owner_stops(self):
        self.component.IsVirtual=True;self.component.GetParent=lambda:NS(Name2='unlisted-parent');self.stopped()
    def test_duplicate_selected_or_writable_copy_refused(self):
        with self.assertRaises(RuntimeError):m.WorkingCopy(self.inventory,self.root,self.names+[m.SOURCE])
        (self.root/self.names[1]).chmod(0o644)
        with self.assertRaises(RuntimeError):m.WorkingCopy(self.inventory,self.root,self.names)
    def test_source_replacement_same_bytes_refused(self):
        p=self.root/self.names[1];data=p.read_bytes();p.unlink();p.write_bytes(data);p.chmod(0o444)
        with self.assertRaises(RuntimeError):self.copy.unchanged()
    def test_unlisted_input_refused_before_native_open(self):
        (self.root/'unlisted.SLDPRT').write_bytes(b'other')
        with self.assertRaisesRegex(RuntimeError,'unlisted'):self.copy.unchanged()
    def test_hardlinked_working_copy_refused(self):
        import os
        os.link(self.root/self.names[1],self.root/'alias-file')
        with self.assertRaisesRegex(RuntimeError,'hard link'):self.copy.unchanged()
    def test_symlink_copy_directory_refused(self):
        with tempfile.TemporaryDirectory() as area:
            alias=Path(area)/'alias';alias.symlink_to(self.root,target_is_directory=True)
            (self.root/'child').mkdir()
            for path in (alias,alias/'child'):
                with self.subTest(path=path):
                    with self.assertRaisesRegex(RuntimeError,'directory symlink/reparse'):
                        m.WorkingCopy(self.inventory,path,self.names)
    def test_symlink_refused(self):
        p=self.root/self.names[1];p.unlink();p.symlink_to(self.root/m.SOURCE)
        with self.assertRaises(RuntimeError):self.copy.unchanged()

if __name__=='__main__':unittest.main()
