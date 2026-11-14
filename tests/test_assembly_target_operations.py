"""Public B uses the real private observer with fake official COM interfaces."""
from copy import deepcopy
import threading
from types import SimpleNamespace as NS
import unittest
from unittest import mock

from swcli.assembly_target_contracts import census_value
from swcli.cli import build_parser, _typed_operation
from swcli.daemon.documents import DocumentRegistry, DocumentLeaseConflict
from swcli.daemon.operations import execute_operation, DocumentUpdateConflict
from swcli.daemon.assembly_targets import AssemblyTargetNotFound, AssemblyTargetStale, AssemblyTargetConflict
from swcli.daemon import assembly_target_operations as gate
from swcli.hosts import windows_assembly_target_observation as native
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import OperationResultInvalid, validate_operation_result
from swcli.sdk import Client

import test_active_assembly_target_observation as fixture_module


class AssemblyTargetOperationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture_module.ActiveAssemblyTargetsTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.app, self.doc = self.f.app, self.f.assembly
        self.doc.GetTitle = lambda: 'assembly'
        self.f.source.GetTitle = lambda: 'source'
        self.app.GetDocuments = lambda: (self.doc, self.f.source)
        self.documents = DocumentRegistry(self.app)
        self.entry = self.documents.register(self.doc)
        self.registry = self.entry.assembly_targets
        self.lease = self.documents.acquire_lease(self.entry, session_id='reader', ttl_seconds=60)['lease_id']

    def call(self, name='assembly.targets.list', values=None, session='reader', **context):
        return execute_operation(self.app, name, values if values is not None else {'components': self.f.names},
            documents=self.documents, session_id=session, document_id=self.entry.document_id,
            expected_update_stamp=context.pop('expected_update_stamp', 7),
            lease_id=context.pop('lease_id', self.lease), **context)

    def listed(self):
        result = self.call()
        validate_operation_result('assembly.targets.list', result)
        self.assertEqual(len(result['targets']), 4)
        self.assertNotIn('scope', result['census'])
        self.assertFalse(result['read_gate']['write_authorized'])
        self.assertFalse(result['read_gate']['mate_tree_compared'])
        return result

    @staticmethod
    def parameters(result):
        return {'snapshot_id': result['snapshot_id'], 'target_ids': [t['target_id'] for t in result['targets'][:2]]}

    def validate(self, result, **context):
        return self.call('assembly.targets.validate', self.parameters(result), **context)

    def reset_native_counts(self):
        for getter in self.f.owners:
            getter.reset_mock()
        self.f.extension.GetObjectByPersistReference3.reset_mock()
        self.f.extension.GetPersistReference3.reset_mock()

    def assert_owner_count(self, count):
        self.assertEqual([g.call_count for g in self.f.owners], [count]*4)
        for getter in self.f.original_getters:
            getter.assert_not_called()
        self.f.source_getter.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()
        self.doc.CreateMate.assert_not_called()

    def test_list_and_validate_selected_two_still_read_all_four_once(self):
        first = self.listed()
        self.assert_owner_count(1)
        issued = set(self.registry.issued_ids)
        self.reset_native_counts()
        checked = self.validate(first)
        validate_operation_result('assembly.targets.validate', checked)
        self.assertEqual(checked['snapshot_id'], first['snapshot_id'])
        self.assertEqual(checked['census'], first['census'])
        self.assertTrue(checked['unchanged'])
        self.assertEqual(self.registry.issued_ids, issued)
        self.assert_owner_count(1)
        self.assertEqual(self.f.extension.GetObjectByPersistReference3.call_count, 4)

    def test_new_list_retires_previous_batch_without_token_reuse(self):
        old = self.listed()
        new = self.listed()
        self.assertNotEqual(old['snapshot_id'], new['snapshot_id'])
        self.assertTrue(set(t['target_id'] for t in old['targets']).isdisjoint(t['target_id'] for t in new['targets']))
        self.reset_native_counts()
        with self.assertRaises(AssemblyTargetStale): self.validate(old)
        self.assert_owner_count(0)
        self.validate(new)

    def test_background_is_explicit_and_before_any_owner_or_interface(self):
        old = self.listed()
        self.reset_native_counts()
        self.app.ActiveDoc = self.f.source
        with self.assertRaises(native.AssemblyTargetObservationError) as caught:
            self.validate(old)
        self.assertEqual(gate.error_code(caught.exception), 'AssemblyNotActive')
        self.assert_owner_count(0)
        self.assertFalse(self.registry.snapshots)
        self.app.ActiveDoc = self.doc
        with self.assertRaises(AssemblyTargetStale): self.validate(old)

    def test_wrong_kind_session_snapshot_and_target_rejected_before_observer(self):
        old = self.listed()
        self.reset_native_counts()
        p = self.parameters(old)
        p['target_ids'][0] = 'e-abc123'
        with self.assertRaises(ValueError): self.call('assembly.targets.validate', p)
        p = self.parameters(old);p['target_ids'][0] = 'at-'+'0'*32
        with self.assertRaises(AssemblyTargetNotFound): self.call('assembly.targets.validate', p)
        self.documents.release_lease(self.lease, session_id='reader')
        lease = self.documents.acquire_lease(self.entry, session_id='other', ttl_seconds=60)['lease_id']
        with self.assertRaises(AssemblyTargetNotFound): self.validate(old, session='other', lease_id=lease)
        self.assert_owner_count(0)

    def test_missing_expired_or_other_session_lease_precedes_owner(self):
        old = self.listed();self.reset_native_counts()
        with self.assertRaises(ValueError): self.validate(old, lease_id=None)
        with self.assertRaises(DocumentLeaseConflict): self.validate(old, session='other')
        self.documents.release_lease(self.lease, session_id='reader')
        with self.assertRaises(Exception) as caught: self.validate(old)
        self.assertEqual(type(caught.exception).__name__, 'DocumentLeaseNotFound')
        self.assert_owner_count(0)

    def test_all_known_scope_changes_retire_and_stop_before_owner(self):
        changes = [
            lambda: setattr(self.doc, 'GetUpdateStamp', lambda: 8),
            lambda: setattr(self.f.source, 'GetUpdateStamp', lambda: 8),
            lambda: setattr(self.doc.ConfigurationManager.ActiveConfiguration, 'Name', 'Other'),
            lambda: setattr(self.f.components[1], 'IsFixed', True),
            lambda: setattr(self.f.components[1], 'GetSuppression2', 0),
            lambda: self.f.components[1].Transform2.ArrayData.__setitem__(9, 0.03),
            lambda: setattr(self.f.components[1], 'ReferencedConfiguration', 'Other'),
            lambda: setattr(self.f.components[1], 'IsVirtual', True),
            lambda: setattr(self.f.source, 'GetSaveFlag', True),
            lambda: setattr(self.f.source, 'IsOpenedReadOnly', False),
        ]
        for change in changes:
            with self.subTest(change=change):
                self.f.build();self.app=self.f.app;self.doc=self.f.assembly
                self.doc.GetTitle=lambda:'assembly';self.f.source.GetTitle=lambda:'source'
                self.app.GetDocuments=lambda:(self.doc,self.f.source)
                self.documents=DocumentRegistry(self.app);self.entry=self.documents.register(self.doc);self.registry=self.entry.assembly_targets
                self.lease=self.documents.acquire_lease(self.entry,session_id='reader',ttl_seconds=60)['lease_id']
                old=self.listed();self.reset_native_counts();change()
                with self.assertRaises((AssemblyTargetStale,DocumentUpdateConflict,native.AssemblyTargetObservationError)):self.validate(old)
                self.assert_owner_count(0);self.assertFalse(self.registry.snapshots)

    def test_native_source_identity_change_with_same_path_and_state_rejected(self):
        old=self.listed();self.reset_native_counts()
        changed=NS(**vars(self.f.source))
        self.f.components[1].GetModelDoc2=lambda:changed
        with self.assertRaises(AssemblyTargetStale):self.validate(old)
        self.assert_owner_count(0)

    def test_same_geometry_reference_hash_but_different_native_face_rejected(self):
        old=self.listed();self.reset_native_counts()
        # Same full geometry/reference values and current body/source context
        # cannot replace the old retained exact resolved native face identity.
        snapshot=self.registry.snapshots['reader']
        from dataclasses import replace
        old_bindings=tuple(replace(b, resolved=NS(native_token=('old',i))) for i,b in enumerate(snapshot.bindings))
        self.registry.snapshots['reader']=replace(snapshot,bindings=old_bindings)
        with self.assertRaises(AssemblyTargetStale):self.validate(old)
        self.assert_owner_count(1)
        self.assertFalse(self.registry.snapshots)

    def test_full_geometry_change_at_unselected_face_denies_compare(self):
        old=self.listed();self.reset_native_counts()
        self.f.source_faces[1].GetArea=lambda:.008
        self.f.mapped[1].GetArea=self.f.resolved[1].GetArea=self.f.source_faces[1].GetArea
        self.f.mapped[3].GetArea=self.f.resolved[3].GetArea=self.f.source_faces[1].GetArea
        with self.assertRaises(AssemblyTargetStale):self.validate(old)
        self.assert_owner_count(1)
        self.assertFalse(self.registry.snapshots)

    def test_owner_failure_keeps_original_and_issues_zero_partial_tokens(self):
        first=RuntimeError('original owner error')
        self.f.owners[2].side_effect=first
        with self.assertRaises(RuntimeError) as caught:self.call()
        self.assertIs(caught.exception,first)
        self.assertEqual([g.call_count for g in self.f.owners],[1,1,1,0])
        self.assertFalse(self.registry.issued_ids or self.registry.snapshots)

    def test_invalid_result_or_late_guard_never_publishes_staged_tokens(self):
        for stage in ('result','late'):
            with self.subTest(stage=stage):
                original=gate.current_context
                late_count=0
                def late(*a,**kw):
                    nonlocal late_count
                    late_count+=1
                    if late_count==2:raise RuntimeError('late context drift')
                    return original(*a,**kw)
                patch=(mock.patch('swcli.result_schemas.validate_operation_result',side_effect=OperationResultInvalid('bad result'))
                       if stage=='result' else mock.patch.object(gate,'current_context',side_effect=late))
                with patch,self.assertRaises(Exception):self.call()
                self.assertFalse(self.registry.snapshots or self.registry.issued_ids)

    def test_close_and_new_worker_or_document_cannot_resolve_old_scope(self):
        old=self.listed()
        old_registry=self.registry
        self.documents.forget(self.entry.document_id)
        self.assertTrue(old_registry.closed)
        self.entry=self.documents.register(self.doc);self.registry=self.entry.assembly_targets
        self.lease=self.documents.acquire_lease(self.entry,session_id='reader',ttl_seconds=60)['lease_id']
        with self.assertRaises(AssemblyTargetNotFound):self.validate(old)
        self.documents=DocumentRegistry(self.app);self.entry=self.documents.register(self.doc);self.registry=self.entry.assembly_targets
        self.lease=self.documents.acquire_lease(self.entry,session_id='reader',ttl_seconds=60)['lease_id']
        with self.assertRaises(AssemblyTargetNotFound):self.validate(old)

    def test_wrong_sta_thread_denies_before_native_calls(self):
        before=self.app.IsSame.call_count;errors=[]
        def other():
            try:self.registry.capacity('reader')
            except Exception as e:errors.append(e)
        thread=threading.Thread(target=other);thread.start();thread.join()
        self.assertIsInstance(errors[0],AssemblyTargetConflict)
        self.assertEqual(before,self.app.IsSame.call_count)

    def test_no_registry_growth_on_collision_or_capacity(self):
        with mock.patch('swcli.daemon.assembly_targets.secrets.token_hex',return_value='a'*32):
            with self.assertRaises(AssemblyTargetConflict):self.call()
        self.assertFalse(self.registry.snapshots or self.registry.issued_ids)
        self.registry.MAX_ISSUED=0;self.reset_native_counts()
        with self.assertRaises(AssemblyTargetConflict):self.call()
        self.assert_owner_count(0)

    def test_protocol_exact_ids_duplicates_and_context_rejected_before_com(self):
        good=dict(document_id=self.entry.document_id,expected_update_stamp=7)
        invalid=[('assembly.targets.list',{'components':['same','same']},good),
                 ('assembly.targets.list',{'components':self.f.names},{**good,'document_id':'active'}),
                 ('assembly.targets.list',{'components':self.f.names},{**good,'expected_update_stamp':None}),
                 ('assembly.targets.validate',{'snapshot_id':'as-'+'a'*32,'target_ids':['at-'+'b'*32]*2},{**good,'lease_id':self.lease})]
        for name,values,context in invalid:
            with self.subTest(name=name,values=values),self.assertRaises(ValueError):validate_operation_request(name,values,**context)
        self.assert_owner_count(0)

    def test_cli_sdk_and_metadata_are_typed_readonly_with_no_activation(self):
        parser=build_parser()
        args=parser.parse_args(['assembly','targets','list',*self.f.names,'--document',self.entry.document_id,'--if-update-stamp','7','--json'])
        request=_typed_operation(args)
        self.assertEqual(request[0],'assembly.targets.list');self.assertEqual(request[1],{'components':self.f.names})
        client=Client(session_id='reader')
        with mock.patch.object(client,'_execute',return_value={}) as dispatch:
            client.assembly.targets.list(components=self.f.names,document_id=self.entry.document_id,expected_update_stamp=7)
        self.assertEqual(dispatch.call_args.args[0],'assembly.targets.list')
        for name in gate.OPERATIONS:
            spec=OPERATION_CATALOG[name]
            self.assertFalse(spec.temporary_activation)
            self.assertTrue(spec.lease_guarded)
            self.assertIn('READONLY',spec.parameters['description'])

    def test_result_contract_rejects_partial_or_misleading_success(self):
        result=self.listed()
        for alter in [lambda r:r['targets'].pop(),lambda r:r['read_gate'].update(write_authorized=True),
                      lambda r:r['census']['components'][0]['faces'].pop(),lambda r:r['document'].update(active=False),
                      lambda r:r['census']['components'][0]['transform'].__setitem__(0,float('nan'))]:
            broken=deepcopy(result);alter(broken)
            with self.assertRaises(OperationResultInvalid):validate_operation_result('assembly.targets.list',broken)
        broken={'ok':False,'action':'assembly.targets.list','error':{'type':'fail','message':'no'},'targets':result['targets']}
        with self.assertRaises(OperationResultInvalid):validate_operation_result('assembly.targets.list',broken)

    def test_other_session_list_cannot_revive_observed_old_stamp(self):
        old=self.listed()
        self.documents.release_lease(self.lease,session_id='reader')
        self.doc.GetUpdateStamp=lambda:8
        new=self.call(session='other',lease_id=None,expected_update_stamp=8)
        self.assertIn('other',self.registry.snapshots)
        self.assertNotIn('reader',self.registry.snapshots)
        self.doc.GetUpdateStamp=lambda:7
        self.lease=self.documents.acquire_lease(self.entry,session_id='reader',ttl_seconds=60)['lease_id']
        self.reset_native_counts()
        with self.assertRaises(AssemblyTargetStale):self.validate(old)
        self.assert_owner_count(0)
        self.assertNotEqual(old['snapshot_id'],new['snapshot_id'])

    def test_unknown_scope_change_from_other_session_invalidates_all(self):
        old=self.listed()
        self.documents.release_lease(self.lease,session_id='reader')
        self.f.source.GetSaveFlag=True
        with self.assertRaises(native.AssemblyTargetObservationError):self.call(session='other',lease_id=None)
        self.assertFalse(self.registry.snapshots)
        self.f.source.GetSaveFlag=False
        self.lease=self.documents.acquire_lease(self.entry,session_id='reader',ttl_seconds=60)['lease_id']
        with self.assertRaises(AssemblyTargetStale):self.validate(old)

    def test_lease_expiry_during_full_census_never_publishes_or_validates(self):
        clock=[0.0]
        self.documents._clock=lambda:clock[0]
        self.documents.release_lease(self.lease,session_id='reader')
        self.lease=self.documents.acquire_lease(self.entry,session_id='reader',ttl_seconds=1)['lease_id']
        original=native.observe_readonly_active_targets
        def expire(**kwargs):
            result=original(**kwargs)
            clock[0]=2.0
            return result
        with mock.patch.object(native,'observe_readonly_active_targets',side_effect=expire):
            with self.assertRaises(Exception) as caught:self.call()
        self.assertEqual(type(caught.exception).__name__,'DocumentLeaseNotFound')
        self.assertFalse(self.registry.snapshots or self.registry.issued_ids)

    def test_writable_asm_or_source_rejected_without_relaxing_private_policy(self):
        for target in (self.doc,self.f.source):
            target.IsOpenedReadOnly=False
            with self.assertRaises(native.AssemblyTargetObservationError):self.call()
            self.assertFalse(self.registry.snapshots or self.registry.issued_ids)
            self.assert_owner_count(0)
            target.IsOpenedReadOnly=True

    def test_stage_requires_exact_binding_count_and_raw_reference_digest(self):
        from dataclasses import replace
        census=self.f.read()
        sources=(self.f.source,self.f.source)
        for changed in [replace(census,bindings=census.bindings[:-1]),
                        replace(census,bindings=(replace(census.bindings[0],reference=b'changed'),*census.bindings[1:]))]:
            with self.assertRaises(AssemblyTargetConflict):self.registry.stage('reader',changed,sources)
            self.assertFalse(self.registry.snapshots or self.registry.issued_ids)

    def test_registry_ambiguous_bijection_and_unknown_identity_never_fallback(self):
        result=self.listed();snapshot=self.registry.snapshots['reader'];census=self.f.read()
        sources=(self.f.source,self.f.source)
        original=self.registry.same
        def ambiguous(a,b):
            if a is snapshot.bindings[0].resolved:return True
            return original(a,b)
        with mock.patch.object(self.registry,'same',side_effect=ambiguous):
            with self.assertRaises(AssemblyTargetStale):self.registry.compare(snapshot,census,sources)
        self.app.IsSame.side_effect=None;self.app.IsSame.return_value=True
        with self.assertRaises(AssemblyTargetConflict):self.registry.same(object(),object())

    def test_direct_request_bool_stamp_or_bad_lease_never_reads_native_identity(self):
        before=self.app.IsSame.call_count
        for context in [dict(expected_update_stamp=True),dict(expected_update_stamp=-1),dict(lease_id='writer')]:
            with self.assertRaises(ValueError):self.call(**context)
        self.assertEqual(before,self.app.IsSame.call_count)

    def test_worker_rejects_background_and_unknown_handles_before_command_setter(self):
        from test_native_sequence import NativeSequenceTests
        from swcli.daemon import server
        self.app.GetProcessID=lambda:1234
        self.app.CommandInProgress=False
        request=dict(request_id='background',operation='assembly.targets.list',parameters={'components':self.f.names},
                     session_id='reader',document_id=self.entry.document_id,expected_update_stamp=7,lease_id=self.lease)
        self.app.ActiveDoc=self.f.source
        actual_prepare=gate.prepare_request
        def prepare(*args,**kwargs):
            self.assertFalse(self.app.CommandInProgress)
            kwargs['documents']=self.documents
            return actual_prepare(*args,**kwargs)
        execute=mock.Mock()
        with mock.patch.object(gate,'prepare_request',side_effect=prepare), \
             mock.patch.object(server,'native_api_sequence') as sequence:
            responses,_,_=NativeSequenceTests().run_worker(self.app,True,execute,[request,None])
        sequence.assert_not_called();execute.assert_not_called()
        response=responses.put.call_args.args[0]
        self.assertEqual(response['error']['code'],'AssemblyNotActive')
        self.assert_owner_count(0)

    def test_worker_preflight_runs_before_owned_command_and_again_in_handler(self):
        from test_native_sequence import NativeSequenceTests
        from swcli.daemon import server
        self.app.GetProcessID=lambda:1234
        self.app.CommandInProgress=False
        request=dict(request_id='active',operation='assembly.targets.list',parameters={'components':self.f.names},
                     session_id='reader',document_id=self.entry.document_id,expected_update_stamp=7,lease_id=self.lease)
        actual_prepare=gate.prepare_request;states=[]
        def prepare(*args,**kwargs):
            states.append(self.app.CommandInProgress)
            kwargs['documents']=self.documents
            return actual_prepare(*args,**kwargs)
        def execute(app,op,values,**context):
            self.assertTrue(self.app.CommandInProgress)
            context['documents']=self.documents
            with mock.patch.dict('sys.modules',self.f.modules):
                return execute_operation(app,op,values,**context)
        with mock.patch.object(gate,'prepare_request',side_effect=prepare):
            responses,_,_=NativeSequenceTests().run_worker(self.app,True,execute,[request,None])
        response=responses.put.call_args.args[0]
        self.assertTrue(response['success'],response)
        self.assertEqual(states,[False,True])
        self.assertFalse(self.app.CommandInProgress)
        self.assert_owner_count(1)

    def test_sdk_full_result_validation_and_request_never_refresh_or_retry(self):
        result=self.listed();client=Client(session_id='reader')
        reply=dict(api_version='swcli/v1',request_id='sdk-list',success=True,duration_ms=1,result=result)
        with mock.patch('swcli.sdk.client.call_daemon',return_value=reply) as wire:
            response=client.assembly.targets.list(components=self.f.names,document_id=self.entry.document_id,
                expected_update_stamp=7,lease_id=self.lease,request_id='sdk-list')
        self.assertTrue(response.success)
        wire.assert_called_once()
        with mock.patch('swcli.sdk.client.call_daemon') as wire:
            with self.assertRaises(ValueError):client.assembly.targets.validate(snapshot_id=result['snapshot_id'],
                target_ids=['e-abc123'],document_id=self.entry.document_id,expected_update_stamp=7,lease_id=self.lease)
        wire.assert_not_called()


    def test_worker_unknown_typed_snapshot_stops_before_command_setter(self):
        from test_native_sequence import NativeSequenceTests
        from swcli.daemon import server
        self.app.GetProcessID=lambda:1234
        self.app.CommandInProgress=False
        request=dict(request_id='unknown',operation='assembly.targets.validate',
            parameters={'snapshot_id':'as-'+'0'*32,'target_ids':['at-'+'1'*32]},
            session_id='reader',document_id=self.entry.document_id,expected_update_stamp=7,lease_id=self.lease)
        actual_prepare=gate.prepare_request
        def prepare(*args,**kwargs):
            kwargs['documents']=self.documents
            return actual_prepare(*args,**kwargs)
        execute=mock.Mock()
        with mock.patch.object(gate,'prepare_request',side_effect=prepare), \
             mock.patch.object(server,'native_api_sequence') as sequence:
            responses,_,_=NativeSequenceTests().run_worker(self.app,True,execute,[request,None])
        sequence.assert_not_called();execute.assert_not_called()
        self.assertEqual(responses.put.call_args.args[0]['error']['code'],'AssemblyTargetNotFound')
        self.assert_owner_count(0)


    def test_source_close_reopen_between_census_and_publication_cannot_bind_old_faces(self):
        original=native.observe_readonly_active_targets
        def reopen(**kwargs):
            census=original(**kwargs)
            replacement=NS(**vars(self.f.source))
            for component in self.f.components:component.GetModelDoc2=lambda:replacement
            return census
        with mock.patch.object(native,'observe_readonly_active_targets',side_effect=reopen):
            with self.assertRaises(AssemblyTargetStale):self.call()
        self.assert_owner_count(1)
        self.assertFalse(self.registry.issued_ids or self.registry.snapshots)


    def test_unknown_initial_identity_retires_all_sessions_before_owner_and_never_revives(self):
        first=self.listed()
        self.documents.release_lease(self.lease,session_id='reader')
        other=self.call(session='other',lease_id=None)
        self.lease=self.documents.acquire_lease(self.entry,session_id='reader',ttl_seconds=60)['lease_id']
        self.assertEqual(set(self.registry.snapshots),{'reader','other'})
        self.reset_native_counts()
        failure=AssemblyTargetConflict('native assembly target identity is unknown')
        with mock.patch.object(self.registry,'same',side_effect=failure):
            with self.assertRaises(AssemblyTargetConflict) as caught:self.validate(first)
        self.assertIs(caught.exception,failure)
        self.assertFalse(self.registry.snapshots)
        self.assert_owner_count(0)
        with self.assertRaises(AssemblyTargetStale):self.validate(first)
        self.documents.release_lease(self.lease,session_id='reader')
        other_lease=self.documents.acquire_lease(self.entry,session_id='other',ttl_seconds=60)['lease_id']
        with self.assertRaises(AssemblyTargetStale):self.validate(other,session='other',lease_id=other_lease)
        self.assert_owner_count(0)

    def test_unknown_initial_identity_list_also_retires_old_snapshot(self):
        first=self.listed();self.reset_native_counts()
        original_same=self.app.IsSame.side_effect
        def unknown(first,second):
            if first is self.doc and second is self.registry.document:return True
            return original_same(first,second)
        with mock.patch.object(self.app.IsSame,'side_effect',unknown):
            with self.assertRaises(AssemblyTargetConflict):self.call()
        self.assertFalse(self.registry.snapshots)
        self.assert_owner_count(0)
        with self.assertRaises(AssemblyTargetStale):self.validate(first)

    def test_wrong_lease_kind_or_session_does_not_observe_initial_native_identity(self):
        first=self.listed();self.reset_native_counts()
        with mock.patch.object(self.registry,'same',side_effect=AssertionError('ordinary refusal must precede identity')) as same:
            bad=self.parameters(first);bad['target_ids']=['at-'+'0'*32]
            with self.assertRaises(AssemblyTargetNotFound):self.call('assembly.targets.validate',bad)
            with self.assertRaises(DocumentLeaseConflict):self.validate(first,session='other')
            with self.assertRaises(ValueError):self.validate(first,lease_id=None)
        same.assert_not_called()
        self.assertIn('reader',self.registry.snapshots)
        self.validate(first)


    def test_prepare_closed_registry_cleanup_is_idempotent_and_preserves_original(self):
        for name in ('list','validate'):
            with self.subTest(operation=name):
                first=self.listed();self.reset_native_counts()
                original=RuntimeError('original initial identity failure')
                def close_then_fail(*args):
                    self.registry.close()
                    raise original
                with mock.patch.object(self.registry,'same',side_effect=close_then_fail):
                    with self.assertRaises(RuntimeError) as caught:
                        self.call() if name=='list' else self.validate(first)
                self.assertIs(caught.exception,original)
                self.assertTrue(self.registry.closed)
                self.registry.invalidate_all();self.registry.invalidate_after_failure()
                self.assertFalse(self.registry.snapshots)
                self.assert_owner_count(0)
                # A new document registry is an explicitly new worker scope.
                self.documents=DocumentRegistry(self.app);self.entry=self.documents.register(self.doc)
                self.registry=self.entry.assembly_targets
                self.lease=self.documents.acquire_lease(self.entry,session_id='reader',ttl_seconds=60)['lease_id']

    def test_run_closed_registry_cleanup_keeps_with_document_first_error_for_both_entries(self):
        for name in ('list','validate'):
            with self.subTest(operation=name):
                first=self.listed();self.reset_native_counts()
                issued=set(self.registry.issued_ids)
                original=RuntimeError('original document descriptor failure')
                def close_then_fail(*args,**kwargs):
                    self.registry.close()
                    raise original
                with mock.patch('swcli.daemon.operations._with_document',side_effect=close_then_fail):
                    with self.assertRaises(RuntimeError) as caught:
                        self.call() if name=='list' else self.validate(first)
                self.assertIs(caught.exception,original)
                self.assertTrue(self.registry.closed)
                self.assertFalse(self.registry.snapshots)
                self.assertEqual(self.registry.issued_ids,issued)
                self.assert_owner_count(1)
                with self.assertRaises(AssemblyTargetNotFound):self.validate(first)
                self.documents=DocumentRegistry(self.app);self.entry=self.documents.register(self.doc)
                self.registry=self.entry.assembly_targets
                self.lease=self.documents.acquire_lease(self.entry,session_id='reader',ttl_seconds=60)['lease_id']

    def test_secondary_retirement_failure_closes_grants_and_never_overwrites_first_error(self):
        first=self.listed();self.reset_native_counts()
        original=RuntimeError('original observation failure')
        secondary=OSError('secondary retirement failure')
        with mock.patch.object(self.registry,'same',side_effect=original), \
             mock.patch.object(self.registry,'invalidate_all',side_effect=secondary):
            with self.assertRaises(RuntimeError) as caught:self.validate(first)
        self.assertIs(caught.exception,original)
        self.assertTrue(self.registry.closed)
        self.assertFalse(self.registry.snapshots)
        self.assertEqual(self.registry.retirement_error,'OSError')
        self.assert_owner_count(0)
