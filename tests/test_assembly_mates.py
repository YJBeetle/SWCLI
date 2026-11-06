"""Portable ownership/CAS/failure tests; never a claim of native mate acceptance."""
import copy
import json
import sys
import types
import unittest
from contextlib import contextmanager
from types import SimpleNamespace as NS
from unittest import mock

from jsonschema import Draft202012Validator
from swcli.assembly_mates import SNAPSHOT
from swcli.cli import build_parser, _typed_operation
from swcli.daemon import operations
from swcli.daemon.documents import DocumentRegistry, DocumentLeaseConflict
from swcli.hosts import windows_assembly_mates as api
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import validate_operation_result

IDENTITY = [1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.]


class Data:
    def __setattr__(self, key, value):
        object.__setattr__(self, key, value.value if key == 'EntitiesToMate' else value)


class Scene:
    def __init__(self):
        self.cfg = NS(Name='Default')
        self.selection = NS(GetSelectedObjectCount2=lambda mark: 0)
        self.doc = NS(GetType=lambda: 2, GetTitle=lambda: 'Assembly1', GetPathName=lambda: '',
            GetUpdateStamp=lambda: 3, GetSaveFlag=lambda: True, IsOpenedReadOnly=lambda: False,
            IsOpenedViewOnly=lambda: False, GetConfigurationNames=lambda: ('Default',), GetConfigurationCount=lambda: 1,
            GetActiveConfiguration=lambda: self.cfg, SketchManager=NS(ActiveSketch=None),
            SelectionManager=self.selection, Extension=NS(NeedsRebuild2=0), GetEditTargetComponent=lambda: None,
            FirstFeature=None, EditRebuild3=lambda: True)
        self.doc.GetEditTarget=lambda: self.doc
        self.app=NS(IsSame=lambda a,b: int(a is b), ActiveDoc=self.doc)
        self.components=[]
        self.faces=[]
        for c in range(2):
            source=NS(GetType=lambda: 1, GetConfigurationNames=lambda: ('Default',),
                GetConfigurationCount=lambda: 1, GetActiveConfiguration=lambda: self.cfg,
                GetUpdateStamp=lambda: 7, GetSaveFlag=lambda: False, SketchManager=NS(ActiveSketch=None))
            source.GetPathName=lambda c=c: f'C:\\part{c}.SLDPRT'
            component=NS(Name2=f'part{c}-1', GetPathName=source.GetPathName, ReferencedConfiguration='Default',
                GetModelDoc2=lambda source=source: source, GetSuppression2=lambda: 2, IsVirtual=lambda:False,
                GetID=lambda c=c: c+1, IsFixed=lambda c=c: c==0, Transform2=NS(ArrayData=list(IDENTITY)))
            body=NS()
            faces=[]
            for i, kind in enumerate(('plane', 'cylinder')):
                surface=NS(IsPlane=lambda kind=kind: kind=='plane', IsCylinder=lambda kind=kind: kind=='cylinder',
                           PlaneParams=(0,0,1,0,0,0), CylinderParams=(0,0,0,0,0,1,.003))
                face=NS(GetSurface=lambda surface=surface: surface, GetArea=lambda: .001,
                    FaceInSurfaceSense=False, Normal=(0,0,1), GetBody=lambda body=body: body,
                    GetComponent=lambda component=component: component, token=bytes([c,i]))
                faces.append(face)
            body.GetFaces=lambda faces=faces: tuple(faces)
            body.GetFaceCount=lambda: 2
            source.GetBodies2=lambda kind, visible, body=body: (body,)
            component.GetCorresponding=lambda native: native
            self.components.append(component)
            self.faces.append(faces)
        self.doc.GetComponents=lambda top: tuple(reversed(self.components))
        self.doc.GetComponentCount=lambda top: len(self.components)
        self.data=Data()
        self.doc.CreateMateData=mock.Mock(return_value=self.data)
        self.doc.CreateMate=mock.Mock(side_effect=self.create)
        self.error_code=0
        self.suppressed=False
        self.lock_rotation=False

    def create(self, data):
        entities=[NS(ReferenceComponent=face.GetComponent(), Reference=face) for face in data.EntitiesToMate]
        mate=NS(Type=0 if entities[0].Reference.GetSurface().IsPlane() else 1,
                Alignment=data.MateAlignment, GetMateEntityCount=lambda: 2, MateEntity=lambda i: entities[i])
        feature=NS(Name=('Coincident' if mate.Type==0 else 'Concentric')+str(len(getattr(self,'created_features',[]))+1), GetTypeName2=lambda: 'MateCoincident' if mate.Type==0 else 'MateConcentric',
                   GetSpecificFeature2=lambda: mate, GetDefinition=lambda: NS(LockRotation=self.lock_rotation), IsSuppressed2=lambda scope,names: (self.suppressed,),
                   GetNextSubFeature=lambda: None)
        if self.doc.FirstFeature is None:self.created_features=[]
        if self.created_features:self.created_features[-1].GetNextSubFeature=lambda:feature
        self.created_features.append(feature)
        group=NS(Name='Mates', GetTypeName2=lambda: 'MateGroup', GetNextFeature=lambda: None,
                 GetFirstSubFeature=lambda:self.created_features[0])
        self.doc.FirstFeature=group
        return feature

    @property
    def names(self): return [c.Name2 for c in self.components]


class MateTests(unittest.TestCase):
    def setUp(self):
        self.scene=Scene()
        self.patches=[mock.patch.object(api, 'PUBLIC_MATE_WRITES_CALIBRATED', False),
                      mock.patch.object(api, '_saved_external_part', return_value=True),
                      mock.patch.object(api, '_native_windows', return_value=True),
                      mock.patch.object(api, '_dispatch', side_effect=lambda native, interface, **context: native),
                      mock.patch.object(api, 'capture_verified_reference', side_effect=lambda a,e,f: f.token),
                      mock.patch.object(api, 'feature_error', side_effect=lambda f: self.scene.error_code),
                      mock.patch.object(api, '_running_command', return_value={'ui_active':False}),
                      mock.patch.object(api, '_empty_variant', return_value=None),
                      mock.patch.dict(sys.modules, {'pythoncom':NS(VT_ARRAY=1, VT_DISPATCH=2),
                          'win32com.client':NS(VARIANT=lambda typ, value: NS(value=value))})]
        for patch in self.patches: patch.start(); self.addCleanup(patch.stop)
        self.expected=api.snapshot(self.scene.app, self.scene.doc, self.scene.names)[0]
        self.targets=[dict(component=name,face_index=0) for name in self.scene.names]

    def add(self, **values):
        request=dict(app=self.scene.app, document=self.scene.doc, kind='coincident', alignment='aligned',
                     targets=self.targets, expected_value=self.expected, _calibration=True)
        request.update(values)
        result=api.add_mate_windows(**request)
        validate_operation_result('assembly.add-mate', result)
        return result

    def test_snapshot_complete_ordered_and_background_without_selection_or_activation(self):
        self.scene.app.ActiveDoc=object()
        result=api.read_mate_targets_windows(app=self.scene.app, document=self.scene.doc, components=self.scene.names)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['snapshot'], self.expected)
        Draft202012Validator(SNAPSHOT).validate(result['snapshot'])
        self.scene.doc.CreateMate.assert_not_called()

    def test_read_refuses_foreground_identity_change_without_restoring_or_selecting(self):
        original=api.snapshot
        def changed(*args,**kwargs):
            result=original(*args,**kwargs)
            self.scene.app.ActiveDoc=object()
            return result
        with mock.patch.object(api,'snapshot',side_effect=changed):
            result=api.read_mate_targets_windows(app=self.scene.app,document=self.scene.doc,components=self.scene.names)
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['type'],'MateObservationChanged')
        self.scene.doc.CreateMate.assert_not_called()

    def test_public_writes_remain_fail_closed_before_native_acceptance(self):
        self.assertEqual(self.add(_calibration=False)['error']['type'], 'MateWriteNotCalibrated')
        self.scene.doc.CreateMateData.assert_not_called()
        self.scene.doc.CreateMate.assert_not_called()

    def test_public_runtime_permission_is_exact_and_unknown_revision_stays_closed(self):
        self.scene.app.RevisionNumber=lambda:'known-revision'
        with mock.patch.object(api,'PUBLIC_MATE_WRITES_CALIBRATED',True), \
             mock.patch.object(api,'CALIBRATED_WINDOWS_REVISIONS',frozenset({'known-revision'})):
            result=self.add(_calibration=False)
            self.assertTrue(result['ok'],result)
        self.scene.doc.FirstFeature=None
        self.scene.doc.CreateMate.reset_mock()
        for revision in ('different-revision','',None,True):
            self.scene.app.RevisionNumber=lambda revision=revision:revision
            with mock.patch.object(api,'PUBLIC_MATE_WRITES_CALIBRATED',True), \
                 mock.patch.object(api,'CALIBRATED_WINDOWS_REVISIONS',frozenset({'known-revision'})):
                result=self.add(_calibration=False)
            self.assertEqual(result['error']['type'],'MateRuntimeNotCalibrated')
            self.assertFalse(result['mutation']['attempted'])
            self.scene.doc.CreateMate.assert_not_called()

    def test_native_windows_calibration_never_opens_wine_writes(self):
        with mock.patch.object(api,'PUBLIC_MATE_WRITES_CALIBRATED',True), \
             mock.patch.object(api,'_native_windows',return_value=False):
            result=self.add(_calibration=False)
        self.assertEqual(result['error']['type'],'MateRuntimeNotCalibrated')
        self.assertFalse(result['mutation']['attempted'])
        self.scene.doc.CreateMate.assert_not_called()

    def test_coincident_and_concentric_single_native_commit(self):
        for kind, index in (('coincident',0), ('concentric',1)):
            self.scene.doc.FirstFeature=None
            self.scene.doc.CreateMate.reset_mock()
            targets=[dict(component=n,face_index=index) for n in self.scene.names]
            result=self.add(kind=kind, targets=targets)
            self.assertTrue(result['ok'], result)
            self.assertEqual(result['mate']['kind'],kind)
            self.assertEqual(result['mate']['distance_mm'],0)
            self.scene.doc.CreateMate.assert_called_once_with(self.scene.data)

    def test_aligned_concentric_complements_one_aligned_coincident_and_stops_at_two(self):
        self.assertTrue(self.add()['ok'])
        self.expected=api.snapshot(self.scene.app,self.scene.doc,self.scene.names)[0]
        targets=[dict(component=n,face_index=1) for n in self.scene.names]
        second=self.add(kind='concentric',targets=targets)
        self.assertTrue(second['ok'],second)
        self.assertEqual(len(second['snapshot']['mates']),2)
        self.expected=second['snapshot']
        self.scene.doc.CreateMate.reset_mock()
        refused=self.add(kind='concentric',targets=targets)
        self.assertEqual(refused['error']['type'],'UnsupportedMateScope')
        self.assertFalse(refused['mutation']['attempted'])
        self.scene.doc.CreateMate.assert_not_called()

    def test_full_value_cas_rejects_each_snapshot_field_before_definition(self):
        for key, replacement in (('modified',False),('configuration','other'),('path','other'),('update_stamp',4),('mates',[{}])):
            expected=copy.deepcopy(self.expected); expected[key]=replacement
            result=self.add(expected_value=expected)
            self.assertEqual(result['error']['type'],'MateValueConflict')
            self.scene.doc.CreateMateData.assert_not_called()
        expected=copy.deepcopy(self.expected); expected['components'][1]['faces'][0]['parameters'][3]=1
        self.assertEqual(self.add(expected_value=expected)['error']['type'],'MateValueConflict')

    def test_component_config_fixed_suppression_readonly_and_selection_fail_before_commit(self):
        cases=[(self.scene.components[0], 'IsFixed', lambda:False),
               (self.scene.components[1], 'IsFixed', lambda:True),
               (self.scene.components[1], 'GetSuppression2', lambda:0),
               (self.scene.components[1], 'ReferencedConfiguration', 'other'),
               (self.scene.components[1], 'IsVirtual', lambda:True),
               (self.scene.components[1], 'IsVirtual', lambda:None),
               (self.scene.doc,'IsOpenedReadOnly',lambda:True),
               (self.scene.doc,'IsOpenedReadOnly',lambda:0),
               (self.scene.doc,'IsOpenedViewOnly',lambda:True),
               (self.scene.selection,'GetSelectedObjectCount2',lambda mark:1),
               (self.scene.doc,'GetEditTarget',lambda:object())]
        for target,member,value in cases:
            with self.subTest(member=member), mock.patch.object(target,member,value):
                result=self.add()
                self.assertFalse(result['ok'], result)
                self.assertFalse(result['mutation']['attempted'])
                self.scene.doc.CreateMate.assert_not_called()

    def test_component_must_belong_to_selected_assembly_and_face_to_exact_instance(self):
        targets=[dict(component='other',face_index=0),self.targets[1]]
        self.assertEqual(self.add(targets=targets)['error']['type'],'ComponentNotFound')
        with mock.patch.object(self.scene.faces[1][0], 'GetComponent', lambda:self.scene.components[0]):
            self.assertFalse(self.add()['ok'])
        self.scene.doc.CreateMate.assert_not_called()

    def test_missing_saved_external_source_never_reaches_native_creation(self):
        with mock.patch.object(api,'_saved_external_part',return_value=False):
            result=self.add()
        self.assertEqual(result['error']['type'],'ComponentFileUnavailable')
        self.assertFalse(result['mutation']['attempted'])
        self.scene.doc.CreateMate.assert_not_called()

    def test_unknown_native_arrays_booleans_nonfinite_transforms_fail_closed(self):
        for raw in (None,0,'parts'):
            with mock.patch.object(self.scene.doc,'GetComponents',lambda top:raw):
                self.assertFalse(self.add()['ok'])
        for raw in (None,0,'false'):
            with mock.patch.object(self.scene.components[1],'IsFixed',lambda:raw):
                self.assertFalse(self.add()['ok'])
        for index,raw in ((9,float('nan')),(0,2),(12,0)):
            data=list(IDENTITY); data[index]=raw
            with mock.patch.object(self.scene.components[1].Transform2,'ArrayData',data):
                self.assertFalse(self.add()['ok'])
        self.scene.doc.CreateMate.assert_not_called()

    def test_out_of_range_face_and_wrong_surface_fail_before_commit(self):
        for index,code in ((64,'MateTargetNotFound'),(1,'MateSurfaceMismatch'),(-1,'MateTargetNotFound')):
            targets=[dict(component=n,face_index=index) for n in self.scene.names]
            self.assertEqual(self.add(targets=targets)['error']['type'],code)
        self.scene.doc.CreateMate.assert_not_called()

    def test_native_null_and_exception_preserve_uncertain_partial_mutation_without_retry(self):
        for failure in (None, RuntimeError('original native error')):
            self.scene.doc.CreateMate.reset_mock()
            self.scene.doc.CreateMate.side_effect=failure if isinstance(failure,Exception) else None
            self.scene.doc.CreateMate.return_value=None
            result=self.add()
            self.assertFalse(result['ok'])
            self.assertEqual(result['mutation'],dict(attempted=True,creation_returned=False,may_have_changed=True))
            if failure: self.assertIn('original native error',result['error']['message'])
            self.scene.doc.CreateMate.assert_called_once()

    def test_failed_solve_and_suppression_preserve_created_feature_and_evidence(self):
        for member,value in (('error_code',4),('suppressed',True)):
            self.scene.doc.FirstFeature=None
            self.scene.doc.CreateMate.reset_mock()
            with mock.patch.object(self.scene,member,value):
                result=self.add()
            self.assertEqual(result['error']['type'],'MateSolveFailed')
            self.assertTrue(result['mutation']['creation_returned'])
            self.assertIn('mate',result)
            self.scene.doc.CreateMate.assert_called_once()

    def test_concentric_final_lock_rotation_is_read_back_and_cannot_be_hidden_by_staging(self):
        targets=[dict(component=n,face_index=1) for n in self.scene.names]
        self.scene.lock_rotation=True
        result=self.add(kind='concentric',targets=targets)
        self.assertEqual(result['error']['type'],'MateSolveFailed')
        self.assertTrue(result['mate']['lock_rotation'])
        self.assertTrue(result['mutation']['creation_returned'])
        self.scene.doc.CreateMate.assert_called_once()

    def test_rebuild_failure_does_not_retry_creation(self):
        self.scene.doc.EditRebuild3=lambda:False
        result=self.add()
        self.assertEqual(result['error']['type'],'MateSolveFailed')
        self.assertTrue(result['mutation']['creation_returned'])
        self.scene.doc.CreateMate.assert_called_once()

    def test_geometric_relation_uses_rotation_translation_not_reported_native_success(self):
        before=copy.deepcopy(self.expected['components'])
        before[1]['transform'][11]=.02
        first=(before[0],before[0]['faces'][0]);second=(before[1],before[1]['faces'][0])
        self.assertAlmostEqual(api.relation(first,second,'coincident')['distance_mm'],20)
        before[1]['transform'][9]=.01
        self.assertAlmostEqual(api.relation((before[0],before[0]['faces'][1]),
                                          (before[1],before[1]['faces'][1]),'concentric')['distance_mm'],10)


class ContractTests(unittest.TestCase):
    def test_catalog_request_sdk_and_cli_share_complete_contract(self):
        from swcli.sdk._generated import AssemblyOperations
        self.assertTrue(hasattr(AssemblyOperations,'add_mate'))
        self.assertTrue(hasattr(AssemblyOperations,'mate_targets'))
        from swcli.sdk.models import FeatureFilletResultMutation
        self.assertIn('creation_returned',FeatureFilletResultMutation.__annotations__)
        read=OPERATION_CATALOG['assembly.mate-targets']
        write=OPERATION_CATALOG['assembly.add-mate']
        self.assertFalse(read.temporary_activation or read.lease_guarded)
        self.assertTrue(write.temporary_activation and write.lease_guarded)
        self.assertEqual(write.parameters['x-swcli-context']['expected_update_stamp'],'required')
        parsed=_typed_operation(build_parser().parse_args(['assembly','mate-targets','fixed-1','float-1','--document','d-ab12cd','--json']))
        self.assertEqual(parsed[:2],('assembly.mate-targets',{'components':['fixed-1','float-1']}))
        for values in ({'components':['same','same']},{'components':['one']},{'components':['one','two'],'extra':True}):
            with self.assertRaises(ValueError):validate_operation_request('assembly.mate-targets',values)
        Draft202012Validator.check_schema(write.parameters)

    def test_write_lease_and_stamp_conflicts_precede_activation(self):
        scene=Scene(); scene.app.GetDocuments=lambda:(scene.doc,)
        registry=DocumentRegistry(scene.app);entry=registry.register(scene.doc)
        lease=registry.acquire_lease(entry,session_id='owner',ttl_seconds=60)
        expected=dict(title='Assembly1',path='',configuration='Default',update_stamp=3,modified=True,
            components=[dict(name=n,path='x',configuration='Default',native_id=i,fixed=i==0,suppression=2,
                source_update_stamp=1,source_modified=False,transform=IDENTITY,faces=[dict(index=0,
                surface_kind='plane',parameters=[0,0,1,0,0,0],area_mm2=1,sense=False,reference_sha256='0'*64)])
                for i,n in enumerate(scene.names)],mates=[])
        parameters=dict(kind='coincident',alignment='aligned',targets=[dict(component=n,face_index=0) for n in scene.names],expected_value=expected)
        with mock.patch.object(registry,'temporarily_activate') as activate, mock.patch.object(operations,'add_mate_windows') as add:
            with self.assertRaises(DocumentLeaseConflict):
                operations.execute_operation(scene.app,'assembly.add-mate',parameters,documents=registry,
                    document_id=entry.document_id,expected_update_stamp=3,session_id='other')
            with self.assertRaises(operations.DocumentUpdateConflict):
                expected['update_stamp']=2
                operations.execute_operation(scene.app,'assembly.add-mate',parameters,documents=registry,
                    document_id=entry.document_id,expected_update_stamp=2,lease_id=lease['lease_id'],session_id='owner')
            activate.assert_not_called();add.assert_not_called()

class ClientContractTests(unittest.TestCase):
    # Reuse the same strict owned fake to test real SDK/MCP envelopes.
    setUp = MateTests.setUp
    def test_cli_sdk_mcp_preserve_full_snapshot_and_mutation_refusal(self):
        from swcli.sdk import Client
        from swcli.mcp import DaemonBridge
        parameters=dict(kind='coincident',alignment='aligned',targets=self.targets,expected_value=self.expected)
        refusal=api.add_mate_windows(app=self.scene.app,document=self.scene.doc,**parameters)
        envelope=dict(api_version='swcli/v1',request_id='mate-once',success=True,duration_ms=0,result=refusal)
        options=dict(document_id='d-ab12cd',expected_update_stamp=3,lease_id='l-ab12cd34ef56',request_id='mate-once')
        args=['assembly','add-mate','--kind','coincident','--alignment','aligned',
              '--targets',json.dumps(self.targets),'--expected-value',json.dumps(self.expected),
              '--document','d-ab12cd','--if-update-stamp','3','--lease','l-ab12cd34ef56','--json']
        parsed=_typed_operation(build_parser().parse_args(args))
        self.assertEqual(parsed[:2],('assembly.add-mate',parameters))
        with mock.patch('swcli.sdk.client.call_daemon',return_value=envelope) as wire:
            result=Client(session_id='mates').assembly.add_mate(**parameters,**options)
            self.assertEqual(result.raw['result'],refusal)
            self.assertEqual(wire.call_args.args,('assembly.add-mate',parameters))
            self.assertEqual(wire.call_args.kwargs['expected_update_stamp'],3)
            self.assertEqual(wire.call_args.kwargs['lease_id'],options['lease_id'])
            self.assertEqual(wire.call_args.kwargs['session_id'],'mates')
        with mock.patch('swcli.mcp.DaemonManager'), mock.patch('swcli.mcp.call_daemon',return_value=envelope) as wire:
            result=DaemonBridge(session_id='mates').call('execute',dict(operation='assembly.add-mate',parameters=parameters,**options))
            self.assertEqual(result['result'],refusal)
            self.assertEqual(wire.call_args.args,('assembly.add-mate',parameters))
            self.assertEqual(wire.call_args.kwargs['expected_update_stamp'],3)
            self.assertEqual(wire.call_args.kwargs['lease_id'],options['lease_id'])
            self.assertEqual(wire.call_args.kwargs['session_id'],'mates')
        self.scene.doc.CreateMate.assert_not_called()

class DispatchInterfaceTests(unittest.TestCase):
    def test_nested_object_need_not_implement_get_type_info(self):
        raw=object()
        target=NS(_oleobj_=NS(GetTypeInfo=mock.Mock(side_effect=RuntimeError('Invalid index')),
                             QueryInterface=mock.Mock(return_value=raw)))
        interface=NS(GetDocumentation=lambda memid:('IFace2',),
                     GetTypeAttr=lambda:NS(typekind=4,iid='official-face-iid'))
        library=NS(GetLibAttr=lambda:('official-library',0,0,33,0,0),
                   GetTypeInfoCount=lambda:1,GetTypeInfo=lambda index:interface)
        application_info=NS(GetContainingTypeLib=lambda:(library,0))
        app=NS(_oleobj_=NS(GetTypeInfo=mock.Mock(return_value=application_info)))
        modules={'pythoncom':NS(TKIND_DISPATCH=4,IID_IDispatch='dispatch-iid'),
                 'win32com.client':NS(Dispatch=lambda native:native)}
        with mock.patch.dict(sys.modules,modules),mock.patch.dict(api._INTERFACE_IIDS,{},clear=True), \
             mock.patch.object(api,'_official_library',return_value=library) as resolve:
            result=api._dispatch(target,'IFace2',app=app)
        resolve.assert_called_once_with(app)
        self.assertIs(result,raw)
        target._oleobj_.GetTypeInfo.assert_not_called()
        target._oleobj_.QueryInterface.assert_called_once_with('official-face-iid','dispatch-iid')
        app._oleobj_.GetTypeInfo.assert_not_called()

    def test_library_is_derived_from_exact_host_process_image_and_handle_is_closed(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'sldworks.tlb').write_bytes(b'official fixture library')
            handle=NS(Close=mock.Mock());library=object()
            open_process=mock.Mock(return_value=handle)
            load=mock.Mock(return_value=library)
            modules={'pythoncom':NS(LoadTypeLib=load),'win32api':NS(OpenProcess=open_process),
                'win32con':NS(PROCESS_QUERY_INFORMATION=1,PROCESS_VM_READ=2),
                'win32process':NS(GetModuleFileNameEx=lambda process,module:str(root/'SLDWORKS.exe'))}
            with mock.patch.dict(sys.modules,modules),mock.patch.dict(api._OFFICIAL_LIBRARIES,{},clear=True):
                result=api._official_library(NS(GetProcessID=lambda:77))
            self.assertIs(result,library)
            open_process.assert_called_once_with(3,False,77)
            handle.Close.assert_called_once_with()
            load.assert_called_once_with(str(root/'sldworks.tlb'))

    def test_saved_external_part_requires_exact_extension_and_nonempty_real_file(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'part.SLDPRT'
            self.assertFalse(api._saved_external_part(str(path)))
            path.touch()
            self.assertFalse(api._saved_external_part(str(path)))
            path.write_bytes(b'saved fixture')
            self.assertTrue(api._saved_external_part(str(path)))
            other=Path(directory)/'part.SLDASM';other.write_bytes(b'assembly')
            self.assertFalse(api._saved_external_part(str(other)))
