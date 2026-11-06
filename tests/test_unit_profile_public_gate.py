"""Public acceptance rejects weakened CAS, noop, readonly and persistence evidence."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from tests.test_document_units_smoke import UnitsCLI
from swcli.document_unit_profile import FIELDS,LINKAGE,snapshot

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('unit_profile_public_test',ROOT/'scripts/ci/verify-document-unit-profile.py')
public=importlib.util.module_from_spec(spec);spec.loader.exec_module(public)

def profile(kind):
    raw={f:4 if f=='system' else 2 if 'precision' in f or f=='mass_properties.mass_unit' else 4 if f=='mass_properties.volume_unit' else 0 for f in FIELDS}
    return snapshot(kind,raw,(0,1,8,2,0),{n:False if family=='Toggle' else 0 for n,(family,_) in LINKAGE.items()})

class ProfileCLI(UnitsCLI):
    def dispatch(self,args):
        if args.command=='document' and args.document_command in ('unit-profile','unit-profile-set'):
            d=self.documents[args.document_id]
            state=d.setdefault('unit_profile',profile(d['type']))
            result=dict(ok=True,action='document.'+args.document_command,session_id=args.session,document=self.descriptor(d,args.session))
            if args.document_command=='unit-profile':
                result['unit_profile']=deepcopy(state)
                if self.units_defect=='readonly-drift' and d['read_only']:result['unit_profile']['linkage']['swUnitsTimeUnits']+=1
                return result
            if d['lease'] and d['lease']['session']!=args.session:return self.failure('DocumentLeaseConflict')
            if args.expected_update_stamp!=d['stamp']:return self.failure('DocumentUpdateConflict')
            mutation=dict(attempted=False,may_have_changed=False)
            if d['read_only']:return self.failure('ValueError',mutation=mutation)
            if json.loads(args.expected_snapshot)!=state:
                if self.units_defect!='cas-ignored':return self.failure('DocumentUnitProfileConflict',mutation=mutation)
            if int(args.value)!=state['values']['linear.precision']['native_value']:
                return self.failure('UnitProfileCalibrationRequired',mutation=dict(attempted=self.units_defect=='mutation',may_have_changed=self.units_defect=='mutation'))
            if self.units_defect=='noop-dirty':d['modified']=True
            result.update(field=args.field,before=deepcopy(state),unit_profile=deepcopy(state),changed=False,mutation=mutation,document=self.descriptor(d,args.session))
            return result
        if args.command=='document' and args.document_command=='save-as':
            d=self.documents[args.document_id];d['path']=args.output;d['modified']=False
            target=Path(args.output);target.write_bytes(bytes(1024));self.saved[args.output]=deepcopy(d)
            if self.units_defect=='source-changed':(self.fixtures/('units.'+target.suffix[1:])).write_bytes(b'changed')
            return dict(ok=True,action='document.save-as',document=self.descriptor(d,args.session),api_saved=True,save_errors=0,save_warnings=None)
        result=super().dispatch(args)
        if args.command=='document' and args.document_command=='measure':
            result['metrics']=dict(solid_body_count=1,volume_mm3=12000,surface_area_mm2=3800,centroid_mm=dict(x=0,y=0,z=5))
            result.update(action='document.measure',session_id=args.session,scope='sum-of-solid-bodies',coordinate_system='part-model',method='native-body-mass-properties',bodies=[dict(index=0,volume_mm3=12000,surface_area_mm2=3800,centroid_mm=dict(x=0,y=0,z=5))])
            if self.units_defect=='geometry-drift':result['metrics']['centroid_mm']['x']=0.001
        return result

class UnitPublicGateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.fixtures=self.root/'fixtures';self.fixtures.mkdir()
        self.output=self.root/'public'
        self.prior=self.root/'prior.json';self.prior.write_text('[]')
        cases=[]
        for kind,suffix in ((1,'SLDPRT'),(2,'SLDASM'),(3,'SLDDRW')):
            p=self.fixtures/('units.'+suffix);p.write_bytes(bytes(1024))
            cases.append(dict(success=True,document_type=kind,file_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),read=dict(unit_profile=profile(kind))))
        (self.fixtures/'report.json').write_text(json.dumps(dict(success=True,profile='units-read-cas-v1',source_commit='native-head',cases=cases)))
        self.fake=ProfileCLI(self.output,self.fixtures)
    def execute(self):
        with mock.patch.object(public.modeling.subprocess,'run',side_effect=self.fake.run):
            public.main(['--output-dir',str(self.output),'--fixture-dir',str(self.fixtures),'--endpoint','127.0.0.1:18495','--prior-pids',str(self.prior)])
    def test_all_three_public_read_refusal_noop_save_reopen_cases(self):
        self.execute()
        result=json.loads((self.output/'public-unit-profile.json').read_text())
        self.assertTrue(result['success'])
        self.assertFalse(result['changed_write_acceptance'])
        self.assertEqual([c['document_type'] for c in result['unit_cases']],[1,2,3])
        self.assertEqual(self.fake.documents,{})
    def test_first_failure_preserved_and_stops_next_fixture(self):
        for defect in ('noop-dirty','cas-ignored','mutation','readonly-drift','source-changed','geometry-drift'):
            with self.subTest(defect=defect):
                self.setUp();self.fake.units_defect=defect
                with self.assertRaises((RuntimeError,ValueError)):self.execute()
                result=json.loads((self.output/'public-unit-profile.json').read_text())
                self.assertFalse(result['success'])
                self.assertEqual(len(result['unit_cases']),1)
                self.assertIn('error',result)
    def test_uncalibrated_fixture_rejected_before_any_public_command(self):
        report=self.fixtures/'report.json';data=json.loads(report.read_text());data['success']=False;report.write_text(json.dumps(data))
        with self.assertRaises(RuntimeError):self.execute()
        self.assertEqual(self.fake.calls,[])
    def test_durable_failure_is_not_success(self):
        with mock.patch.object(public.evidence,'durable',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.execute()

    def test_native_failure_retained_when_final_evidence_write_fails(self):
        failure=RuntimeError('first public failure')
        original=public.evidence.durable
        calls=0
        def persist(path,value):
            nonlocal calls
            calls+=1
            if calls>1:raise OSError('final write failed')
            return original(path,value)
        with mock.patch.object(public,'run',side_effect=failure),mock.patch.object(public.evidence,'durable',side_effect=persist):
            with self.assertRaises(RuntimeError) as raised:self.execute()
        self.assertIs(raised.exception,failure)

    def test_preexisting_native_pid_is_rejected(self):
        self.prior.write_text('[123]')
        with self.assertRaises(RuntimeError):self.execute()
        self.assertFalse(any(getattr(c,'document_command',None)=='open' for c in self.fake.calls))
