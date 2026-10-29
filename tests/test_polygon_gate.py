"""Public installed polygon gate oracles and failure boundaries, without CAD."""
import copy
import math
import unittest
from unittest import mock
from test_modeling_smoke import gate
from gate_support.model_polygons import PolygonCases, verify_polygon_metrics, verify_polygon_segments, PROFILES

IDENTITY = [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]


class PolygonGateTests(unittest.TestCase):
    def test_all_48_cases_and_first_failure_stops_without_retry(self):
        harness = PolygonCases(); harness.record={}
        harness._polygon_case=mock.Mock(); harness.require_empty=mock.Mock()
        harness.polygon_model()
        cases=harness.record['polygon_cases']
        self.assertEqual(len(cases),48)
        self.assertEqual({(c['shape'],c['winding'],c['mode'],c['plane'],c['reverse']) for c in cases},
            {(shape,winding,mode,plane,reverse) for shape in PROFILES for winding in ('ccw','cw')
             for mode in ('boss','cut') for plane in ('front','top','right') for reverse in (False,True)})
        self.assertTrue(all(c['success'] for c in cases))
        harness._polygon_case=mock.Mock(side_effect=RuntimeError('native failure'))
        with self.assertRaisesRegex(RuntimeError,'native failure'): harness.polygon_model()
        harness._polygon_case.assert_called_once()
        self.assertEqual(len(harness.record['polygon_cases']),1)
        self.assertFalse(harness.record['polygon_cases'][0]['success'])

    def test_independent_volume_surface_centroid_and_direction_oracle(self):
        for shape in PROFILES:
            perimeter,cx=(60,-10+20/3) if shape=='triangle' else (70,-2.5)
            for mode in ('boss','cut'):
                for reverse in (False,True):
                    volume,surface=(1500,300+perimeter*10) if mode=='boss' else (11250,3800+perimeter*5)
                    x,z=(cx,5) if mode=='boss' else (-750*cx/11250,(60000-1875)/11250)
                    metric=dict(solid_body_count=1,volume_mm3=volume,surface_area_mm2=surface,
                                centroid_mm=dict(x=x,y=0,z=-z if reverse else z))
                    verify_polygon_metrics(metric,shape,mode,reverse,IDENTITY)
                    for key,value in [('volume_mm3',volume-1),('surface_area_mm2',surface-1),
                                      ('solid_body_count',True),('volume_mm3',math.nan)]:
                        with self.subTest(shape=shape,mode=mode,key=key),self.assertRaises(RuntimeError):
                            verify_polygon_metrics({**metric,key:value},shape,mode,reverse,IDENTITY)
                    changed=copy.deepcopy(metric);changed['centroid_mm']['z']+=.01
                    with self.assertRaises(RuntimeError): verify_polygon_metrics(changed,shape,mode,reverse,IDENTITY)

    def test_readback_cycle_rejects_wrong_vertices_extra_or_duplicate_edges(self):
        for points in PROFILES.values():
            observed=dict(geometry_complete=True,editing=False,segment_count=len(points),profile_segment_count=len(points),
                segments=[dict(construction=False,geometry=dict(kind='line',
                    start_mm=dict(x=p[0],y=p[1],z=0),end_mm=dict(x=points[(i+1)%len(points)][0],y=points[(i+1)%len(points)][1],z=0)))
                    for i,p in enumerate(points)])
            verify_polygon_segments(observed,points)
            for mutation in (lambda r:r.update(editing=True),lambda r:r.update(geometry_complete=False),
                    lambda r:r['segments'][0]['geometry']['start_mm'].update(x=100),
                    lambda r:r['segments'].__setitem__(0,r['segments'][1])):
                value=copy.deepcopy(observed);mutation(value)
                with self.assertRaises(RuntimeError):verify_polygon_segments(value,points)

    def test_full_native_set_calls_polygon_but_core_does_not(self):
        for suite in ('full','core'):
            smoke=gate.ModelingSmoke(directory=__import__('pathlib').Path('/tmp'),host_directory='C:\\Evidence',endpoint='127.0.0.1:1',suite=suite,case_set='native')
            with mock.patch.object(smoke,'health',return_value={'host':{'process_id':42}}), \
                 mock.patch.object(smoke,'command'),mock.patch.object(smoke,'checkpoint'), \
                 mock.patch.object(smoke,'require_empty'),mock.patch.object(smoke,'native_model'), \
                 mock.patch.object(smoke,'polygon_model') as polygon:
                smoke.run()
            self.assertEqual(polygon.call_count,1 if suite=='full' else 0)
            self.assertEqual(smoke.record['cases'],['native-model','polygon-model'] if suite=='full' else ['native-model'])
