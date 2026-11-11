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
        # Real native drawing source retained stored mass-property inches even
        # after the explicit IPS -> MMGS -> Custom preparation.
        if kind==3:state['values']['mass_properties.length_unit']=catalog.observe('mass_properties.length_unit',3)
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
        self.assertEqual([p['document_type'] for p in self.gate.record['cold_start_coverage']['probes']],[1,2,3])
        self.assertTrue(all(p['equal'] for p in self.gate.record['cold_start_coverage']['probes']))
        self.assertEqual(self.gate.record['cli_process_strategy'],'isolated-reused-cli-main')
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

    def test_readable_drawing_inches_noop_moves_after_measured_changed_target(self):
        with self.assertRaises(ValueError):catalog.target('mass_properties.length_unit','inch')
        self.execute()
        cases=[c for c in self.gate.record['unit_cases'] if c['document_type']==3 and c['write']['field']=='mass_properties.length_unit']
        deferred=[c for c in cases if c['noop_phase']=='after-write']
        self.assertEqual(len(deferred),3)  # one identical source for CLI/SDK/MCP
        for case in deferred:
            self.assertEqual(case['read_only_source_value'],'inch')
            self.assertTrue(case['success']);self.assertFalse(case['noop']['changed'])
            self.assertEqual(case['noop']['document'],case['after_write']['document'])
            self.assertTrue(case['noop']['document']['modified'])
            self.assertEqual(case['noop']['unit_profile'],case['write']['unit_profile'])
        self.assertFalse(any(c.document_command=='unit-profile-set' and c.field=='mass_properties.length_unit' and c.value=='inch' for c in self.fake.calls if getattr(c,'document_command',None)=='unit-profile-set'))
        self.assertEqual(self.fake.changed_attempts,417)
        with self.assertRaises(ValueError):catalog.target('mass_properties.length_unit','inch')

    def test_original_native_drawing_inches_noop_rejects_before_worker_or_setter(self):
        from swcli import cli
        from swcli.daemon import server
        snapshot=json.loads((ROOT/'docs/evidence/units-profile/public-writes-42423042929/first-failure-source-profile.json').read_text())
        self.assertEqual(snapshot['document_type'],3)
        self.assertEqual(snapshot['values']['mass_properties.length_unit'],dict(value='inch',native_value=3))
        self.assertFalse(public.source_noop_is_candidate(snapshot,'mass_properties.length_unit'))
        self.assertEqual(catalog.target('mass_properties.length_unit','mm'),0)
        output=io.StringIO();requests=[]
        def protocol_boundary(operation,parameters,**options):
            request=dict(api_version=PROTOCOL_VERSION,request_id='original-inch-noop',operation=operation,parameters=parameters,
                         document_id=options['document_id'],expected_update_stamp=options['expected_update_stamp'],lease_id=options['lease_id'])
            requests.append(request)
            handler=object.__new__(server.SwclidRequestHandler)
            handler.rfile=io.BytesIO(json.dumps(request).encode()+b'\n');handler.wfile=io.BytesIO()
            handler.server=mock.Mock(manager=mock.Mock());handler.server.security=server.ServerSecurity();handler.server.workspace=None
            handler.connection=mock.Mock();handler.handle()
            handler.server.manager.assert_not_called()
            self.assertEqual(handler.server.manager.mock_calls,[])
            return json.loads(handler.wfile.getvalue())
        args=['document','unit-profile-set','mass_properties.length_unit','inch','--if-snapshot',json.dumps(snapshot),'--if-update-stamp','103','--document','d-012345','--lease','l-0123456789ab','--json']
        with mock.patch.object(cli,'call_daemon',side_effect=protocol_boundary) as daemon, mock.patch('sys.stdout',new=output):
            self.assertNotEqual(cli.main(args),0)
        daemon.assert_called_once();self.assertEqual(len(requests),1)
        result=json.loads(output.getvalue());self.assertFalse(result['ok'])
        self.assertEqual(result['error']['type'],'ValueError')
        self.assertEqual(result['error']['message'],'unsupported candidate unit target')

    def test_independent_cold_probe_snapshot_drift_stops_before_changed_setter(self):
        import subprocess
        def run(command,**options):
            result=self.fake.run(command,**options)
            if self.gate.cold_probe:
                payload=json.loads(result.stdout);payload['unit_profile']['linkage']['swUnitsTimeUnits']+=1
                return subprocess.CompletedProcess(command,result.returncode,json.dumps(payload).encode(),result.stderr)
            return result
        with mock.patch.object(catalog,'CALIBRATED_UNIT_WRITES',self.domains),mock.patch.object(catalog,'CALIBRATED_UNIT_SYSTEM_RESULTS',self.results),mock.patch.object(self.gate,'run_command',side_effect=run),mock.patch.object(self.gate,'checkpoint'),mock.patch('sys.stdout',new=io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'fresh CLI probe differs'):
                try:public.run(self.gate,self.fixtures,[])
                finally:self.gate.cleanup()
        self.assertEqual(self.fake.changed_attempts,0)
