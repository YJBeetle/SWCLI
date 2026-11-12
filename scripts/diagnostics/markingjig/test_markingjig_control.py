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
        self.Extension.GetDependencies=lambda *args:()
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
        self.dependency_calls=[]
        def dependencies(*args):
            self.dependency_calls.append(args)
            return ('Spirit_Level',r'C:\old\Spirit_Level.SLDPRT')
        self.top.Extension.GetDependencies=dependencies
        self.spec=NS(Error=0,Warning=0);self.opens=[];self.calls=[];self.exports=[]
        def open7(s):self.opens.append(s);return self.top
        self.app=NS(GetOpenDocSpec=lambda path:self.spec,OpenDoc7=open7,GetProcessID=lambda:17,RevisionNumber=lambda:'33.5.0',
                    Visible=False,CommandInProgress=False,UserControl=True,UserControlBackground=True,
                    ActiveDoc=self.top,IsSame=lambda a,b:1 if a is b else 2,
                    GetDocuments=lambda:(self.top,self.child),GetDocumentCount=lambda:2,
                    GetOpenDocumentByName=lambda path:self.child if path==self.child.path else self.top if path==self.top.path else None)
        self.report={};self.live={};self.constants=dict(swComponentFullyResolved=2,swComponentResolved=3,swFileLoadWarning_ReadOnly=2)
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
        self.top.Extension.GetDependencies=lambda *a:('Missing',r'C:\elsewhere\Missing.SLDPRT');self.stopped()
        self.assertEqual(list(self.copy.files),self.names)
    def test_dependency_pair_shape_mismatch_stops(self):
        self.top.Extension.GetDependencies=lambda *a:('name',);self.stopped()
    def test_modern_dependency_flags_no_legacy_count_or_query(self):
        self.run_case('probe')
        self.assertEqual(self.dependency_calls,[(True,False,False,True,True),(True,False,False,False,True)])
        self.assertFalse(any('GetNumDependencies' in x or 'GetDependencies2' in x for x in self.calls))
        query=self.report['observations'][0]['dependency_queries'][0]
        self.assertIsNone(query['independent_native_string_count'])
        self.assertEqual(query['reads'][0]['returned_string_count'],2)
    def test_broken_reference_in_inclusive_census_stops(self):
        def dependencies(*args):
            if args[3]:return ('Spirit_Level',r'C:\old\Spirit_Level.SLDPRT','Broken',r'C:\old\Broken.SLDPRT')
            return ('Spirit_Level',r'C:\old\Spirit_Level.SLDPRT')
        self.top.Extension.GetDependencies=dependencies;self.stopped()
        queries=self.report['observations'][0]['dependency_queries']
        self.assertEqual(queries[0]['reads'][0]['returned_string_count'],4)
        self.assertNotIn('broken_census_equal',queries[0])
    def test_derived_reference_unloaded_stops(self):
        name='MarkingJigRod.SLDPRT';path=self.root/name;path.write_bytes(b'derived-native')
        self.inventory['files'][name]=m.stable_file(path);path.chmod(0o444)
        self.copy=m.WorkingCopy(self.inventory,self.root,self.names+[name])
        self.top.Extension.GetDependencies=lambda *a:('Spirit_Level',r'C:\old\Spirit_Level.SLDPRT','Derived',r'C:\old\MarkingJigRod.SLDPRT')
        with self.assertRaisesRegex(RuntimeError,'dependency not loaded'):self.run_case()
        self.assertFalse(self.exports)
        self.assertEqual(self.report['observations'][0]['dependencies'][-1]['name'],'Derived')
    def test_imported_origin_retained_and_not_silently_stripped(self):
        raw=('Spirit_Level',r'C:\old\Spirit_Level.SLDPRT|C:\upstream\source.step')
        self.top.Extension.GetDependencies=lambda *a:raw;self.stopped()
        observed=self.report['observations'][0]
        self.assertEqual(observed['dependency_queries'][0]['reads'][0]['raw_strings'],list(raw))
        self.assertEqual(observed['dependencies'][0]['stored_path'],raw[1])
    def test_unknown_dependency_variant_is_not_assumed_empty(self):
        for raw in (None,False,0,'',object()):
            with self.subTest(kind=type(raw).__name__):
                self.top.Extension.GetDependencies=lambda *a:raw;self.stopped()
    def test_even_dependency_array_cannot_omit_loaded_external_graph(self):
        self.top.Extension.GetDependencies=lambda *a:();self.stopped()
    def test_dependency_census_cannot_hide_duplicate_broken_record(self):
        one=('Spirit_Level',r'C:\old\Spirit_Level.SLDPRT')
        self.top.Extension.GetDependencies=lambda *a:one*2 if a[3] else one;self.stopped()
    def test_cross_channel_all_non_ctime_fields_must_match(self):
        original=m.os.fstat
        for key in ('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_birthtime_ns','st_file_attributes','st_nlink'):
            with self.subTest(field=key):
                def changed(fd):
                    row=m.fingerprint(original(fd));row[key]=(row[key] or 0)+1
                    return NS(**row)
                with mock.patch.object(m.os,'fstat',side_effect=changed),mock.patch.object(m,'split_ctime_channels',return_value=True):
                    with self.assertRaisesRegex(RuntimeError,'path/opened file differs: '+key):m.stable_file(self.root/m.SOURCE)
    def test_ctime_cross_channel_exception_is_narrow_and_preserves_raw_values(self):
        original=m.os.fstat
        def changed(fd):
            row=m.fingerprint(original(fd));row['st_ctime_ns']+=7;return NS(**row)
        with mock.patch.object(m.os,'fstat',side_effect=changed):
            with mock.patch.object(m,'split_ctime_channels',return_value=False):
                with self.assertRaisesRegex(RuntimeError,'st_ctime_ns'):m.stable_file(self.root/m.SOURCE)
            with mock.patch.object(m,'split_ctime_channels',return_value=True):
                row=m.stable_file(self.root/m.SOURCE)
                self.assertEqual(row['path_before']['st_ctime_ns']+7,row['handle_before']['st_ctime_ns'])
                self.assertEqual(row['handle_before'],row['handle_after'])
    def test_ctime_same_handle_channel_change_still_stops(self):
        original=m.os.fstat;calls=[]
        def changed(fd):
            calls.append(fd);row=m.fingerprint(original(fd));row['st_ctime_ns']+=len(calls);return NS(**row)
        with mock.patch.object(m.os,'fstat',side_effect=changed),mock.patch.object(m,'split_ctime_channels',return_value=True):
            with self.assertRaisesRegex(RuntimeError,'held input metadata changed'):m.stable_file(self.root/m.SOURCE)
    def test_ctime_same_path_channel_change_still_stops(self):
        original=m.fingerprint;calls=[]
        def changed(value):
            calls.append(value);row=original(value)
            if len(calls)==4:row['st_ctime_ns']+=1
            return row
        with mock.patch.object(m,'fingerprint',side_effect=changed),mock.patch.object(m,'split_ctime_channels',return_value=True):
            with self.assertRaisesRegex(RuntimeError,'input path metadata changed'):m.stable_file(self.root/m.SOURCE)
    def test_ctime_exception_only_for_known_windows_cpython_3147(self):
        for platform,implementation,version,wanted in (('nt','cpython',(3,14,7),True),('posix','cpython',(3,14,7),False),('nt','cpython',(3,14,8),False),('nt','pypy',(3,14,7),False)):
            with self.subTest(platform=platform,implementation=implementation,version=version):
                with mock.patch.object(m.os,'name',platform),mock.patch.object(m.sys,'implementation',NS(name=implementation)),mock.patch.object(m.sys,'version_info',version):
                    self.assertIs(m.split_ctime_channels(),wanted)
    def test_external_clone_same_bytes_is_not_private_file(self):
        elsewhere=self.root/'outside';elsewhere.mkdir();p=elsewhere/self.names[1];p.write_bytes((self.root/self.names[1]).read_bytes())
        self.child.path=str(p);self.stopped()
    def test_readonly_or_dirty_unknown_stops(self):
        self.top.readonly=False;self.stopped();self.top.readonly=True;self.top.modified=True;self.stopped()
    def test_warning_stops_but_retains_document_for_cleanup(self):
        self.spec.Warning=1;self.stopped();self.assertIs(self.live['document'],self.top)
    def test_precise_readonly_warning_requires_clean_readonly_model_then_full_probe(self):
        self.spec.Warning=2;self.run_case('probe')
        self.assertTrue(self.report['probe_success']);self.assertFalse(self.exports)
        self.assertEqual(self.report['expected_readonly_warning_model'],dict(readonly=True,modified=False,viewonly=False,provisional_only=True))
        self.assertTrue(self.report['open_warning_policy']['complete_model_gate_still_required'])
    def test_readonly_warning_does_not_bypass_unknown_or_dirty_model(self):
        for member,value_ in (('readonly',False),('readonly',None),('modified',True),('modified',0)):
            with self.subTest(member=member,value=value_):
                self.top.readonly=True;self.top.modified=False;setattr(self.top,member,value_);self.spec.Warning=2
                self.stopped();self.assertEqual(self.report['observations'],[])
    def test_readonly_warning_rejects_viewonly_or_unknown_flag(self):
        for flag in (True,None,0):
            with self.subTest(flag=flag):
                self.spec.Warning=2;self.top.IsOpenedViewOnly=lambda:flag;self.stopped()
    def test_all_other_warning_bits_and_mixed_flags_rejected(self):
        for warning in (1,3,4,6,32,128,2|1048576,-1,True,None,'2'):
            with self.subTest(warning=warning):
                self.spec.Warning=warning;self.stopped()
                self.assertIs(self.live['document'],self.top)
        self.assertFalse(any(x.startswith('read-open-model-') for x in self.calls))
    def test_nonzero_error_with_readonly_warning_stops_before_semantic_reads(self):
        self.spec.Error=1;self.spec.Warning=2;self.stopped()
        self.assertFalse(any(x.startswith('read-open-model-') for x in self.calls))
    def test_unknown_error_shapes_rejected_even_with_precise_readonly_warning(self):
        for error in (False,None,'0'):
            with self.subTest(error=error):
                self.spec.Error=error;self.spec.Warning=2;self.stopped()
        self.assertFalse(any(x.startswith('read-open-model-') for x in self.calls))
    def test_installed_readonly_enum_must_be_exact_verified_int_two_before_open(self):
        for raw in (None,True,1,3,'2'):
            with self.subTest(raw=raw):
                self.constants['swFileLoadWarning_ReadOnly']=raw;self.stopped()
        self.assertFalse(self.opens)
    def test_known_readonly_warning_does_not_bypass_original_rebuild_graph_gate(self):
        self.spec.Warning=2;self.top.Extension.NeedsRebuild2=1;self.stopped()
        self.assertIn('needs_rebuild',self.report['observations'][0]['top'])
    def test_expected_readonly_warning_does_not_ignore_copy_source_window_failure(self):
        self.spec.Warning=2
        with mock.patch.object(self.copy,'unchanged',side_effect=RuntimeError('held ctime changed')):
            self.stopped()
        self.assertFalse(self.report.get('probe_success',False));self.assertEqual(self.report['open_warnings'],2)
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
        self.top.Extension.GetDependencies=lambda *a:()
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
