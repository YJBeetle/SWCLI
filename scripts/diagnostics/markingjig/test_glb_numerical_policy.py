"""Exact synthetic numerical boundaries; no COM, VM or business source access."""
import copy
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path
import unittest
import test_markingjig_control as existing
import test_component_context as context_tests

m=existing.m


def steps(value,n,direction=math.inf):
    for _ in range(n):value=math.nextafter(value,direction)
    return value


def model():
    return dict(type=1,path='C:/fixture/part.SLDPRT',title='part.SLDPRT',configuration='Default',configurations=['Default'],
                stamp=144,readonly=True,modified=False,viewonly=False,needs_rebuild=0,
                geometry=[dict(type=0,bounds=[0.,0.,0.,1.,1.,1.],volume_m3=1.,area_m2=2.,
                               centroid_m=[0.,0.,0.],faces=6,edges=12)])


def snapshot():
    doc=model();b=copy.deepcopy(doc['geometry'][0])
    b.update(body_info=1,bounds_raw=tuple(b['bounds']),mass_properties_raw=[0.,0.,0.,1.,2.,1.,1.,1.,1.,0.,0.,0.])
    top=copy.deepcopy(doc);top.pop('geometry');top['type']=2
    return dict(complete=True,host=dict(pid=17,created_filetime=1,exe_path='fixture',exe_sha256='fixture',revision='33.5.0',
                                      Visible=False,CommandInProgress=False,UserControl=True,UserControlBackground=True),
                top=top,dependencies=[],dependency_queries=[],catalog=[],components=[
        dict(name='part-1',virtual=False,model=doc,referenced_configuration='Default',transform=[1.]*16,
             component_context=dict(complete=True,kind='part',model_state_after=copy.deepcopy(doc),bodies=[b]))])


class NumericalBoundaries(unittest.TestCase):
    def compare_model(self,key,value,before=None):
        a=before or model();b=copy.deepcopy(a)
        if isinstance(key,int):b['geometry'][0]['centroid_m'][key]=value
        else:b['geometry'][0][key]=value
        return m.glb_geometry_comparison(a,b,scope='model')
    def test_centroid_decimal_mm_boundary_and_units_are_exact(self):
        below=math.nextafter(1e-15,0.)
        self.assertLess(Fraction.from_float(below)*1000,Fraction(1,10**12))
        self.assertGreater(Fraction.from_float(1e-15)*1000,Fraction(1,10**12))
        self.assertTrue(self.compare_model(0,below)['accepted'])
        self.assertFalse(self.compare_model(0,1e-15)['accepted'])
        self.assertFalse(self.compare_model(0,1e-12)['accepted'])
        self.assertTrue(self.compare_model(0,-below)['accepted'])
        self.assertFalse(self.compare_model(0,-1e-15)['accepted'])
    def test_centroid_bound_is_per_coordinate_not_vector_norm(self):
        a=model();b=copy.deepcopy(a);b['geometry'][0]['centroid_m']=[math.nextafter(1e-15,0.)]*3
        self.assertTrue(m.glb_geometry_comparison(a,b,scope='model')['accepted'])
    def test_equal_invalid_topology_bounds_or_incomplete_context_refused(self):
        for key,value in (('faces',0),('edges',-1),('bounds',[2.,0.,0.,1.,1.,1.])):
            a=model();a['geometry'][0][key]=value
            with self.subTest(key=key):self.assertFalse(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='model')['accepted'])
        a=snapshot();a['components'][0]['component_context']['complete']=False
        self.assertFalse(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='snapshot')['accepted'])
    def test_zero_nearby_opposite_sign_centroids_use_absolute_bound(self):
        a=model();a['geometry'][0]['centroid_m'][0]=-2e-16
        result=self.compare_model(0,2e-16,a)
        self.assertTrue(result['accepted'])
        check=next(c for c in result['numeric_checks'] if c['path']==['geometry',0,'centroid_m',0])
        self.assertGreater(check['ulp_distance'],2)
        self.assertFalse(self.compare_model(0,2e-15,a)['accepted'])
    def test_signed_zero_values_are_retained_not_normalized(self):
        result=self.compare_model(0,-0.)
        self.assertTrue(result['accepted'])
        check=next(c for c in result['numeric_checks'] if c['path']==['geometry',0,'centroid_m',0])
        self.assertEqual(check['before_hex'],'0x0.0p+0');self.assertEqual(check['after_hex'],'-0x0.0p+0')
        self.assertEqual(check['signed_delta_exact']['numerator'],0)
    def test_volume_one_two_three_ULP_up_and_down(self):
        for direction in (math.inf,0.):
            for n in (1,2,3):
                with self.subTest(direction=direction,n=n):
                    result=self.compare_model('volume_m3',steps(1.,n,direction))
                    self.assertEqual(result['accepted'],n<=2)
                    check=next(c for c in result['numeric_checks'] if c['semantic']=='volume')
                    self.assertEqual(check['ulp_distance'],n)
    def test_volume_subnormals_zero_and_negative_sign(self):
        a=model();a['geometry'][0]['volume_m3']=0.
        for n in (1,2,3):
            with self.subTest(n=n):self.assertEqual(self.compare_model('volume_m3',steps(0.,n),a)['accepted'],n<=2)
        self.assertFalse(self.compare_model('volume_m3',math.nextafter(0.,-math.inf),a)['accepted'])
        self.assertTrue(self.compare_model('volume_m3',-0.,a)['accepted'])
    def test_nonfinite_and_wrong_numeric_types_are_refused_even_equal(self):
        for key in (0,'volume_m3'):
            for value in (math.nan,math.inf,-math.inf,True,0, '0',None):
                with self.subTest(key=key,value=value):
                    self.assertFalse(self.compare_model(key,value)['accepted'])
        a=model();a['geometry'][0]['centroid_m'][0]=math.nan
        self.assertFalse(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='model')['accepted'])
    def test_areas_bounds_topology_configuration_and_state_remain_strict(self):
        mutations=[lambda b:b['geometry'][0].update(area_m2=steps(2.,1)),
                   lambda b:b['geometry'][0]['bounds'].__setitem__(0,math.nextafter(0.,math.inf)),
                   lambda b:b['geometry'][0].update(faces=7),lambda b:b['geometry'][0].update(edges=13),
                   lambda b:b['geometry'][0].update(type=1),lambda b:b.update(configuration='Other'),
                   lambda b:b.update(stamp=145),lambda b:b.update(readonly=False),
                   lambda b:b['geometry'].append(copy.deepcopy(b['geometry'][0]))]
        for change in mutations:
            a=model();b=copy.deepcopy(a);change(b)
            with self.subTest(change=change):self.assertFalse(m.glb_geometry_comparison(a,b,scope='model')['accepted'])
    def test_strict_numeric_rejections_retain_hex_delta_ULP_and_decision(self):
        result=self.compare_model('area_m2',steps(2.,1))
        self.assertFalse(result['accepted'])
        row=next(r for r in result['strict_differences'] if r['path']==['geometry',0,'area_m2'])
        self.assertFalse(row['accepted']);self.assertEqual(row['rule'],'strict');self.assertEqual(row['ulp_distance'],1)
        self.assertEqual(row['before_hex'],(2.).hex());self.assertEqual(row['after_hex'],steps(2.,1).hex())
        self.assertGreater(row['absolute_delta_exact']['numerator'],0)
    def test_unknown_fields_and_shapes_cannot_get_numeric_exception(self):
        a=model();a['geometry'][0]['unknown']=0.;b=copy.deepcopy(a)
        self.assertFalse(m.glb_geometry_comparison(a,b,scope='model')['accepted'])
        a=model();a['geometry'][0]['centroid_m'].append(0.)
        self.assertFalse(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='model')['accepted'])
        a=model();a['other']={'centroid_m':[0.,0.,0.]};b=copy.deepcopy(a);b['other']['centroid_m'][0]=1e-20
        self.assertFalse(m.glb_geometry_comparison(a,b,scope='model')['accepted'])
        with self.assertRaisesRegex(RuntimeError,'scope'):m.glb_geometry_comparison(model(),model(),scope='unknown')
    def test_only_component_semantic_raw_mass_slots_zero_to_three_are_bounded(self):
        for i in range(12):
            a=snapshot();b=copy.deepcopy(a);body=b['components'][0]['component_context']['bodies'][0]
            raw=body['mass_properties_raw'];raw[i]=1e-16 if i<3 else steps(raw[i],1)
            if i<3:body['centroid_m'][i]=raw[i]
            elif i==3:body['volume_m3']=raw[i]
            elif i==4:body['area_m2']=raw[i]
            with self.subTest(index=i):
                result=m.glb_geometry_comparison(a,b,scope='snapshot')
                self.assertEqual(result['accepted'],i<=3)
    def test_raw_aliases_cannot_disagree_even_inside_allowed_bound(self):
        a=snapshot();b=copy.deepcopy(a)
        b['components'][0]['component_context']['bodies'][0]['centroid_m'][0]=1e-16
        result=m.glb_geometry_comparison(a,b,scope='snapshot')
        self.assertFalse(result['accepted']);self.assertTrue(result['invalid_fields'])
    def test_host_or_unrelated_same_named_field_stays_strict(self):
        a=snapshot();a['host']['centroid_m']=[0.,0.,0.];b=copy.deepcopy(a);b['host']['centroid_m'][0]=1e-20
        self.assertFalse(m.glb_geometry_comparison(a,b,scope='snapshot')['accepted'])
    def test_nonfinite_raw_inertia_or_wrong_area_cannot_hide_as_equal(self):
        a=snapshot();a['components'][0]['component_context']['bodies'][0]['mass_properties_raw'][5]=math.inf
        self.assertFalse(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='snapshot')['accepted'])
        a=model();a['geometry'][0]['area_m2']=True
        self.assertFalse(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='model')['accepted'])
    def test_same_missing_model_CAS_fields_on_both_sides_are_refused(self):
        for key in ('stamp','configuration','configurations','readonly','modified','viewonly','needs_rebuild','path','geometry'):
            a=model();a.pop(key)
            with self.subTest(key=key):self.assertFalse(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='model')['accepted'])
    def test_same_unknown_dirty_or_wrong_native_state_type_is_refused(self):
        for key,value in (('stamp',True),('type',True),('readonly',1),('readonly',False),('modified',True),
                          ('viewonly',True),('needs_rebuild',True),('needs_rebuild',1),('path',''),('title',None),
                          ('configuration',''),('configuration','Missing'),('configurations',[]),
                          ('configurations',['Default','Default']),('configurations',['Default',None])):
            a=model();a[key]=value
            with self.subTest(key=key,value=value):self.assertFalse(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='model')['accepted'])
    def test_subassembly_geometry_marker_required_and_exact(self):
        a=model();a['type']=2;a['geometry']=dict(kind='subassembly',model_state_observed=True)
        self.assertTrue(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='model')['accepted'])
        for value in (None,{},[],dict(kind='part',model_state_observed=True),dict(kind='subassembly',model_state_observed=1)):
            a['geometry']=value
            with self.subTest(value=value):self.assertFalse(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='model')['accepted'])
    def test_snapshot_requires_seven_native_collections_and_top_without_geometry(self):
        a=snapshot();self.assertTrue(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='snapshot')['accepted'])
        for key in a:
            b=copy.deepcopy(a);b.pop(key)
            with self.subTest(key=key):self.assertFalse(m.glb_geometry_comparison(b,copy.deepcopy(b),scope='snapshot')['accepted'])
        a['top']['geometry']=dict(kind='subassembly',model_state_observed=True)
        self.assertFalse(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='snapshot')['accepted'])
    def test_snapshot_top_and_host_identity_fields_cannot_disappear_together(self):
        for section,keys in (('top',('stamp','configuration','configurations','readonly')),
                             ('host',('pid','created_filetime','exe_path','exe_sha256','revision','Visible','CommandInProgress','UserControl','UserControlBackground'))):
            for key in keys:
                a=snapshot();a[section].pop(key)
                with self.subTest(section=section,key=key):self.assertFalse(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='snapshot')['accepted'])
        for key,value in (('pid',True),('created_filetime',0),('Visible',0),('revision','unknown')):
            a=snapshot();a['host'][key]=value
            with self.subTest(key=key):self.assertFalse(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='snapshot')['accepted'])
    def test_snapshot_component_kind_model_type_and_virtual_readonly_are_bound(self):
        a=snapshot();a['components'][0]['component_context']['kind']='subassembly'
        self.assertFalse(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='snapshot')['accepted'])
        a=snapshot();row=a['components'][0];row['model']['readonly']=row['component_context']['model_state_after']['readonly']=False
        self.assertFalse(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='snapshot')['accepted'])
        row['virtual']=True
        self.assertTrue(m.glb_geometry_comparison(a,copy.deepcopy(a),scope='snapshot')['accepted'])

    def test_three_observed_number_shapes_get_receipts_without_raw_mutation(self):
        a=model();a['geometry'].append(copy.deepcopy(a['geometry'][0]))
        a['geometry'][0]['centroid_m'][2]=-0.00491648046615544
        a['geometry'][1].update(volume_m3=3.657348806308393e-08,centroid_m=[0.027470467043563977,0.,0.])
        b=copy.deepcopy(a);b['geometry'][0]['centroid_m'][2]=-0.004916480466155441
        b['geometry'][1]['centroid_m'][0]=0.027470467043563974;b['geometry'][1]['volume_m3']=3.657348806308394e-08
        original=(copy.deepcopy(a),copy.deepcopy(b));result=m.glb_geometry_comparison(a,b,scope='model')
        self.assertTrue(result['accepted']);self.assertEqual((a,b),original)
        changed=[c for c in result['numeric_checks'] if c['before_hex']!=c['after_hex']]
        self.assertEqual(len(changed),3);self.assertTrue(all(c['accepted'] and c['ulp_distance']==1 for c in changed))
        self.assertEqual(json.loads(json.dumps(result)),result)


class NumericalIntegration(unittest.TestCase):
    def setUp(self):
        self.fixture=context_tests.ComponentContextTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.c=self.fixture.c
    def audit(self):
        path=self.c.root/'numerical-audit';path.mkdir(exist_ok=True);(path/'worker.stderr.log').write_text('')
        (path/'report.json').write_text(json.dumps(dict(success=True,failure=None,cleanup_errors=[],cases=[self.c.report])))
        spec=importlib.util.spec_from_file_location('numerical_supervisor',Path(__file__).with_name('run-markingjig-control.py'))
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        return runner.audit(path,'probe','opening-transition-probe','component-bodies-probe')
    def test_local_model_after_one_ULP_is_raw_and_supervisor_recomputes(self):
        body=self.c.child.GetBodies2(-1,False)[0];count=[]
        def properties(density):
            count.append(1);return (0.,0.,0.,1. if len(count)%2 else steps(1.,1),1.,0.,0.,0.,0.,0.,0.,0.)
        body.GetMassProperties=properties;self.fixture.run_candidate()
        self.assertTrue(self.c.report['probe_success']);self.assertFalse(self.c.exports)
        self.assertEqual(len(self.c.report['geometry_comparisons']),3)
        row=self.c.report['observations'][0]['components'][0]
        self.assertNotEqual(row['model']['geometry'][0]['volume_m3'],row['component_context']['model_state_after']['geometry'][0]['volume_m3'])
        self.assertTrue(self.audit()['success'])
        self.assertNotIn('geometry_comparisons',self.c.report['observations'][0])
    def test_snapshot_two_ULP_body_volume_and_raw_alias_agree(self):
        reads=[]
        def reader(component,kind):
            reads.append(1);return (context_tests.body(volume=2. if len(reads)==1 else steps(2.,2)),),(1,)
        self.fixture.run_candidate(component_bodies=reader)
        self.assertTrue(self.audit()['success'])
        whole=self.c.report['geometry_comparisons'][-1]['comparison']
        changed=[c for c in whole['numeric_checks'] if c['ulp_distance']]
        self.assertEqual(len(changed),2);self.assertTrue(all(c['ulp_distance']==2 for c in changed))
    def test_snapshot_three_ULP_volume_stops_without_rebaseline(self):
        reads=[]
        def reader(component,kind):
            reads.append(1);return (context_tests.body(volume=2. if len(reads)==1 else steps(2.,3)),),(1,)
        with self.assertRaisesRegex(RuntimeError,'loaded-stage'):self.fixture.run_candidate(component_bodies=reader)
        self.assertNotIn('probe_success',self.c.report);self.assertFalse(self.c.exports)
        self.assertFalse(self.c.report['geometry_comparisons'][-1]['comparison']['accepted'])
    def test_snapshot_inertia_one_ULP_remains_strict(self):
        reads=[]
        def reader(component,kind):
            reads.append(1);b=context_tests.body()
            b.GetMassProperties=lambda density:(0.,0.,0.,2.,3.,1. if len(reads)==1 else steps(1.,1),0.,0.,0.,0.,0.,0.)
            return (b,),(1,)
        with self.assertRaisesRegex(RuntimeError,'loaded-stage'):self.fixture.run_candidate(component_bodies=reader)
        self.assertFalse(self.c.exports)
    def test_original_strict_snapshot_path_still_rejects_one_ULP(self):
        self.c.component.ReferencedConfiguration='Default';body=self.c.child.GetBodies2(-1,False)[0];count=[]
        def properties(density):
            count.append(1);return (0.,0.,0.,1. if len(count)==1 else steps(1.,1),1.,0.,0.,0.,0.,0.,0.,0.)
        body.GetMassProperties=properties
        with self.assertRaisesRegex(RuntimeError,'loaded-stage'):
            m.one_case(self.c.app,self.c.copy,'probe',self.c.root/'output',existing.value,self.c.call,self.c.live,self.c.report,
                       self.c.constants,17,self.c.export,lambda pid:dict(created_filetime=1),phase_guard=self.fixture.guard)
        self.assertNotIn('geometry_numerical_policy',self.c.report);self.assertFalse(self.c.exports)
    def test_audit_refuses_tampered_receipt_raw_state_or_missing_policy(self):
        self.fixture.run_candidate();self.assertTrue(self.audit()['success']);original=copy.deepcopy(self.c.report)
        for kind in ('accepted','missing','raw-state','policy'):
            self.c.report.clear();self.c.report.update(copy.deepcopy(original))
            if kind=='accepted':self.c.report['geometry_comparisons'][0]['comparison']['accepted']=False
            elif kind=='missing':self.c.report.pop('geometry_comparisons')
            elif kind=='policy':self.c.report.pop('geometry_numerical_policy')
            else:self.c.report['observations'][1]['components'][0]['model']['stamp']+=1
            with self.subTest(kind=kind):self.assertFalse(self.audit()['success'])


if __name__=='__main__':unittest.main()
