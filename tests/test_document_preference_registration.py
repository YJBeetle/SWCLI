"""Public request/result registrations, isolated from CLI and daemon handlers."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from swcli.document_preferences_schemas import document_preference_parameters
from swcli.operation_schemas import OPERATION_CATALOG, operation_schemas, validate_operation_request
from swcli.result_schemas import OperationResultInvalid, validate_operation_result
from swcli.protocol import load_schema

OPS=('document.annotation-font','document.annotation-font-set','document.display-options',
     'document.display-option-set','document.drafting-standard','document.drafting-standard-set')


class DocumentPreferenceRegistrationTests(unittest.TestCase):
    def setUp(self):
        path=Path(__file__).with_name('test_document_preferences_schemas.py')
        spec=importlib.util.spec_from_file_location('_preference_registration_fixture',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.data=module.DocumentPreferenceSchemaTests();self.data.setUp()
        self.document={'title':'Background.SLDPRT','path':'','type':1,'modified':False,
            'update_stamp':19,'document_id':'d-ab12cd','current':False,'active':False}

    def wire(self, operation, payload, *, modified=False):
        return {'ok':True,'action':operation,'session_id':'writer',
                'document':{**self.document,'modified':modified},**deepcopy(payload)}

    def requests(self):
        return {
            'document.annotation-font':{},
            'document.annotation-font-set':{'field':'bold','value':True,'expected_font':self.data.font},
            'document.display-options':{},
            'document.display-option-set':{'field':'grid.display','value':True,'expected_value':False},
            'document.drafting-standard':{},
            'document.drafting-standard-set':{'value':'iso','expected_snapshot':self.data.snapshot},
        }

    def changed_result(self, operation):
        if operation=='document.annotation-font-set':
            payload=self.data.font_result(normalized=True)
            payload.update(observed_font=deepcopy(payload['font']),observed_native_font=deepcopy(payload['native_font']))
        elif operation=='document.display-option-set':
            before=deepcopy(self.data.options);after=deepcopy(before)
            after['grid.display']={'value':True,'native_value':True}
            payload={'field':'grid.display','before':before,'options':after,'observed_options':deepcopy(after),
                     'changed':True,'mutation':{'attempted':True,'may_have_changed':True}}
        else:
            payload=self.data.fixture.edit()
            self.assertTrue(payload['ok'],payload)
        return self.wire(operation,payload,modified=True)

    def reject_result(self, operation, result):
        with self.assertRaises(OperationResultInvalid):validate_operation_result(operation,result)

    def test_all_six_operations_have_discoverable_strict_json_schemas_and_context(self):
        catalog=operation_schemas()
        for name in OPS:
            with self.subTest(operation=name):
                spec=OPERATION_CATALOG[name]
                self.assertTrue(spec.selected_document)
                self.assertFalse(spec.temporary_activation)
                self.assertEqual(spec.handler,name.replace('.','_').replace('-','_'))
                self.assertEqual(spec.lease_guarded,name.endswith('-set'))
                context=spec.parameters['x-swcli-context']
                self.assertEqual(context['document_id'],'optional')
                self.assertEqual(context['expected_update_stamp'],'required' if name.endswith('-set') else 'optional')
                self.assertEqual(context['lease_id'],'required' if name.endswith('-set') else 'forbidden')
                self.assertFalse(spec.parameters['additionalProperties'])
                Draft202012Validator.check_schema(catalog[name])
                Draft202012Validator.check_schema(spec.result)
                self.assertTrue(Draft202012Validator(catalog[name]).is_valid(self.requests()[name]))

    def test_new_schemas_obey_existing_capabilities_and_cli_discovery_protocol(self):
        from swcli.cli import _capabilities_mismatch
        operation_contract=load_schema('capabilities')['properties']['operation_schemas']['additionalProperties']
        payload={'protocol_versions':['swcli/v1'],'server_version':'test','host':None,
            'operations':list(OPS),'export_formats':{'part':[],'assembly':[],'drawing':[]},
            'request_replay':{'supported':True,'max_entries':1,'max_bytes':1,'scope':'daemon'},
            'worker_alive':False,'host_connected':False,'recovery_required':False,'recovery_error':None,
            'operation_schemas':{name:deepcopy(OPERATION_CATALOG[name].parameters) for name in OPS},
            'operation_result_schemas':{name:deepcopy(OPERATION_CATALOG[name].result) for name in OPS}}
        for name in OPS:
            parameters=payload['operation_schemas'][name]
            self.assertNotIn('oneOf',parameters)
            Draft202012Validator(operation_contract).validate(parameters)
            if name in ('document.annotation-font-set','document.display-option-set'):
                self.assertIn('oneOf',parameters['allOf'][0])
        Draft202012Validator(load_schema('capabilities')).validate(payload)
        self.assertIsNone(_capabilities_mismatch(payload))
        invalid=deepcopy(payload)
        parameters=invalid['operation_schemas']['document.annotation-font-set']
        parameters['oneOf']=parameters.pop('allOf')[0]['oneOf']
        self.assertFalse(Draft202012Validator(operation_contract).is_valid(parameters))
        self.assertIsNotNone(_capabilities_mismatch(invalid))

    def test_backend_validates_all_six_requests_and_requires_write_stamp(self):
        for name,parameters in self.requests().items():
            context={'lease_id':'l-ab12cd34ef56'} if name.endswith('-set') else {}
            self.assertEqual(validate_operation_request(name,parameters,document_id='d-ab12cd',expected_update_stamp=19,**context),parameters)
            if name.endswith('-set'):
                with self.assertRaisesRegex(ValueError,'requires expected_update_stamp'):
                    validate_operation_request(name,parameters)
                validate_operation_request(name,parameters,expected_update_stamp=19,lease_id='l-ab12cd34ef56')
            else:
                with self.assertRaisesRegex(ValueError,'lease_id is not supported'):
                    validate_operation_request(name,parameters,lease_id='l-ab12cd34ef56')
            for stamp in (True,19.0,'19'):
                with self.assertRaises(ValueError):validate_operation_request(name,parameters,expected_update_stamp=stamp)

    def test_only_new_set_requests_require_a_lease_before_registry_or_host_access(self):
        from swcli.daemon.operations import execute_operation
        for name,parameters in self.requests().items():
            if not name.endswith('-set'):
                continue
            with self.subTest(operation=name):
                app,documents=mock.Mock(),mock.Mock()
                with self.assertRaisesRegex(ValueError,'requires lease_id'):
                    execute_operation(app,name,parameters,documents=documents,
                        document_id='d-ab12cd',session_id='writer',expected_update_stamp=19)
                documents.resolve.assert_not_called()
                self.assertEqual(app.mock_calls,[])
        legacy=OPERATION_CATALOG['document.annotation-option-set']
        self.assertEqual(legacy.parameters['x-swcli-context']['lease_id'],'optional')
        self.assertEqual(legacy.parameters['x-swcli-context']['expected_update_stamp'],'optional')
        self.assertTrue(legacy.lease_guarded)
        validate_operation_request('document.annotation-option-set',
            {'field':'zero.leading','value':'show','expected_value':'standard'})

    def test_mcp_missing_lease_is_rejected_by_protocol_before_host_without_starting(self):
        from swcli import PROTOCOL_VERSION
        from swcli.daemon import operations
        from swcli.mcp import DaemonBridge
        app,documents,manager=mock.Mock(),mock.Mock(),mock.Mock()
        def dispatch(operation,parameters,**context):
            try:
                operations.execute_operation(app,operation,parameters,documents=documents,
                    session_id=context['session_id'],document_id=context.get('document_id'),
                    expected_update_stamp=context.get('expected_update_stamp'),lease_id=context.get('lease_id'))
            except ValueError as error:
                return {'api_version':PROTOCOL_VERSION,'request_id':context['request_id'],
                    'success':False,'duration_ms':0,'error':{'code':'ValueError','message':str(error)}}
            raise AssertionError('missing lease reached host dispatch')
        host_functions={name:mock.Mock() for name in ('set_document_annotation_font_windows',
            'set_document_display_option_windows','set_document_drafting_standard_windows')}
        with mock.patch('swcli.mcp.DaemonManager',return_value=manager),\
             mock.patch('swcli.mcp.call_daemon',side_effect=dispatch) as transport,\
             mock.patch.multiple(operations,**host_functions):
            bridge=DaemonBridge(session_id='writer')
            for name,parameters in self.requests().items():
                if not name.endswith('-set'):
                    continue
                result=bridge.call('execute',{'operation':name,'parameters':parameters,
                    'document_id':'d-ab12cd','expected_update_stamp':19})
                self.assertFalse(result['success'],result)
                self.assertIn('requires lease_id',result['error']['message'])
            self.assertEqual(transport.call_count,3)
        self.assertEqual(app.mock_calls,[])
        documents.resolve.assert_not_called()
        manager.start.assert_not_called()
        for function in host_functions.values():function.assert_not_called()

    def test_context_and_cas_cannot_be_smuggled_into_parameters(self):
        for name,parameters in self.requests().items():
            for field,value in (('document_id','d-ab12cd'),('lease_id','l-ab12cd34ef56'),('expected_update_stamp',19)):
                changed={**parameters,field:value}
                with self.subTest(operation=name,field=field),self.assertRaises(ValueError):
                    validate_operation_request(name,changed,expected_update_stamp=19)
                self.assertFalse(Draft202012Validator(OPERATION_CATALOG[name].parameters).is_valid(changed))
        for name,key in (('document.annotation-font-set','expected_font'),
                         ('document.display-option-set','expected_value'),
                         ('document.drafting-standard-set','expected_snapshot')):
            parameters=deepcopy(self.requests()[name]);parameters.pop(key)
            with self.assertRaises(ValueError):validate_operation_request(name,parameters,expected_update_stamp=19)

    def test_registered_nested_request_validation_rejects_float_int_nan_extra_and_coverage_faults(self):
        cases=[]
        font=deepcopy(self.requests()['document.annotation-font-set']);font['expected_font']['height_points']=12.0
        cases.append(('document.annotation-font-set',font))
        font=deepcopy(self.requests()['document.annotation-font-set']);font['expected_font']['extra']=True
        cases.append(('document.annotation-font-set',font))
        cases.append(('document.display-option-set',{'field':'plane.transparency','value':25.0,'expected_value':95}))
        cases.append(('document.display-option-set',{'field':'grid.major_spacing_mm','value':float('nan'),'expected_value':100}))
        standard=deepcopy(self.requests()['document.drafting-standard-set'])
        standard['expected_snapshot']['observed_defaults']['coverage']['display'].pop()
        cases.append(('document.drafting-standard-set',standard))
        standard=deepcopy(self.requests()['document.drafting-standard-set'])
        standard['expected_snapshot']['observed_defaults']['annotation_font']['font']['height_mm']=7
        cases.append(('document.drafting-standard-set',standard))
        for name,parameters in cases:
            with self.subTest(operation=name),self.assertRaises(ValueError):
                validate_operation_request(name,parameters,expected_update_stamp=19)

    def test_read_results_validate_real_fixed_profile_and_font_display_native_pairs(self):
        font=self.data.snapshot['observed_defaults']['annotation_font']
        results={'document.annotation-font':self.wire('document.annotation-font',font),
                 'document.display-options':self.wire('document.display-options',{'options':self.data.options}),
                 'document.drafting-standard':self.wire('document.drafting-standard',self.data.snapshot)}
        for name,result in results.items():
            validate_operation_result(name,result)
            bad=deepcopy(result);bad['extra']=True;self.reject_result(name,bad)
            bad=deepcopy(result);bad.pop('session_id');self.reject_result(name,bad)
            for stamp in (None,19.0,True):
                bad=deepcopy(result);bad['document']['update_stamp']=stamp;self.reject_result(name,bad)
        result=deepcopy(results['document.annotation-font']);result['font']['height_mm']=4
        self.reject_result('document.annotation-font',result)
        result=deepcopy(results['document.display-options']);result['options']['grid.major_spacing_mm']['value']=0.1
        self.reject_result('document.display-options',result)
        result=deepcopy(results['document.drafting-standard']);result['standard']['native_value']=7.0
        self.reject_result('document.drafting-standard',result)

    def test_changed_set_results_validate_all_three_lifecycles(self):
        for name in OPS[1::2]:
            result=self.changed_result(name)
            validate_operation_result(name,result)
            for defect in (lambda x:x['document'].update(modified=False),
                           lambda x:x['mutation'].update(attempted=False),
                           lambda x:x.update(changed=False)):
                bad=deepcopy(result);defect(bad);self.reject_result(name,bad)

    def test_standard_changed_result_requires_after_final_and_correct_coupling_flag(self):
        name='document.drafting-standard-set';result=self.changed_result(name)
        for key in ('after','final','observed_defaults_changed'):
            bad=deepcopy(result);bad.pop(key)
            self.assertFalse(Draft202012Validator(OPERATION_CATALOG[name].result).is_valid(bad))
            self.reject_result(name,bad)
        bad=deepcopy(result);bad['observed_defaults_changed']=not bad['observed_defaults_changed'];self.reject_result(name,bad)
        bad=deepcopy(result);bad['final']['observed_defaults']['annotation_font']['font']['bold']=False
        self.reject_result(name,bad)
        bad=deepcopy(result);bad['before']['observed_defaults']['document_type']=2
        bad['before']['observed_defaults']['coverage']=deepcopy(result['before']['observed_defaults']['coverage'])
        self.reject_result(name,bad)

    def test_font_normalization_and_display_unrequested_changes_remain_strict(self):
        name='document.annotation-font-set';result=self.changed_result(name)
        self.assertEqual(len(result['native_normalizations']),1)
        bad=deepcopy(result);bad['native_normalizations']=[];self.reject_result(name,bad)
        bad=deepcopy(result);bad['observed_native_font']['CharHeightInPts']=12;self.reject_result(name,bad)
        name='document.display-option-set';result=self.changed_result(name)
        bad=deepcopy(result);bad['options']['plane.transparency']={'value':25,'native_value':25}
        bad['observed_options']=deepcopy(bad['options']);self.reject_result(name,bad)
        bad=deepcopy(result);bad['field']='plane.transparency';self.reject_result(name,bad)

    def test_noop_results_preserve_all_observed_values_and_zero_mutation(self):
        false={'attempted':False,'may_have_changed':False}
        results={
            'document.annotation-font-set':{'field':'bold','before':self.data.font,'native_before':self.data.native,
                'font':self.data.font,'native_font':self.data.native,'native_normalizations':[], 'changed':False,'mutation':false},
            'document.display-option-set':{'field':'grid.display','before':self.data.options,'options':self.data.options,
                'changed':False,'mutation':false},
            'document.drafting-standard-set':{'before':self.data.snapshot,**self.data.snapshot,'changed':False,'mutation':false},
        }
        for name,payload in results.items():
            result=self.wire(name,payload);validate_operation_result(name,result)
            bad=deepcopy(result);bad['mutation']['may_have_changed']=True;self.reject_result(name,bad)
        name='document.annotation-font-set';bad=self.wire(name,results[name])
        bad['native_font']['CharHeightInPts']=14;bad['font']['height_points']=14
        bad['native_normalizations']=[{'member':'CharHeightInPts','before':12,'after':14,'reason':'inactive-height-representation'}]
        self.reject_result(name,bad)

    def test_failed_set_result_preserves_partial_mutation_without_claiming_rollback(self):
        for name in OPS[1::2]:
            result={'ok':False,'action':name,'error':{'type':'RuntimeError','message':'native failed'},
                    'mutation':{'attempted':True,'may_have_changed':True}}
            validate_operation_result(name,result)
            bad=deepcopy(result);bad.pop('mutation');self.reject_result(name,bad)
            bad=deepcopy(result);bad['mutation']['attempted']=1;self.reject_result(name,bad)


if __name__=='__main__':unittest.main()
