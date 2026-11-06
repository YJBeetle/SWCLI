"""Public gate harness contracts, independent of native internal permission."""
import copy
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace as NS

from swcli.cli import build_parser, _typed_operation

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_public_mates_test',ROOT/'scripts/ci/verify-assembly-mates.py')
public=importlib.util.module_from_spec(spec);spec.loader.exec_module(public)
IDENTITY=[1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.]


def state():
    return dict(title='Assembly1',path='',configuration='Default',update_stamp=3,modified=True,components=[
        dict(name='part-'+str(i+1),path='source.SLDPRT',configuration='Default',native_id=i+1,fixed=i==0,
             suppression=2,source_update_stamp=1,source_modified=False,transform=list(IDENTITY),faces=[
             dict(index=0,surface_kind='plane',parameters=[0,0,1,0,0,0],area_mm2=1,sense=False,reference_sha256=str(i*2)*64),
             dict(index=1,surface_kind='cylinder',parameters=[0,0,0,0,0,1,.003],area_mm2=1,sense=False,reference_sha256=str(i*2+1)*64)])
        for i in range(2)],mates=[])


class FakeGate:
    def __init__(self,directory):
        self.directory=directory;self.host_directory=str(directory);self.session='public-reader'
        self.record={'cases':[],'cleanup_errors':[]};self.owned={};self.leases={}
        self.documents={};self.saved={};self.counter=0;self.current=None
        self.commands=[];self.mutations=0;self.changed_on_reopen=False
        self.missing_reference=False;self.truncated=False;self.native_failure=False
        self.source_auto_unload=False

    def checkpoint(self,stage):pass
    def health(self):return {'host':{'process_id':123,'owned_by_daemon':True,'visible':False}}
    def require_empty(self):
        if self.documents:raise RuntimeError('documents remain')
    def descriptor(self,identifier):
        doc=self.documents[identifier]
        snapshot=doc.get('snapshot')
        return dict(document_id=identifier,title=snapshot['title'] if snapshot else 'Part',path=doc.get('path',''),
            type=doc['type'],modified=snapshot['modified'] if snapshot else False,
            update_stamp=snapshot['update_stamp'] if snapshot else 1,current=self.current==identifier,active=self.current==identifier)
    def create_doc(self,kind):
        self.counter+=1;identifier=f'd-{self.counter:06d}';self.documents[identifier]={'type':kind}
        if kind==2:self.documents[identifier]['snapshot']=state()
        self.owned[identifier]=self.session;self.current=identifier
        return identifier
    def create(self):return self.create_doc(1)
    def circle(self,doc,**kwargs):return {'sketch':{'sketch_id':'s-000001'}}
    def background(self,result,document):
        if result['document']['active'] or result['document']['current']:raise RuntimeError('foreground changed')
    def close(self,document):
        closed=self.documents.pop(document);self.owned.pop(document,None)
        if closed['type']==2 and self.source_auto_unload:
            for identifier,doc in list(self.documents.items()):
                if doc.get('path','').endswith('.SLDPRT'):self.documents.pop(identifier)
        if self.current==document:self.current=None
    def write(self,*arguments,document,**options):return self.command(*arguments,document=document,**options)
    def command(self,*arguments,document=None,session=None,lease=None,expected_error=None):
        self.commands.append((arguments,document,session,lease,expected_error))
        action=arguments[:2]
        if action==('document','create'):
            identifier=self.create_doc(2 if arguments[3]=='assembly' else 1)
            return {'document':self.descriptor(identifier)}
        if action==('document','list'):return {'documents':[self.descriptor(i) for i in self.documents]}
        if action==('document','inspect'):
            return {'structure':{'configurations':{'active':'Default'}},'needs_rebuild':0}
        if action==('document','diagnose'):
            return dict(ok=True,action='document.diagnose',document=self.descriptor(document),needs_rebuild=0,
                diagnostics=dict(healthy=True,issues=[],issue_count=0,scanned_feature_count=3,truncated=False,limit=128))
        if action==('document','lease'):
            self.leases[document]='l-000000000001';return {'lease':{'lease_id':self.leases[document]}}
        if action==('feature','extrude'):return {'ok':True}
        if action==('assembly','add-component'):
            return {'component':{'name':'part-'+str(sum(c[0][:2]==action for c in self.commands)%2 or 2)}}
        if action==('document','save-as'):
            path=Path(arguments[2]);path.write_bytes(b'owned native fixture'*30)
            self.documents[document]['path']=str(path)
            if self.documents[document]['type']==2:
                snapshot=self.documents[document]['snapshot'];snapshot.update(path=str(path),modified=False)
                self.saved[str(path)]=copy.deepcopy(snapshot)
            return {'ok':True,'document':self.descriptor(document)}
        if action==('document','save'):
            self.documents[document]['snapshot']['modified']=False
            return {'ok':True,'document':self.descriptor(document)}
        if action==('document','open'):
            path=arguments[2];identifier=self.create_doc(2)
            self.documents[identifier].update(path=path,readonly='--read-only' in arguments,
                snapshot=copy.deepcopy(self.saved[path]))
            if self.changed_on_reopen:self.documents[identifier]['snapshot']['components'][1]['transform'][9]=.001
            if self.truncated:Path(path).write_bytes(b'bad')
            return {'document':self.descriptor(identifier),'api_errors':0,'api_warnings':1 if self.missing_reference else 0}
        if action==('assembly','mate-targets'):
            return dict(ok=True,action='assembly.mate-targets',document=self.descriptor(document),
                        snapshot=copy.deepcopy(self.documents[document]['snapshot']))
        if action==('assembly','add-mate'):
            values={arguments[i]:arguments[i+1] for i in range(2,len(arguments),2)}
            snapshot=json.loads(values['--expected-value']);targets=json.loads(values['--targets'])
            doc=self.documents[document]
            code=('DocumentReadOnly' if doc.get('readonly') else
                  'DocumentLeaseConflict' if session and session!=self.session else
                  'MateValueConflict' if snapshot!=doc['snapshot'] else None)
            if code:
                if expected_error!=code:raise RuntimeError('unexpected refusal '+code)
                return dict(ok=False,error={'type':code},mutation=dict(attempted=False,creation_returned=False,may_have_changed=False))
            if expected_error:raise RuntimeError('expected refusal was lost')
            self.mutations+=1
            if self.native_failure:raise RuntimeError('first native mate failure')
            mate=dict(name='Mate'+str(len(doc['snapshot']['mates'])+1),kind=values['--kind'],alignment=values['--alignment'],error_code=0,suppressed=False,
                components=[t['component'] for t in targets],references=[snapshot['components'][c]['faces'][t['face_index']]['reference_sha256']
                    for c,t in enumerate(targets)],distance_mm=0,parallel_error=0)
            if values['--kind']=='concentric':mate['lock_rotation']=False
            doc['snapshot']['mates'].append(mate)
            doc['snapshot']['update_stamp']+=1
            return dict(ok=True,action='assembly.add-mate',document=self.descriptor(document),before=snapshot,
                snapshot=copy.deepcopy(doc['snapshot']),mate=mate,cleanup_errors=[],
                diagnostics_before=dict(healthy=True,issues=[],issue_count=0,scanned_feature_count=3,truncated=False,limit=128),
                diagnostics=dict(healthy=True,issues=[],issue_count=0,scanned_feature_count=3,truncated=False,limit=128),
                mutation=dict(attempted=True,creation_returned=True,may_have_changed=True))
        if arguments==('capabilities','--full'):
            return dict(host_connected=True,operations=list(public.OPERATION_CATALOG),
                operation_schemas={k:v.parameters for k,v in public.OPERATION_CATALOG.items()},
                operation_result_schemas={k:v.result for k,v in public.OPERATION_CATALOG.items()})
        raise AssertionError('unexpected public command: '+repr(arguments))



class PublicMatePreflightTests(unittest.TestCase):
    def test_preflight_checks_vacant_loopback_by_bind_and_refuses_occupied_endpoint(self):
        spec = importlib.util.spec_from_file_location(
            "_mate_runner_test", ROOT / "scripts/ci/run-assembly-mates-public.py"
        )
        runner_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner_module)
        runner = runner_module.PublicMateRunner.__new__(runner_module.PublicMateRunner)
        runner.record = {}
        runner.checkpoint = mock.Mock()
        runner.health = mock.Mock()
        runner.public = mock.Mock()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            runner.bind_host, runner.bind_port = listener.getsockname()
            with self.assertRaises(OSError):
                runner.preflight()
            self.assertEqual(runner.record, {})
        runner.preflight()
        self.assertTrue(runner.record["preflight_endpoint"]["bind_verified"])
        runner.checkpoint.assert_called_once()
        runner.health.assert_not_called()
        runner.public.assert_not_called()


class PublicMateGateTests(unittest.TestCase):
    def test_four_cases_use_only_public_commands_and_actual_saved_content(self):
        with tempfile.TemporaryDirectory() as directory:
            gate=FakeGate(Path(directory));public.run(gate)
            self.assertTrue(gate.record['success'])
            self.assertEqual(gate.mutations,5)
            self.assertEqual(len(gate.record['cases']),4)
            self.assertTrue(all(len(case['reopens'])==2 for case in gate.record['cases']))
            self.assertFalse(gate.documents)
            parts={path.stem for path in Path(directory).glob('*.SLDPRT')}
            assemblies={path.stem for path in Path(directory).glob('*.SLDASM')}
            self.assertTrue(parts and assemblies and parts.isdisjoint(assemblies))
            self.assertEqual(sum(args[:2]==('assembly','add-mate') for args,*_ in gate.commands),17)

    def test_shared_command_accepts_real_capability_shape_without_operation_ok(self):
        with tempfile.TemporaryDirectory() as directory:
            gate=public.PublicMateSmoke(directory=Path(directory),host_directory=directory,endpoint='127.0.0.1:1',request_timeout_seconds=600)
            payload=FakeGate(Path(directory)).command('capabilities','--full')
            completed=NS(returncode=0,stdout=json.dumps(payload).encode(),stderr=b'')
            with mock.patch.object(gate,'checkpoint'),mock.patch.object(public.modeling.subprocess,'run',return_value=completed):
                self.assertEqual(gate.command('capabilities','--full'),payload)

    def test_changed_capability_contract_refuses_before_fixture_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            gate=FakeGate(Path(directory));original=gate.command
            def command(*args,**kwargs):
                result=original(*args,**kwargs)
                if args==('capabilities','--full'):
                    result['operation_schemas']=copy.deepcopy(result['operation_schemas'])
                    result['operation_schemas']['assembly.add-mate']['additionalProperties']=True
                return result
            gate.command=command
            with self.assertRaisesRegex(RuntimeError,'exact mate request/result contracts'):public.run(gate)
            self.assertFalse(gate.documents)
            self.assertEqual(gate.mutations,0)

    def test_source_can_auto_unload_without_hiding_unrelated_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            gate=FakeGate(Path(directory));gate.source_auto_unload=True
            public.run_case(gate,'concentric','anti-aligned')
            self.assertTrue(gate.record['cases'][0]['success'])
            self.assertFalse(gate.owned)

    def test_changed_relations_missing_reference_and_truncated_output_fail(self):
        for member in ('changed_on_reopen','missing_reference','truncated'):
            with self.subTest(member=member),tempfile.TemporaryDirectory() as directory:
                gate=FakeGate(Path(directory));setattr(gate,member,True)
                with self.assertRaises(RuntimeError):public.run_case(gate,'coincident','aligned')
                self.assertFalse(gate.record['cases'][0]['success'])
                self.assertEqual(gate.mutations,2)

    def test_first_public_native_failure_is_never_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            gate=FakeGate(Path(directory));gate.native_failure=True
            with self.assertRaisesRegex(RuntimeError,'first native mate failure'):
                public.run(gate)
            self.assertEqual(gate.mutations,1)
            self.assertEqual(len(gate.record['cases']),1)

    def test_reopen_compares_geometric_face_content_without_promising_ordinal_stability(self):
        original=state()
        changed=copy.deepcopy(original)
        changed['components'][1]['native_id']=999
        changed['components'][1]['faces'].reverse()
        for i,face in enumerate(changed['components'][1]['faces']):face['index']=i
        public.verify_content(public.content(changed),public.content(original))
        changed['components'][1]['faces'][0]['parameters'][6]=.004
        with self.assertRaises(RuntimeError):public.verify_content(public.content(changed),public.content(original))

    def test_failed_close_is_not_replayed_by_fixture_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            gate=public.PublicMateSmoke(directory=Path(directory),host_directory=directory,endpoint='127.0.0.1:1',request_timeout_seconds=600)
            gate.owned['d-000001']='owner'
            gate.command=mock.Mock(side_effect=RuntimeError('first native CloseDoc failure'))
            with self.assertRaisesRegex(RuntimeError,'first native CloseDoc failure'):gate.close('d-000001')
            gate.cleanup()
            gate.command.assert_called_once()
            self.assertTrue(gate.record['cleanup_errors'])

    def test_real_cli_parser_accepts_exact_public_context_without_private_permission(self):
        parser=build_parser()
        observed=state();targets=[dict(component=c['name'],face_index=0) for c in observed['components']]
        def execute(*args,document,session,lease,expected_error):
            parsed=_typed_operation(parser.parse_args(list(map(str,[*args,'--document',document,'--lease',lease,'--json']))))
            self.assertEqual(parsed[0],'assembly.add-mate')
            self.assertEqual(parsed[1]['expected_value'],observed)
            self.assertNotIn('_calibration',parsed[1])
            self.assertEqual(parsed[3:],('d-000001',3,'l-000000000001'))
            return {}
        gate=mock.Mock();gate.command.side_effect=execute
        public.command_mate(gate,'d-000001','coincident','aligned',targets,observed,lease='l-000000000001')
