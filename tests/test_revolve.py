"""Portable intent, contract, refusal and first-failure boundaries (not native acceptance)."""

from copy import deepcopy
import importlib.util
import math
import contextlib
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from swcli.cli import build_parser, _typed_operation
from swcli.hosts import windows_revolves as worker
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import validate_operation_result, OperationResultInvalid
from swcli.revolve_geometry import validate_revolve_intent, cylinder_expectation, verify_cylinder_metrics
from swcli.sdk import Client

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]
VALUES = dict(sketch_id="s-ab12cd", expected_profile_mm=[0,-5,10,15], axis_mm=[0,-5,0,15], angle_deg=360)
CONSTANTS = dict(swEndCondBlind=73, swThinWallOneDirection=74, swRevolveTypeOneDirection=75, swSelSKETCHSEGS=76)


class IntentTests(unittest.TestCase):
    def test_complete_intent_refuses_crossing_axis_invalid_angle_and_unresolved_geometry(self):
        validate_revolve_intent(VALUES['expected_profile_mm'], VALUES['axis_mm'], 360)
        for bounds, axis, angle in (([-5,-5,5,15],[0,-5,0,15],360),
            ([0,-5,10,15],[5,-5,5,15],360), ([0,-5,10,15],[0,15,0,-5],360),
            ([0,-5,10,15],[0,-5,0,15],0), ([0,0,1e-9,10],[0,0,0,10],360),
            ([0,-5,math.inf,15],[0,-5,0,15],360), ([False,-5,10,15],[0,-5,0,15],360)):
            with self.subTest(bounds=bounds,axis=axis,angle=angle), self.assertRaises(ValueError):
                validate_revolve_intent(bounds,axis,angle)

    def test_cylinder_oracle_independently_checks_volume_area_centroid_and_body_count(self):
        expected = cylinder_expectation(VALUES['expected_profile_mm'], IDENTITY)
        self.assertAlmostEqual(expected['volume_mm3'], 2000*math.pi)
        self.assertAlmostEqual(expected['surface_area_mm2'], 600*math.pi)
        self.assertEqual(expected['centroid_mm'],dict(x=0,y=5,z=0))
        verify_cylinder_metrics(expected, expected)
        for key, value in (('volume_mm3',1999*math.pi),('surface_area_mm2',599*math.pi),
                           ('solid_body_count',2),('volume_mm3',float('nan'))):
            actual=deepcopy(expected);actual[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):verify_cylinder_metrics(actual,expected)
        for axis in 'xyz':
            actual=deepcopy(expected);actual['centroid_mm'][axis]+=0.001
            with self.assertRaises(ValueError):verify_cylinder_metrics(actual,expected)

    def test_inverse_rotation_uses_native_row_vector_transform_convention(self):
        # Positive 90-degree rotation about X: local Y corresponds to model -Z.
        transform=[1,0,0,0,0,1,0,-1,0,0,0,0,1,0,0,0]
        self.assertEqual(cylinder_expectation([0,-5,10,15],transform)['centroid_mm'],dict(x=0,y=0,z=-5))
        for index, value in ((12,2),(0,2),(9,1)):
            changed=IDENTITY[:];changed[index]=value
            with self.assertRaises(ValueError):cylinder_expectation([0,-5,10,15],changed)


class ContractTests(unittest.TestCase):
    def test_request_requires_document_stamp_and_complete_geometry(self):
        spec=OPERATION_CATALOG['feature.revolve']
        self.assertTrue(spec.lease_guarded)
        self.assertTrue(spec.temporary_activation)
        self.assertIn('native Windows SW 33.5.0',spec.parameters['title'])
        schema=Draft202012Validator(spec.parameters)
        self.assertTrue(schema.is_valid(VALUES))
        for context in ({},{'document_id':'d-ab12cd'},{'expected_update_stamp':1}):
            with self.assertRaises(ValueError):validate_operation_request('feature.revolve',VALUES,**context)
        validate_operation_request('feature.revolve',VALUES,document_id='d-ab12cd',expected_update_stamp=1)
        for key in VALUES:
            changed=deepcopy(VALUES);del changed[key]
            self.assertFalse(schema.is_valid(changed))
        changed=deepcopy(VALUES);changed['angle_deg']=180
        self.assertTrue(schema.is_valid(changed))
        validate_operation_request('feature.revolve',changed,document_id='d-ab12cd',expected_update_stamp=1)

    def test_cli_and_sdk_forward_all_intent_and_context(self):
        args=build_parser().parse_args(['feature','revolve','s-ab12cd','--expected-profile-mm','0','-5','10','15',
            '--axis-mm','0','-5','0','15','--angle-deg','360','--document','d-ab12cd','--if-update-stamp','12','--lease','l-abcdefghjkmn','--json'])
        operation,values,as_json,document,stamp,lease=_typed_operation(args)
        self.assertEqual((operation,values,as_json,document,stamp,lease),('feature.revolve',VALUES,True,'d-ab12cd',12,'l-abcdefghjkmn'))
        client=Client(endpoint='127.0.0.1:18495',session_id='revolve')
        with mock.patch.object(client,'_execute',return_value={'ok':False}) as execute:
            client.feature.revolve(**VALUES,document_id='d-ab12cd',expected_update_stamp=12,lease_id='l-abcdefghjkmn')
        self.assertEqual(execute.call_args.args,('feature.revolve',VALUES))
        self.assertEqual(execute.call_args.kwargs['expected_update_stamp'],12)

    def test_unknown_native_scope_does_not_observe_or_mutate_com_or_fake_success(self):
        result,feature=worker.create_revolve_windows_with_handle(app=object(),document=object(),sketch_feature=object(),
            **{k:v for k,v in VALUES.items() if k!='sketch_id'})
        self.assertIsNone(feature)
        self.assertEqual(result['error']['type'],'RevolveNotCalibrated')
        result['sketch_id']=VALUES['sketch_id']
        validate_operation_result('feature.revolve',result)
        changed=deepcopy(result);changed['ok']=True;changed.pop('error')
        with self.assertRaises(OperationResultInvalid):validate_operation_result('feature.revolve',changed)
        changed=deepcopy(result);changed['mutation']['may_have_changed']=True
        with self.assertRaises(OperationResultInvalid):validate_operation_result('feature.revolve',changed)

    def test_mcp_execute_uses_the_same_operation_and_context_contract(self):
        from swcli.mcp import tool_definitions
        # Generic MCP execute is the only modeling surface, with no COM bypass.
        tools=tool_definitions()
        execute=next(item for item in tools if item['name']=='execute')
        schema=execute['inputSchema']
        self.assertIn('parameters',schema['properties'])
        from swcli.mcp import DaemonBridge
        from swcli import PROTOCOL_VERSION
        response=dict(api_version=PROTOCOL_VERSION,request_id='revolve-request',success=False,
                      duration_ms=1,error=dict(code='RevolveNotCalibrated',message='gate closed'))
        with mock.patch('swcli.mcp.call_daemon',return_value=response) as call:
            bridge=DaemonBridge(session_id='revolve-test')
            observed=bridge.call('execute',dict(operation='feature.revolve',parameters=VALUES,
                document_id='d-ab12cd',expected_update_stamp=12,lease_id='l-abcdefghjkmn',request_id='revolve-request'))
        self.assertEqual(observed,response)
        self.assertEqual(call.call_args.args,('feature.revolve',VALUES))
        self.assertEqual(call.call_args.kwargs['expected_update_stamp'],12)
        self.assertEqual(call.call_args.kwargs['document_id'],'d-ab12cd')
        for key in ('document_id','expected_update_stamp','lease_id'):
            self.assertIn(key,schema['properties'])


class PlatformScopeTests(unittest.TestCase):
    def test_only_the_exact_native_windows_revision_is_eligible(self):
        app=NS(RevisionNumber='33.5.0')
        with mock.patch('sys.platform','win32'),mock.patch('ctypes.WinDLL',create=True,return_value=NS()):
            self.assertEqual(worker._native_constants(app),worker._CALIBRATED_CONSTANTS)
            app.RevisionNumber='33.4.0'
            self.assertIsNone(worker._native_constants(app))
        with mock.patch('sys.platform','win32'),mock.patch('ctypes.WinDLL',create=True,return_value=NS(wine_get_version=object())):
            self.assertIsNone(worker._native_constants(NS(RevisionNumber='33.5.0')))
        with mock.patch('sys.platform','win32'),mock.patch('ctypes.WinDLL',create=True,side_effect=OSError('unknown platform')):
            self.assertIsNone(worker._native_constants(app))


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.selected=[]
        self.axis=NS(GetStartPoint2=NS(X=0,Y=-.005,Z=0),GetEndPoint2=NS(X=0,Y=.015,Z=0))
        self.axis.Select4=lambda append,data:self.selected.append((self.axis,data.Mark)) or True
        self.sketch=NS(Is3D=False,ModelToSketchTransform=NS(ArrayData=IDENTITY))
        self.profile=NS(bounds_mm=(0,-5,10,15),left_edge=self.axis,construction_segment_count=2,native_segment_count=6)
        self.sketch_feature=NS(GetSpecificFeature2=self.sketch)
        self.sketch_feature.Select2=lambda append,mark:self.selected.append((self.sketch_feature,mark)) or True
        self.definition=NS(AccessSelections=mock.Mock(return_value=True), ReleaseSelectionAccess=mock.Mock(spec=lambda:None),
            GetRevolutionAngle=lambda forward:2*math.pi,ReverseDirection=False,Type=75,IsBossFeature=True,
            IsThinFeature=False,Merge=True,GetAxisType=76,GetContoursCount=0,Axis=self.axis)
        self.feature=NS(Name='Revolve',GetTypeName2='Revolution',GetDefinition=self.definition)
        def created(*args):
            self.document.GetBodies2.return_value = (object(),)
            return self.feature
        self.create=mock.Mock(side_effect=created)
        self.document=NS(GetType=1,IsOpenedReadOnly=False,IsOpenedViewOnly=False,GetConfigurationNames=['Default'],
            GetConfigurationCount=1,GetBodies2=mock.Mock(return_value=()),
            SelectionManager=NS(GetSelectedObjectCount2=lambda mark:len(self.selected),CreateSelectData=NS(Mark=0),
                GetSelectedObject6=lambda index,mark:next(obj for obj,m in self.selected if m==mark)),
            FeatureManager=NS(FeatureRevolve2=self.create),ClearSelection2=lambda all:self.selected.clear(),EditRebuild3=True)
        self.app=NS()
        self.state=dict(configuration='Default',update_stamp=1,modified=True,editing=False)
        for name,value in (('_state',(self.state,None,self.document)),('_running_command',{'ui_active':False}),
            ('_unabsorbed_profile',self.sketch_feature),('observe_rectangle_profile',self.profile),
            ('_diagnose_features',{'healthy':True,'truncated':False}),
            ('_null_dispatch',None),('measure_part_windows',dict(ok=True,metrics=cylinder_expectation([0,-5,10,15],IDENTITY)))):
            patch=mock.patch.object(worker,name,return_value=value);patch.start();self.addCleanup(patch.stop)
        patch=mock.patch.object(worker,'_same',side_effect=lambda app,a,b:a is b);patch.start();self.addCleanup(patch.stop)

    def call(self, **updates):
        return worker._calibrate_revolve_windows_with_handle(app=self.app,document=self.document,sketch_feature=self.sketch_feature,
            **{**{k:v for k,v in VALUES.items() if k!='sketch_id'},'constants':CONSTANTS,**updates})

    def test_exact_axis_native_arguments_and_readback(self):
        result,feature=self.call()
        self.assertTrue(result['ok'],result)
        self.assertIs(feature,self.feature)
        self.assertEqual(self.create.call_count,1)
        self.assertEqual(self.create.call_args.args,(True,True,False,False,False,False,73,73,2*math.pi,0.0,
            False,False,0.0,0.0,74,0.0,0.0,True,False,False))
        self.assertEqual(self.selected,[])
        self.definition.ReleaseSelectionAccess.assert_called_once()

    def test_success_result_requires_independent_geometry_angle_and_exact_handle(self):
        from test_result_schemas import DOCUMENT
        from test_windows_features import DIAGNOSTICS
        result,feature=self.call()
        result.update(sketch_id=VALUES['sketch_id'],document=DOCUMENT,diagnostics=DIAGNOSTICS)
        result['feature']['feature_id']='f-ab12cd'
        result['definition'].update(kind=0,axis_type=10)
        validate_operation_result('feature.revolve',result)
        for mutate in (lambda r:r['definition'].update(angle_rad=math.pi),
                       lambda r:r['metrics'].update(volume_mm3=1),
                       lambda r:r['metrics']['centroid_mm'].update(z=2),
                       lambda r:r['feature'].pop('feature_id')):
            changed=deepcopy(result);mutate(changed)
            with self.assertRaises(OperationResultInvalid):validate_operation_result('feature.revolve',changed)

    def test_partial_native_mutation_retains_first_error_and_handle_without_retry(self):
        self.definition.GetRevolutionAngle=lambda forward:math.pi
        self.definition.ReleaseSelectionAccess.side_effect=RuntimeError('second release error')
        result,feature=self.call()
        self.assertFalse(result['ok'])
        self.assertIs(feature,self.feature)
        self.assertEqual(result['error']['type'],'RevolveDefinitionMismatch')
        self.assertTrue(all(result['mutation'].values()))
        self.assertIn('second release error',result['definition']['cleanup_errors'][0]['error'])
        self.create.assert_called_once()
        self.assertEqual(self.selected,[])

    def test_null_and_throwing_creation_remain_uncertain_partial_mutations(self):
        for value in (None, RuntimeError('first native failure')):
            self.create.reset_mock();self.create.side_effect=value if isinstance(value,Exception) else None;self.create.return_value=None
            result,feature=self.call()
            self.assertFalse(result['ok'])
            self.assertIsNone(feature)
            self.assertEqual(result['mutation'],dict(attempted=True,creation_returned=False,may_have_changed=True))
            self.create.assert_called_once()

    def test_unreadable_created_metadata_retains_partial_state_in_a_valid_failure_result(self):
        for name,kind in ((None,'Revolution'),('NativeUnexpected','Cut')):
            with self.subTest(name=name,kind=kind):
                self.document.GetBodies2.return_value=()
                self.feature.Name=name;self.feature.GetTypeName2=kind
                result,feature=self.call()
                self.assertFalse(result['ok'])
                self.assertIs(feature,self.feature)
                self.assertTrue(all(result['mutation'].values()))
                result['sketch_id']=VALUES['sketch_id']
                validate_operation_result('feature.revolve',result)

    def test_unavailable_definition_values_preserve_the_original_partial_failure(self):
        for member in ('GetRevolutionAngle','ReverseDirection','Type','IsBossFeature','IsThinFeature','Merge','GetAxisType','GetContoursCount'):
            with self.subTest(member=member):
                before=getattr(self.definition,member)
                setattr(self.definition,member,(lambda forward:None) if member=='GetRevolutionAngle' else None)
                self.document.GetBodies2.return_value=()
                result,feature=self.call()
                setattr(self.definition,member,before)
                self.assertFalse(result['ok'])
                self.assertEqual(result['error']['type'],'RevolveDefinitionMismatch')
                self.assertIs(feature,self.feature)
                self.assertTrue(all(result['mutation'].values()))
                result['sketch_id']=VALUES['sketch_id']
                validate_operation_result('feature.revolve',result)

    def test_uncalibrated_origin_plane_frame_refuses_before_native_creation(self):
        c=math.sqrt(0.5)
        self.sketch.ModelToSketchTransform.ArrayData=[c,c,0,-c,c,0,0,0,1,0,0,0,1,0,0,0]
        result,feature=self.call()
        self.assertEqual(result['error']['type'],'UnsupportedRevolvePlane')
        self.assertFalse(any(result['mutation'].values()))
        self.assertIsNone(feature)
        self.create.assert_not_called()
        self.assertEqual(self.selected,[])

    def test_readonly_multibody_and_profile_cas_refuse_before_selection(self):
        for field,value,error in (('IsOpenedReadOnly',True,'DocumentReadOnly'),
                                 ('GetBodies2',lambda *args:(object(),object()),'UnsupportedRevolveBodyScope')):
            before=getattr(self.document,field);setattr(self.document,field,value)
            result,_=self.call();setattr(self.document,field,before)
            self.assertEqual(result['error']['type'],error)
            self.assertFalse(any(result['mutation'].values()))
            self.create.assert_not_called();self.assertEqual(self.selected,[])
        self.profile.bounds_mm=(-5,-5,5,15)
        result,_=self.call()
        self.assertEqual(result['error']['type'],'RevolveProfileConflict')
        self.create.assert_not_called()


class DaemonGuardTests(unittest.TestCase):
    def setUp(self):
        from swcli.daemon.documents import DocumentRegistry
        self.target=NS(GetTitle=lambda:'Target',GetPathName=lambda:'',GetType=lambda:1,
                       GetSaveFlag=lambda:False,GetUpdateStamp=lambda:12)
        self.foreground=NS(GetTitle=lambda:'Foreground',GetPathName=lambda:'',GetType=lambda:1,GetSaveFlag=lambda:False)
        self.app=NS(ActiveDoc=self.foreground,GetDocuments=lambda:[self.target],IsSame=lambda a,b:int(a is b),
                    ActivateDoc3=mock.Mock())
        self.registry=DocumentRegistry(self.app)
        self.entry=self.registry.register(self.target)
        self.feature=object()
        patch=mock.patch.object(self.registry,'resolve_sketch',return_value=self.feature)
        self.resolve=patch.start();self.addCleanup(patch.stop)
        @contextlib.contextmanager
        def activation(entry):
            previous=self.app.ActiveDoc
            self.app.ActiveDoc=entry.document
            try:yield []
            finally:self.app.ActiveDoc=previous
        patch=mock.patch.object(self.registry,'temporarily_activate',side_effect=activation)
        self.activate=patch.start();self.addCleanup(patch.stop)

    def call(self,values=None,**context):
        from swcli.daemon.operations import execute_operation
        return execute_operation(self.app,'feature.revolve',VALUES if values is None else values,documents=self.registry,session_id='writer',
            document_id=self.entry.document_id,**{'expected_update_stamp':12,**context})

    def test_update_and_lease_conflicts_precede_native_adapter(self):
        from swcli.daemon.operations import DocumentUpdateConflict
        from swcli.daemon.documents import DocumentLeaseConflict
        with mock.patch.object(worker,'create_revolve_windows_with_handle') as adapter:
            with self.assertRaises(DocumentUpdateConflict):self.call(expected_update_stamp=13)
            self.registry.acquire_lease(self.entry,session_id='other',ttl_seconds=60)
            with self.assertRaises(DocumentLeaseConflict):self.call()
        adapter.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()

    def test_partial_creation_and_registration_failure_keep_first_error_and_mutation(self):
        partial=dict(ok=False,action='feature.revolve',mutation=dict(attempted=True,creation_returned=True,may_have_changed=True),
                     cleanup_errors=[],feature=dict(name='Revolve',type='Revolution'),
                     error=dict(type='FirstNativeFailure',message='original verification failed'))
        with mock.patch.object(worker,'create_revolve_windows_with_handle',return_value=(partial,object())), \
             mock.patch.object(self.registry,'register_feature',side_effect=RuntimeError('secondary registration failure')), \
             mock.patch.object(self.entry.entities,'retire_scope') as retire:
            result=self.call()
        self.assertEqual(result['error'],dict(type='FirstNativeFailure',message='original verification failed'))
        self.assertTrue(all(result['mutation'].values()))
        self.assertEqual(result['cleanup_errors'],[dict(stage='register-created-feature',error='secondary registration failure')])
        retire.assert_called_once()

    def test_partial_refusal_precedes_activation_adapter_and_entity_retirement(self):
        values = dict(VALUES, angle_deg=90)
        with mock.patch.object(worker, 'create_revolve_windows_with_handle') as adapter, \
             mock.patch.object(self.entry.entities, 'retire_scope') as retire:
            result = self.call(values=values)
        validate_operation_result('feature.revolve', result)
        self.assertEqual(result['angle_deg'], 90)
        self.assertEqual(result['error']['type'], 'RevolveNotCalibrated')
        self.assertFalse(any(result['mutation'].values()))
        self.activate.assert_not_called()
        adapter.assert_not_called()
        retire.assert_not_called()
        self.assertIs(self.app.ActiveDoc, self.foreground)
        self.resolve.assert_called()

    def test_partial_refusal_preserves_lease_stamp_and_reference_guards(self):
        from swcli.daemon.operations import DocumentUpdateConflict
        from swcli.daemon.documents import DocumentLeaseConflict
        values = dict(VALUES, angle_deg=180)
        with self.assertRaises(DocumentUpdateConflict):
            self.call(values=values, expected_update_stamp=13)
        self.resolve.side_effect = ValueError('unknown sketch')
        with self.assertRaisesRegex(ValueError, 'unknown sketch'):
            self.call(values=values)
        self.resolve.side_effect = None
        self.registry.acquire_lease(self.entry, session_id='other', ttl_seconds=60)
        with self.assertRaises(DocumentLeaseConflict):
            self.call(values=values)
        self.activate.assert_not_called()

    def test_closed_background_call_preserves_foreground_and_current_session(self):
        result=self.call()
        validate_operation_result('feature.revolve',result)
        self.assertEqual(result['error']['type'],'RevolveNotCalibrated')
        self.assertIs(self.app.ActiveDoc,self.foreground)
        self.app.ActivateDoc3.assert_not_called()
        self.resolve.assert_called()


class WiringTests(unittest.TestCase):
    def test_ci_is_manual_default_off_exact_branch_and_keeps_default_gates(self):
        workflow=(ROOT/'.github/workflows/ci.yml').read_text()
        input_block=workflow.split('      native_revolve_calibration:',1)[1].split('      native_full:',1)[0]
        self.assertIn('default: false',input_block)
        step=workflow.split('      - name: Calibrate bounded revolve candidate',1)[1].split('      - name:',1)[0]
        for text in ("github.event_name == 'workflow_dispatch'",'!inputs.native_full',
                     "github.ref == 'refs/heads/codex/swcli-revolve-feature'",'timeout-minutes: 31',
                     'verify-revolve-calibration.py','--swconst','--sldworks'):
            self.assertIn(text,step)
        self.assertIn("needs.test.result == 'success' && needs.package.result == 'success'",workflow)
        self.assertIn("needs.tag-policy.result == 'success'",workflow)
        self.assertNotIn("pull_request_target",workflow)
        self.assertIn("inputs.native_revolve_calibration && format('swcli-revolve-calibration-{0}', github.ref) || 'swcli-hosted-windows-solidworks'",workflow)
        self.assertIn('cancel-in-progress: false',workflow.split('  solidworks-e2e:',1)[1].split('    env:',1)[0])
        self.assertIn('Internal revolve calibration only; see revolve-calibration/report.json. Public acceptance is false.',workflow)
        summary=workflow.split('      - name: Summarize public test evidence',1)[1].split('      - name:',1)[0]
        self.assertIn('if: always()',summary)
        self.assertLess(summary.index('exit 0'),summary.index('--scope windows-installed-full'))

    def test_public_ci_is_default_off_exact_branch_and_has_its_own_profile(self):
        workflow=(ROOT/'.github/workflows/ci.yml').read_text()
        declaration=workflow.split('      native_revolve_public:',1)[1].split('      native_revolve_calibration:',1)[0]
        self.assertIn('default: false',declaration)
        step=workflow.split('      - name: Verify bounded revolve through public CLI and daemon',1)[1].split('      - name:',1)[0]
        for value in ("github.event_name == 'workflow_dispatch'",'inputs.native_revolve_public',
                      '!inputs.native_revolve_calibration','!inputs.native_full',
                      "github.ref == 'refs/heads/codex/swcli-revolve-feature'",'timeout-minutes: 31'):
            self.assertIn(value,step)
        self.assertIn("inputs.native_revolve_public && format('swcli-revolve-public-{0}', github.ref)",workflow)
        self.assertIn('not complete full acceptance',workflow)
        control=workflow.split('      - name: Verify native partial mutation with an internal observation fault',1)[1].split('      - name:',1)[0]
        for value in ('inputs.native_revolve_public','!inputs.native_revolve_calibration','!inputs.native_full',
                      "github.ref == 'refs/heads/codex/swcli-revolve-feature'",'timeout-minutes: 31','revolve-partial-control'):
            self.assertIn(value,control)
        self.assertLess(workflow.index('Verify native partial mutation'),workflow.index('Verify bounded revolve through public CLI'))

    def test_calibration_retains_full_turn_oracles_and_fails_on_first_error_without_retry(self):
        script=(ROOT/'scripts/ci/verify-revolve-calibration.py').read_text()
        for text in ('threading.Timer(600, timeout)','child.wait(timeout=1800)',
                     'read_type_libraries','file_sha256','reopened_definition','verify_cylinder_metrics',
                     'axis_crossing_rejection','multibody_rejection','public_acceptance=False',
                     'injected-postcreation-observation-failure','partial-preserved-measure','reopen-partial-evidence'):
            self.assertIn(text,script)


if __name__ == '__main__':
    unittest.main()
