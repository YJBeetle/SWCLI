"""Actual CLI/parser/schema gate flow; synthetic domains here never authorize native writes."""
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from swcli import document_unit_profile as catalog
from swcli.cli import _typed_operation
from swcli.daemon.server import validate_request, PROTOCOL_VERSION
from test_unit_profile_public_gate import ProfileCLI, profile
from test_unit_profile_write_calibration import write as planning

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('unit_write_public_test',ROOT/'scripts/ci/verify-document-unit-writes.py')
public=importlib.util.module_from_spec(spec);spec.loader.exec_module(public)


def fixture_report(directory):
    cases=[];transitions={}
    for kind,suffix in ((1,'SLDPRT'),(2,'SLDASM'),(3,'SLDDRW')):
        state=profile(kind);state['values']['system']=catalog.observe('system',3 if kind==3 else 5)
        case=dict(document_type=kind,success=True,write_diagnostic_success=True,initial_profile=deepcopy(state),write_steps=[])
        def add(field,value,role):
            nonlocal state
            before=deepcopy(state);native=catalog.target(field,value)
            state['values'][field]=catalog.observe(field,native)
            if field=='system':state['linkage']['swUnitsTimeUnits']=native
            if field=='linear.unit':state['native_units']['length_unit']=native
            if field=='linear.precision':state['native_units']['significant_digits']=native
            target_dir=directory/('kind-%d'%kind)/('step-%03d'%(len(case['write_steps'])+1));target_dir.mkdir(parents=True)
            source=target_dir/('source.'+suffix);target_file=target_dir/('target.'+suffix)
            source.write_bytes(json.dumps(before).encode());target_file.write_bytes(json.dumps(state).encode())
            step=dict(success=True,role=role,field=field,value=value,before=before,after=deepcopy(state),before_fingerprint=catalog.fingerprint(before),after_fingerprint=catalog.fingerprint(state),
                source_file=str(source.relative_to(directory)),target_file=str(target_file.relative_to(directory)),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),target_sha256=hashlib.sha256(target_file.read_bytes()).hexdigest(),readonly_profile=deepcopy(state),
                result=dict(ok=True,changed=True,mutation=dict(attempted=True,may_have_changed=True),native_return_value=True,before=before,unit_profile=deepcopy(state)))
            case['write_steps'].append(step);transitions[public.domain(before,field,value)]=deepcopy(state)
        for value in planning.custom_preparation(state['values']['system']['native_value']):add('system',value,'explicit-custom-preparation')
        for field in catalog.FIELDS:
            if field!='system':
                for value in planning.scalar_targets(field,state['values'][field]['native_value']):add(field,value,'scalar')
        for value in planning.system_targets(state['values']['system']['native_value']):add('system',value,'system-spoke')
        cases.append(case)
    report=dict(success=True,profile='units-write-calibration-v1',source_commit='synthetic-not-native',cases=cases)
    (directory/'report.json').write_text(json.dumps(report))
    return report,transitions


class WriteCLI(ProfileCLI):
    def __init__(self,directory,fixtures,transitions):
        super().__init__(directory,fixtures);self.transitions=transitions;self.changed_attempts=0
        for case in json.loads((fixtures/'report.json').read_text())['cases']:
            for step in case['write_steps']:
                path=str(fixtures/step['source_file'])
                self.saved[path]=dict(unit_profile=deepcopy(step['before']),type=case['document_type'],path=path,profiles={},count=1,volume=12000,area=3800,stamp=1,modified=False,lease=None)
    def dispatch(self,args):
        if args.command=='document' and args.document_command=='unit-profile-set':
            operation,parameters,_,document_id,stamp,lease=_typed_operation(args)
            validate_request(dict(api_version=PROTOCOL_VERSION,request_id='test-unit-writes',operation=operation,parameters=parameters,document_id=document_id,expected_update_stamp=stamp,lease_id=lease,session_id=args.session))
            d=self.documents[args.document_id];before=deepcopy(d['unit_profile']);mutation=dict(attempted=False,may_have_changed=False)
            if d['lease'] and d['lease']['session']!=args.session:return self.failure('DocumentLeaseConflict')
            if stamp!=d['stamp']:return self.failure('DocumentUpdateConflict')
            if d['read_only']:return self.failure('ValueError',mutation=mutation)
            if catalog.typed_key(parameters['expected_snapshot'])!=catalog.typed_key(before):return self.failure('DocumentUnitProfileConflict',mutation=mutation)
            key=public.domain(before,parameters['field'],parameters['value'])
            changed=before['values'][parameters['field']]['native_value']!=key[-1]
            if changed:
                if key not in catalog.CALIBRATED_UNIT_WRITES:return self.failure('UnitProfileCalibrationRequired',mutation=mutation)
                self.changed_attempts+=1
                if self.units_defect=='false':return self.failure('RuntimeError',native_return_value=False,mutation=dict(attempted=True,may_have_changed=True),before=before)
                d['unit_profile']=deepcopy(self.transitions[key]);d['modified']=True;d['stamp']+=1
                if self.units_defect=='wrong-linkage':d['unit_profile']['linkage']['swUnitsTimeUnits']+=1
            return dict(ok=True,action=operation,session_id=args.session,document=self.descriptor(d,args.session),field=parameters['field'],before=before,unit_profile=deepcopy(d['unit_profile']),changed=changed,mutation=dict(attempted=changed,may_have_changed=changed),**({'native_return_value':True} if changed else {}))
        return super().dispatch(args)


class WritePublicGateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.fixtures=self.root/'fixtures';self.fixtures.mkdir()
        self.report,self.transitions=fixture_report(self.fixtures)
        self.domains=tuple(self.transitions)
        self.results=tuple((key,catalog.fingerprint(after)) for key,after in self.transitions.items() if key[2]=='system')
        self.output=self.root/'output';self.output.mkdir()
        self.fake=WriteCLI(self.output,self.fixtures,self.transitions)
        self.gate=public.WriteGate(directory=self.output,host_directory=str(self.output),endpoint='127.0.0.1:18911',request_timeout_seconds=600)

    def execute(self,reviewed=True):
        with mock.patch.object(catalog,'CALIBRATED_UNIT_WRITES',self.domains if reviewed else ()),mock.patch.object(catalog,'CALIBRATED_UNIT_SYSTEM_RESULTS',self.results if reviewed else ()),mock.patch.object(self.gate,'run_command',side_effect=self.fake.run),mock.patch.object(self.gate,'checkpoint'),mock.patch('sys.stdout',new=io.StringIO()):
            try:public.run(self.gate,self.fixtures,[])
            finally:self.gate.cleanup()

    def test_full_three_type_candidate_gate_and_native_files_are_verified(self):
        self.execute()
        self.assertTrue(self.gate.record['success'])
        self.assertTrue(self.gate.record['changed_write_acceptance'])
        self.assertEqual(len(self.gate.record['unit_cases']),417)
        self.assertEqual(self.fake.changed_attempts,417)
        self.assertEqual(self.fake.documents,{})
        self.assertTrue(any(c.get('custom_closed_refusal') for c in self.gate.record['unit_cases']))

    def test_empty_or_partial_reviewed_domain_fails_before_any_cad_open(self):
        with self.assertRaisesRegex(RuntimeError,'manually reviewed'):self.execute(reviewed=False)
        self.assertEqual(self.fake.changed_attempts,0)
        self.assertFalse(any(c.command=='document' and c.document_command=='open' for c in self.fake.calls))
        self.assertIn('host',self.gate.record)
        self.assertFalse(self.gate.record['changed_write_acceptance'])

    def test_missing_candidate_or_system_direction_is_not_whole_scope_acceptance(self):
        for role in ('scalar','system-spoke'):
            broken=deepcopy(self.report['cases'][0])
            broken['write_steps'].remove(next(s for s in broken['write_steps'] if s['role']==role))
            with self.subTest(role=role),self.assertRaises(RuntimeError):public.require_complete_case(broken)

    def test_failed_public_write_stops_once_and_preserves_native_receipt(self):
        self.fake.units_defect='false'
        with self.assertRaisesRegex(RuntimeError,'failed'):self.execute()
        self.assertEqual(self.fake.changed_attempts,1)
        self.assertFalse(self.gate.record['changed_write_acceptance'])
        failed=next(e['result'] for e in self.gate.record['events'] if e.get('result',{}).get('native_return_value') is False)
        self.assertEqual(failed['mutation'],dict(attempted=True,may_have_changed=True))
        self.assertEqual(self.fake.documents,{})

    def test_linkage_drift_in_public_changed_result_is_not_accepted(self):
        self.fake.units_defect='wrong-linkage'
        with self.assertRaises(RuntimeError):self.execute()
        self.assertEqual(self.fake.changed_attempts,1)
        self.assertFalse(self.gate.record['changed_write_acceptance'])

    def test_wrong_native_fixture_bytes_or_escaping_path_stop_before_cad(self):
        for relative,digest in (('../outside.SLDPRT','a'*64),(self.report['cases'][0]['write_steps'][0]['source_file'],'a'*64)):
            with self.subTest(relative=relative),self.assertRaises(RuntimeError):public.file_in_fixture(self.fixtures,relative,digest)
