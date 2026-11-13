"""Synthetic component context only. Never instantiate COM or touch live input."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock
import test_markingjig_control as existing
import test_opening_phases as phase_tests
import opening_phases

m=existing.m
POLICY='component-bodies-probe'


def body(*,kind=0,volume=2.,area=3.):
    return types.SimpleNamespace(GetType=lambda:kind,GetBodyBox=lambda:(0.,0.,0.,2.,2.,2.),
        GetMassProperties=lambda density:(0.,0.,0.,volume,area,0.,0.,0.,0.,0.,0.,0.),
        GetFaceCount=lambda:8,GetEdgeCount=lambda:16)


class ComponentContextTests(unittest.TestCase):
    def setUp(self):
        self.c=existing.Case();self.c.setUp();self.addCleanup(self.c.tearDown)
        self.c.constants.update(swAllBodies=-1,swSolidBody=0,swSheetBody=1,swUserBody_e=0,swNormalBody_e=1)
        self.c.component.ReferencedConfiguration='Render'
        self.c.child.GetConfigurationNames=lambda:('Default','Render')
        self.source=phase_tests.Source(self.c.copy.before)
        self.guard=opening_phases.PhaseGuard(self.c.copy,self.c.report,self.source.capture)
        original=self.c.app.OpenDoc7
        def opening(spec):self.source.transition();return original(spec)
        self.c.app.OpenDoc7=opening
        self.bodies=(body(),);self.info=(1,);self.reads=[]
    def reader(self,component,kind):
        self.reads.append((component,kind));return self.bodies,self.info
    def run_candidate(self,mode='probe',**options):
        c=self.c
        kwargs=dict(phase_guard=self.guard,component_context_policy=POLICY,component_bodies=self.reader);kwargs.update(options)
        return m.one_case(c.app,c.copy,mode,c.root/'new-output',existing.value,c.call,c.live,c.report,c.constants,
                         17,c.export,lambda pid:dict(created_filetime=123,exe_path='raw',exe_sha256='fixed'),**kwargs)
    def context(self,index=0):return self.c.report['observations'][index]['components'][0]['component_context']
    def rejected(self,message):
        with self.assertRaisesRegex(RuntimeError,message):self.run_candidate()
        self.assertFalse(self.c.exports);self.assertNotIn('probe_success',self.c.report)
        self.assertFalse(self.guard.record['loaded_baseline_sealed'])
    def test_default_still_refuses_configuration_mismatch_without_component_body_call(self):
        with self.assertRaisesRegex(RuntimeError,'different configuration'):self.c.run_case('probe')
        self.assertFalse(self.reads);self.assertFalse(self.c.exports)
    def test_explicit_probe_keeps_distinct_document_and_component_geometry_with_two_snapshots(self):
        before=copy.deepcopy(self.c.copy.before);self.run_candidate()
        self.assertTrue(self.c.report['probe_success']);self.assertEqual(len(self.c.opens),1)
        self.assertFalse(self.c.exports);self.assertEqual(len(self.reads),2)
        self.assertTrue(all(kind==-1 for component,kind in self.reads))
        self.assertEqual(self.c.copy.before,before)
        self.assertTrue(self.guard.record['loaded_baseline_sealed'])
        a,b=self.c.report['observations'];self.assertEqual(a,b)
        row=a['components'][0];context=row['component_context']
        self.assertEqual(row['referenced_configuration'],'Render');self.assertEqual(row['model']['configuration'],'Default')
        self.assertFalse(context['model_active_matches_reference']);self.assertTrue(context['complete'])
        self.assertEqual(row['model']['geometry'][0]['volume_m3'],1.)
        self.assertEqual(context['bodies'][0]['volume_m3'],2.)
        self.assertEqual(context['body_info_raw'],[1]);self.assertEqual(context['model_state_after'],row['model'])
        self.assertFalse(any(x in call for call in self.c.calls for x in ('ShowConfiguration','Activate','EditRebuild','Resolve','SaveAs')))
    def test_invoke_is_refused_before_open(self):
        with self.assertRaisesRegex(RuntimeError,'zero-export'):self.run_candidate('invoke')
        self.assertFalse(self.c.opens);self.assertFalse(self.reads);self.assertFalse(self.c.exports)
    def test_missing_phase_or_binding_is_refused_before_open(self):
        for kwargs in (dict(phase_guard=None),dict(component_bodies=None)):
            with self.subTest(kwargs=kwargs),self.assertRaisesRegex(RuntimeError,'zero-export'):self.run_candidate(**kwargs)
        self.assertFalse(self.c.opens)
    def test_wrong_installed_body_info_enum_stops_before_open(self):
        self.c.constants['swNormalBody_e']=0
        self.rejected('constants differ');self.assertFalse(self.c.opens)
    def test_missing_referenced_configuration_is_not_guessed(self):
        self.c.child.GetConfigurationNames=lambda:('Default',)
        self.rejected('absent from independent');self.assertFalse(self.reads)
    def test_unknown_body_info_retains_raw_and_cannot_seal(self):
        self.info=(7,);self.rejected('body-info shape/value')
        self.assertEqual(self.context()['body_info_raw'],[7]);self.assertFalse(self.context()['complete'])
    def test_boolean_body_info_does_not_become_native_int(self):
        self.info=(True,);self.rejected('body-info shape/value')
        self.assertIs(self.context()['body_info_raw'][0],True)
    def test_float_body_info_is_retained_without_integer_coercion(self):
        self.info=(1.0,);self.rejected('body-info shape/value')
        self.assertEqual(self.context()['body_info_raw'],[1.0])
        self.assertIs(type(self.context()['body_info_raw'][0]),float)
    def test_body_info_count_must_match_body_array(self):
        self.info=();self.rejected('body-info shape/value')
        self.assertEqual(self.context()['body_count'],1);self.assertEqual(self.context()['body_info_raw'],[])
    def test_empty_component_bodies_are_unknown_not_model_doc_fallback(self):
        self.bodies=();self.info=();self.rejected('component bodies unavailable')
        self.assertEqual(self.context()['body_count'],0);self.assertEqual(len(self.reads),1)
    def test_unsupported_component_body_type_retained_and_refused(self):
        self.bodies=(body(kind=2),);self.rejected('unsupported component body type')
        self.assertEqual(self.context()['bodies'][0]['type'],2)
    def test_surface_user_classification_is_not_accepted(self):
        self.bodies=(body(kind=1),);self.info=(0,);self.rejected('surface body cannot')
        self.assertEqual(self.context()['body_info_raw'],[0])
    def test_component_body_getter_first_error_and_partial_geometry_retained(self):
        native=ValueError('original component body read error')
        def fail(*args):raise native
        self.bodies[0].GetMassProperties=fail
        with self.assertRaises(ValueError) as caught:self.run_candidate()
        self.assertIs(caught.exception,native)
        self.assertEqual(self.context()['bodies'][0]['bounds'],[0.,0.,0.,2.,2.,2.])
        self.assertFalse(self.context()['complete']);self.assertFalse(self.c.exports)
    def test_malformed_mass_output_retains_actual_raw_value(self):
        self.bodies[0].GetMassProperties=lambda density:None
        self.rejected('component mass geometry unavailable')
        self.assertIsNone(self.context()['bodies'][0]['mass_properties_raw'])
    def test_component_reference_change_during_geometry_is_a_CAS_failure(self):
        def changed():self.c.component.ReferencedConfiguration='Default';return (0.,0.,0.,2.,2.,2.)
        self.bodies[0].GetBodyBox=changed
        self.rejected('reference configuration changed during')
        self.assertEqual(self.context()['referenced_configuration'],'Render')
        self.assertEqual(self.context()['referenced_configuration_after'],'Default')
    def test_independent_document_state_change_during_geometry_is_a_CAS_failure(self):
        def changed(density):self.c.child.GetUpdateStamp=lambda:145;return (0.,0.,0.,2.,3.,0.,0.,0.,0.,0.,0.,0.)
        self.bodies[0].GetMassProperties=changed
        self.rejected('independent model state changed')
        self.assertEqual(self.context()['model_state_after']['stamp'],145)
        self.assertEqual(self.c.report['observations'][0]['components'][0]['model']['stamp'],144)
    def test_component_model_pointer_change_is_not_same_file_alias_acceptance(self):
        def changed(density):self.c.component.GetModelDoc2=lambda:existing.Model(self.c.child.path,1);return (0.,0.,0.,2.,3.,0.,0.,0.,0.,0.,0.,0.)
        self.bodies[0].GetMassProperties=changed
        self.rejected('component model identity changed')
    def test_component_geometry_change_between_loaded_observations_is_not_rebaseline(self):
        def reader(component,kind):
            self.reads.append((component,kind));return (body(volume=2. if len(self.reads)==1 else 3.),),(1,)
        with self.assertRaisesRegex(RuntimeError,'loaded-stage complete model state changed'):
            self.run_candidate(component_bodies=reader)
        self.assertTrue(self.guard.record['loaded_baseline_sealed'])
        self.assertEqual(len(self.c.report['observations']),2);self.assertFalse(self.c.exports)
        self.assertNotIn('probe_success',self.c.report)
    def test_new_audit_requires_nonempty_context_geometry_and_equal_snapshots(self):
        self.run_candidate()
        path=self.c.root/'audit';path.mkdir();(path/'worker.stderr.log').write_text('')
        spec=importlib.util.spec_from_file_location('component_candidate_audit',Path(__file__).with_name('run-markingjig-control.py'))
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        base=dict(success=True,failure=None,cleanup_errors=[],cases=[copy.deepcopy(self.c.report)])
        def audit(report):
            (path/'report.json').write_text(json.dumps(report))
            return runner.audit(path,'probe','opening-transition-probe',POLICY)
        self.assertTrue(audit(base)['success'])
        self.assertFalse(runner.audit(path,'probe','opening-transition-probe')['success'])
        for kind in ('empty','incomplete','missing-reference','different-snapshots'):
            report=copy.deepcopy(base)
            for obs in report['cases'][0]['observations']:
                row=obs['components'][0]
                if kind=='empty':obs['components']=[]
                elif kind=='incomplete':row['component_context']['complete']=False
                elif kind=='missing-reference':row['model']['configurations']=['Default']
            if kind=='different-snapshots':report['cases'][0]['observations'][1]['components'][0]['component_context']['bodies'][0]['volume_m3']=99.
            with self.subTest(kind=kind):self.assertFalse(audit(report)['success'])
    def test_subassembly_never_calls_part_only_body_api_and_retains_independent_CAS(self):
        self.c.child.kind=2
        observer=m.Observation(self.c.app,existing.value,self.c.call,self.c.copy,self.c.constants,17,
            lambda pid:{},component_context_policy=POLICY,component_bodies=self.reader)
        row=dict(model={},referenced_configuration='Render',virtual=False)
        observer.document(self.c.child,row['model'])
        observer.component_geometry(self.c.component,self.c.child,row)
        self.assertEqual(row['component_context']['kind'],'subassembly')
        self.assertTrue(row['component_context']['complete']);self.assertFalse(self.reads)
        self.assertEqual(row['component_context']['model_state_after'],row['model'])
        self.assertEqual(row['component_context']['referenced_configuration_after'],'Render')
    def test_empty_subassembly_census_does_not_claim_part_geometry(self):
        self.c.child.kind=2;self.rejected('no part component geometry')
        self.assertFalse(self.reads)

    def test_byref_variant_binding_has_one_native_entry_and_preserves_out_array(self):
        tree=ast.parse(Path(__file__).with_name('run-markingjig-control.py').read_bytes())
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='component_bodies')
        flags=[]
        class Variant:
            def __init__(self,kind,value):flags.append((kind,value));self.value=value
        client=types.ModuleType('win32com.client');client.VARIANT=Variant
        package=types.ModuleType('win32com');package.client=client
        namespace=dict(pythoncom=types.SimpleNamespace(VT_BYREF=0x4000,VT_VARIANT=12))
        calls=[]
        def native(kind,info):calls.append(kind);info.value=(1,0);return self.bodies
        with mock.patch.dict(sys.modules,{'win32com':package,'win32com.client':client}):
            exec(compile(ast.Module(body=[node],type_ignores=[]),'exact-byref-binding','exec'),namespace)
            actual=namespace['component_bodies'](types.SimpleNamespace(GetBodies3=native),-1)
        self.assertEqual(actual,(self.bodies,(1,0)));self.assertEqual(calls,[-1]);self.assertEqual(flags,[(0x400c,None)])


if __name__=='__main__':unittest.main()
