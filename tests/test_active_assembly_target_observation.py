"""All planned faces need native owners; no public handles or CAD writes."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest import mock

from swcli.hosts import windows_assembly_target_observation as targets


class ActiveAssemblyTargetsTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.folder=Path(self.directory.name)
        self.modules={'pythoncom':NS(VT_ARRAY=8192,VT_UI1=17,VT_BYREF=16384,VT_VARIANT=12,IID_IDispatch='IDispatch',TKIND_DISPATCH=4),
                      'win32com.client':NS(VARIANT=lambda kind,value:NS(varianttype=kind,value=value))}
        patch=mock.patch.dict(sys.modules,self.modules);patch.start();self.addCleanup(patch.stop)
        self.build()
        self.factory_patch=mock.patch.object(targets,'OfficialInterfaces',side_effect=lambda app:self.binder)
        self.factory=self.factory_patch.start();self.addCleanup(self.factory_patch.stop)

    def build(self):
        for name in ('source.SLDPRT','assembly.SLDASM'):(self.folder/name).write_bytes(b'fixed fixture bytes')
        self.names=['anchor-1','moving-1'];self.source_body=NS();self.source_faces=[]
        for index in range(2):
            surface=NS(IsPlane=index==0,IsCylinder=index==1,PlaneParams=(1,0,0,0,0,0),CylinderParams=(0,0,0,0,0,1,.003))
            self.source_faces.append(NS(GetBody=lambda:self.source_body,GetSurface=lambda surface=surface:surface,
                FaceInSurfaceSense=False,Normal=(1,0,0),GetArea=lambda index=index:.001*(index+1)))
        self.source_body.GetFaceCount=lambda:2;self.source_body.GetFaces=lambda:tuple(self.source_faces)
        def document(kind,name):
            stamp_reader=mock.Mock(return_value=7)
            return NS(GetType=kind,GetConfigurationNames=lambda:('Default',),GetConfigurationCount=lambda:1,
                GetActiveConfiguration=lambda:NS(Name='Default'),GetUpdateStamp=lambda:stamp_reader(),stamp_reader=stamp_reader,GetSaveFlag=False,
                GetPathName=str(self.folder/name),IsOpenedReadOnly=True,IsOpenedViewOnly=False,SketchManager=NS(ActiveSketch=None))
        self.source=document(1,'source.SLDPRT');self.assembly=document(2,'assembly.SLDASM')
        self.source.GetBodies2=mock.Mock(side_effect=lambda kind,visible:(self.source_body,) if kind==0 else None)
        self.components=[];self.mapped=[];self.resolved=[];self.owners=[];self.original_getters=[];self.bodies=[];self.body_faces=[]
        self.source_getter=mock.Mock(side_effect=AssertionError('source face is not an owner receiver'))
        for face in self.source_faces:face.GetComponent=lambda:self.source_getter()
        for ci,name in enumerate(self.names):
            body=NS();faces=[];mapped=[];resolved=[]
            component=NS(Name2=name,IsVirtual=False,GetSuppression2=2,ReferencedConfiguration='Default',IsFixed=ci==0,
                GetModelDoc2=lambda:self.source,GetPathName=self.source.GetPathName,
                Transform2=NS(ArrayData=[1,0,0,0,1,0,0,0,1,.02*ci,0,0,1,0,0,0]))
            for fi,source in enumerate(self.source_faces):
                face=NS(**vars(source));face.native_token=(ci,fi);face.GetBody=lambda body=body:body;faces.append(face)
                original=NS(**vars(face));original_getter=mock.Mock(side_effect=AssertionError('original mapping getter forbidden'))
                original.GetComponent=lambda getter=original_getter:getter()
                owner=mock.Mock(return_value=component)
                resolution=NS(**vars(face));resolution.GetComponent=lambda owner=owner:owner()
                mapped.append(original);resolved.append(resolution);self.owners.append(owner);self.original_getters.append(original_getter)
            body.GetFaceCount=lambda:2;body.GetFaces=lambda faces=faces:tuple(faces)
            def bodies(kind,info,body=body):info.value=(1,);return (body,)
            component.GetBodies3=mock.Mock(side_effect=bodies)
            component.GetCorresponding=mock.Mock(side_effect=lambda face,mapped=mapped:mapped[next(i for i,item in enumerate(self.source_faces) if item is face)])
            self.components.append(component);self.mapped.extend(mapped);self.resolved.extend(resolved);self.bodies.append(body);self.body_faces.append(faces)
        self.assembly.GetEditTarget=lambda:self.assembly;self.assembly.GetEditTargetComponent=lambda:None
        self.assembly.GetComponents=mock.Mock(side_effect=lambda top:tuple(self.components));self.assembly.GetComponentCount=lambda top:2
        def same(first,second):
            if first is second:return 1
            return int(hasattr(first,'native_token') and hasattr(second,'native_token') and first.native_token==second.native_token)
        self.app=NS(ActiveDoc=self.assembly,IsSame=mock.Mock(side_effect=same),RevisionNumber='33.5.0')
        self.extension=NS()
        self.extension.GetPersistReference3=mock.Mock(side_effect=lambda face:bytes((face.native_token[0]+1,face.native_token[1]+1)))
        def resolve(encoded,seed):
            self.assertEqual(type(seed),int);self.assertEqual(seed,2147483647)
            self.assertEqual(encoded.varianttype,8192|17)
            ci,fi=encoded.value;return self.resolved[(ci-1)*2+fi-1],0
        self.extension.GetObjectByPersistReference3=mock.Mock(side_effect=resolve)
        self.assembly.Extension=self.extension
        self.binder=NS(bind=mock.Mock(side_effect=lambda native,interface:native),check_resolver=mock.Mock())
        self.assembly.CreateMate=mock.Mock(side_effect=AssertionError('no writes'))
        self.app.ActivateDoc3=mock.Mock(side_effect=AssertionError('no activation'))

    def read(self,**kwargs):
        return targets.observe_readonly_active_targets(app=self.app,document=self.assembly,components=self.names,**kwargs)

    def assert_no_owner(self):
        for owner in self.owners:owner.assert_not_called()
        for getter in self.original_getters:getter.assert_not_called()
        self.source_getter.assert_not_called()

    def test_complete_two_component_all_face_census_keeps_bindings_private(self):
        census=self.read()
        self.assertEqual(census.value['face_count'],4);self.assertEqual(len(census.bindings),4)
        self.assertTrue(census.value['all_faces_observed']);self.assertFalse(census.value['public_handles_issued'])
        self.assertFalse(census.value['write_CAS_executed']);self.assertFalse(census.value['public_acceptance'])
        self.assertEqual([len(row['faces']) for row in census.value['components']],[2,2])
        self.assertEqual({row['geometry']['surface_kind'] for c in census.value['components'] for row in c['faces']},{'plane','cylinder'})
        for i,binding in enumerate(census.bindings):
            self.assertIs(binding.component,self.components[i//2]);self.assertIs(binding.original_mapped,self.mapped[i]);self.assertIs(binding.resolved,self.resolved[i])
            self.owners[i].assert_called_once_with();self.original_getters[i].assert_not_called()
        self.assertEqual(self.extension.GetPersistReference3.call_count,4);self.assertEqual(self.extension.GetObjectByPersistReference3.call_count,4)
        for component in self.components:self.assertEqual(component.GetCorresponding.call_count,2)
        json.dumps(census.value,allow_nan=False)
        self.assembly.CreateMate.assert_not_called();self.app.ActivateDoc3.assert_not_called()

    def test_each_face_has_one_distinct_native_mapping_reference_owner_trace(self):
        import contextlib
        import io
        import os
        from swcli.hosts.native_trace import trace_native_request
        stream=io.StringIO()
        with mock.patch.dict(os.environ,{'SWCLI_TRACE_NATIVE_CALLS':'1'}),contextlib.redirect_stderr(stream),trace_native_request('offline-census','private-assembly-targets'):
            self.read()
        events=[json.loads(line) for line in stream.getvalue().splitlines()]
        calls=('Component2.GetCorresponding(source-face)','IModelDocExtension.GetPersistReference3',
               'IModelDocExtension.GetObjectByPersistReference3','IEntity(reference-resolved).GetComponent',
               'Resolved.owner-IsSame(target-component)')
        for ci in range(2):
            for fi in range(2):
                stage='assembly-targets.component[%d].face[%d]'%(ci,fi)
                scoped=[event for event in events if event.get('stage')==stage]
                for call in calls:
                    self.assertEqual([e['phase'] for e in scoped if e['call']==call],['begin','end'],(stage,call))
                active=[i for i,e in enumerate(scoped) if e['call']=='Assembly.ActiveDoc-IsSame(target)' and e['phase']=='end']
                owner=next(i for i,e in enumerate(scoped) if e['call']=='IEntity(reference-resolved).GetComponent')
                self.assertEqual(len(active),2);self.assertTrue(all(index<owner for index in active))

    def test_background_rejected_before_document_entity_reference_or_owner_access(self):
        self.app.ActiveDoc=object();self.assembly.GetType=mock.Mock(side_effect=AssertionError('no document traversal'))
        with self.assertRaises(targets.AssemblyTargetObservationError) as caught:self.read()
        self.assertEqual(caught.exception.code,'AssemblyNotActive')
        self.assembly.GetType.assert_not_called();self.assembly.GetComponents.assert_not_called();self.factory.assert_not_called()
        self.extension.GetPersistReference3.assert_not_called();self.assert_no_owner()

    def test_face_limit_and_two_component_scope_are_strict(self):
        for limit in (0,65,True,2.0):
            with self.subTest(limit=limit),self.assertRaises(targets.AssemblyTargetObservationError):self.read(max_faces=limit)
        self.assert_no_owner();self.assembly.GetComponents.assert_not_called()
        self.names=['anchor-1','anchor-1']
        with self.assertRaises(targets.AssemblyTargetObservationError):self.read()
        self.assert_no_owner()

    def test_each_face_null_owner_stops_without_next_receiver_or_postfailure_reads(self):
        for failed in range(4):
            with self.subTest(failed=failed):
                self.build();self.owners[failed].return_value=None
                with self.assertRaisesRegex(targets.AssemblyTargetObservationError,'has no component'):self.read()
                for i,owner in enumerate(self.owners):self.assertEqual(owner.call_count,int(i<=failed))
                for getter in self.original_getters:getter.assert_not_called()
                self.assertEqual(self.extension.GetObjectByPersistReference3.call_count,failed+1)
                self.assertEqual(self.source.stamp_reader.call_count,2)  # inputs only; no success postconditions
                self.assembly.CreateMate.assert_not_called();self.app.ActivateDoc3.assert_not_called()

    def test_matching_reference_body_and_geometry_cannot_mask_wrong_component_owner(self):
        for failed in (0,2):
            with self.subTest(failed=failed):
                self.build();self.owners[failed].return_value=self.components[1-failed//2]
                with self.assertRaisesRegex(targets.AssemblyTargetObservationError,'owner differs'):self.read()
                self.assertEqual(sum(owner.call_count for owner in self.owners),failed+1)

    def test_original_native_getter_exception_is_not_retried_or_replaced(self):
        first=RuntimeError('original native owner failure');self.owners[1].side_effect=first
        with self.assertRaises(RuntimeError) as caught:self.read()
        self.assertIs(caught.exception,first);self.assertEqual([o.call_count for o in self.owners],[1,1,0,0])
        self.assertEqual(self.source.stamp_reader.call_count,2)

    def test_typed_resolution_unknown_shape_status_or_null_never_reaches_owner(self):
        class Unknown:
            def __int__(self):raise AssertionError('no unknown status coercion')
        for result in (None,self.resolved[0],(),(self.resolved[0],),[self.resolved[0],0],(self.resolved[0],0,0),
                       (self.resolved[0],True),(self.resolved[0],0.0),(self.resolved[0],'0'),(self.resolved[0],Unknown()),
                       (self.resolved[0],2147483647),(self.resolved[0],1),(None,0)):
            with self.subTest(result_type=type(result).__name__):
                self.build();self.extension.GetObjectByPersistReference3.side_effect=None;self.extension.GetObjectByPersistReference3.return_value=result
                with self.assertRaises(targets.AssemblyTargetObservationError):self.read()
                self.extension.GetObjectByPersistReference3.assert_called_once();self.assert_no_owner()

    def test_reference_native_exception_stays_first_and_single(self):
        first=TypeError('native InvokeTypes failure');self.extension.GetObjectByPersistReference3.side_effect=first
        with self.assertRaises(TypeError) as caught:self.read()
        self.assertIs(caught.exception,first);self.extension.GetObjectByPersistReference3.assert_called_once();self.assert_no_owner()

    def test_foreign_roundtrip_or_resolved_body_geometry_rejected_before_owner(self):
        for field in ('native','body','geometry'):
            with self.subTest(field=field):
                self.build()
                if field=='native':self.resolved[0].native_token=('foreign',0)
                elif field=='body':self.resolved[0].GetBody=lambda:self.bodies[1]
                else:self.resolved[0].GetArea=lambda:.003
                with self.assertRaises(targets.AssemblyTargetObservationError):self.read()
                self.assert_no_owner()

    def test_incomplete_ambiguous_or_repeated_mapping_never_publishes_partial_census(self):
        self.body_faces[0].append(NS(**vars(self.body_faces[0][0])))
        with self.assertRaises(targets.AssemblyTargetObservationError):self.read()
        self.assert_no_owner()
        self.build();self.components[0].GetCorresponding.side_effect=lambda face:self.mapped[0]
        with self.assertRaisesRegex(targets.AssemblyTargetObservationError,'repeated'):self.read()
        self.assertEqual([o.call_count for o in self.owners],[1,0,0,0])

    def test_cross_component_reference_collision_rejects_complete_result(self):
        self.extension.GetPersistReference3.side_effect=lambda face:bytes((1,face.native_token[1]+1))
        # Isolate duplicate-reference rejection while preserving exact per-instance native resolution.
        counter=iter(self.resolved)
        self.extension.GetObjectByPersistReference3.side_effect=lambda encoded,seed:(next(counter),0)
        with self.assertRaisesRegex(targets.AssemblyTargetObservationError,'ambiguous face references'):self.read()
        self.assertEqual([o.call_count for o in self.owners],[1,1,1,0])

    def test_unclassified_face_is_not_silently_dropped(self):
        surface=self.source_faces[1].GetSurface();surface.IsPlane=False;surface.IsCylinder=False
        with self.assertRaisesRegex(targets.AssemblyTargetObservationError,'unsupported face'):self.read()
        self.assertEqual([o.call_count for o in self.owners],[1,0,0,0])

    def test_fixed_scope_drift_between_initial_check_and_input_capture_is_rejected(self):
        flags=iter((True,False))
        self.components[0].IsFixed=lambda:next(flags)
        with self.assertRaisesRegex(targets.AssemblyTargetObservationError,'scope changed before census'):self.read()
        self.assert_no_owner()

    def test_scope_refusals_before_owner(self):
        mutations=(lambda:setattr(self.source,'GetSaveFlag',True),lambda:setattr(self.source,'IsOpenedReadOnly',False),
            lambda:setattr(self.source,'IsOpenedViewOnly',True),lambda:setattr(self.source,'GetConfigurationCount',2),
            lambda:setattr(self.components[0],'ReferencedConfiguration','other'),lambda:setattr(self.components[0],'IsVirtual',True),
            lambda:setattr(self.components[0],'GetSuppression2',1),lambda:setattr(self.components[1],'IsFixed',True),
            lambda:setattr(self.source,'GetBodies2',lambda kind,visible:(self.source_body,)),
            lambda:setattr(self.source_body,'GetFaceCount',3),lambda:setattr(self.assembly,'GetEditTarget',lambda:self.source))
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                self.build();mutate()
                with self.assertRaises(targets.AssemblyTargetObservationError):self.read()
                self.assert_no_owner()

    def test_loss_of_active_document_stops_before_next_owner(self):
        def owner():self.app.ActiveDoc=object();return self.components[0]
        self.owners[0].side_effect=owner
        with self.assertRaises(targets.AssemblyTargetObservationError) as caught:self.read()
        self.assertEqual(caught.exception.code,'AssemblyNotActive');self.assertEqual([o.call_count for o in self.owners],[1,0,0,0])

    def test_success_postconditions_reject_source_pose_flags_and_edit_drift(self):
        mutations=(lambda:setattr(self.source.stamp_reader,'return_value',8),lambda:setattr(self.source,'GetSaveFlag',0),
                   lambda:self.components[1].Transform2.ArrayData.__setitem__(9,.04),
                   lambda:setattr(self.components[0],'IsFixed',False),lambda:setattr(self.components[1],'GetSuppression2',3),
                   lambda:setattr(self.source.SketchManager,'ActiveSketch',object()),
                   lambda:setattr(self.assembly,'GetEditTargetComponent',lambda:object()))
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                self.build()
                def last_owner():mutate();return self.components[1]
                self.owners[3].side_effect=last_owner
                with self.assertRaises(targets.AssemblyTargetObservationError):self.read()
                for owner in self.owners:owner.assert_called_once_with()


class OfficialBindingTests(unittest.TestCase):
    def test_official_factory_must_retain_pointer_and_native_identity(self):
        queried=object();native=NS(_oleobj_=NS(QueryInterface=mock.Mock(return_value=queried)))
        interfaces=object.__new__(targets.OfficialInterfaces);interfaces.app=NS(IsSame=lambda a,b:1)
        interfaces.info=lambda name:NS(GetTypeAttr=lambda:NS(iid='official-IID'))
        for pointer,identity in ((queried,1),(object(),1),(queried,0)):
            interfaces.app.IsSame=lambda a,b:identity
            factory=mock.Mock(return_value=NS(_oleobj_=pointer))
            with mock.patch.dict(sys.modules,{'pythoncom':NS(IID_IDispatch='IDispatch'),
                                              'win32com.client.dynamic':NS(Dispatch=factory)}):
                if pointer is queried and identity==1:self.assertIs(interfaces.bind(native,'IFace2')._oleobj_,queried)
                else:
                    with self.assertRaises(targets.AssemblyTargetObservationError):interfaces.bind(native,'IFace2')
            factory.assert_called_once()

    def test_library_is_loaded_only_beside_exact_owned_host_image_and_handle_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);image=directory/'SLDWORKS.exe';image.write_bytes(b'fixture')
            library_path=directory/'sldworks.tlb';library_path.write_bytes(b'fixture')
            handle=NS(Close=mock.Mock())
            library=NS(GetLibAttr=lambda:('{83A33D31-27C5-11CE-BFD4-00400513BB57}',0,0,33,0,0))
            load=mock.Mock(return_value=library);process=mock.Mock(return_value=handle)
            modules={'pythoncom':NS(LoadTypeLib=load),'win32api':NS(OpenProcess=process),
                     'win32con':NS(PROCESS_QUERY_INFORMATION=1,PROCESS_VM_READ=2),
                     'win32process':NS(GetModuleFileNameEx=lambda h,offset:str(image))}
            with mock.patch.dict(sys.modules,modules):
                bound=targets.OfficialInterfaces(NS(GetProcessID=42))
            self.assertIs(bound.library,library);process.assert_called_once_with(3,False,42)
            load.assert_called_once_with(str(library_path));handle.Close.assert_called_once_with()

    def test_host_image_failure_closes_exact_handle_without_loading_another_library(self):
        first=RuntimeError('first process image error');handle=NS(Close=mock.Mock());load=mock.Mock()
        modules={'pythoncom':NS(LoadTypeLib=load),'win32api':NS(OpenProcess=lambda *args:handle),
                 'win32con':NS(PROCESS_QUERY_INFORMATION=1,PROCESS_VM_READ=2),
                 'win32process':NS(GetModuleFileNameEx=mock.Mock(side_effect=first))}
        with mock.patch.dict(sys.modules,modules):
            with self.assertRaises(RuntimeError) as caught:targets.OfficialInterfaces(NS(GetProcessID=42))
        self.assertIs(caught.exception,first);handle.Close.assert_called_once();load.assert_not_called()

    def test_missing_ambiguous_or_unbounded_official_interfaces_have_no_fallback(self):
        interfaces=object.__new__(targets.OfficialInterfaces);interfaces.interfaces={}
        info=NS(GetDocumentation=lambda memid:('IFace2','',0,None),GetTypeAttr=lambda:NS(typekind=4,iid='official'))
        library=NS(GetTypeInfoCount=lambda:2,GetTypeInfo=mock.Mock(return_value=info));interfaces.library=library
        with mock.patch.dict(sys.modules,{'pythoncom':NS(TKIND_DISPATCH=4)}):
            with self.assertRaisesRegex(targets.AssemblyTargetObservationError,'ambiguous'):interfaces.info('IFace2')
            library.GetTypeInfoCount=lambda:4097;library.GetTypeInfo.reset_mock()
            with self.assertRaisesRegex(targets.AssemblyTargetObservationError,'exceeds limit'):interfaces.info('IFace2')
            library.GetTypeInfo.assert_not_called()
            library.GetTypeInfoCount=lambda:1
            with self.assertRaisesRegex(targets.AssemblyTargetObservationError,'missing'):interfaces.info('IEntity')

    def test_resolver_actual_descriptor_drift_and_unbounded_metadata_rejected(self):
        descriptor=json.loads(json.dumps(targets.RESOLVE_DESCRIPTOR))
        interfaces=object.__new__(targets.OfficialInterfaces)
        info=NS(GetTypeAttr=lambda:NS(cFuncs=1),GetFuncDesc=lambda index:descriptor,
                GetDocumentation=lambda memid:('GetObjectByPersistReference3','',0,None),
                GetNames=lambda memid:('GetObjectByPersistReference3','PersistId','ErrorCode'))
        interfaces.info=lambda name:info
        interfaces.check_resolver()
        for field,replacement in ((0,102),(2,[[12,1,None],[3,2,None]]),(8,[12,0,None])):
            bad=json.loads(json.dumps(targets.RESOLVE_DESCRIPTOR));bad[field]=replacement
            info.GetFuncDesc=lambda index:bad
            with self.assertRaises(targets.AssemblyTargetObservationError):interfaces.check_resolver()
        info.GetTypeAttr=lambda:NS(cFuncs=2049)
        info.GetFuncDesc=mock.Mock(side_effect=AssertionError('no metadata reads beyond bound'))
        with self.assertRaises(targets.AssemblyTargetObservationError):interfaces.check_resolver()
        info.GetFuncDesc.assert_not_called()


if __name__=='__main__':unittest.main()
