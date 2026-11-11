"""Independent audit boundaries; these small synthetic checks are not native proof."""
from copy import deepcopy
import importlib.util
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('unit_native_audit_test',ROOT/'docs/verification/audit-units-write-42414478796.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def comparison(before,after):
    flat=lambda m:{**{k:m[k] for k in ('solid_body_count','volume_mm3','surface_area_mm2')},**{'centroid_mm.'+k:v for k,v in m['centroid_mm'].items()}}
    a,b=flat(before),flat(after)
    return dict(exact_equal=before==after,differences={k:dict(before=a[k],after=b[k],before_hex=float(a[k]).hex(),after_hex=float(b[k]).hex(),delta=b[k]-a[k]) for k in a if a[k]!=b[k]},centroid_absolute_limit_mm=1e-12,accepted_under_units_centroid_bound=True)


class NativeAuditBoundaries(unittest.TestCase):
    def test_ulp_volume_area_and_body_type_cannot_be_hidden(self):
        before=dict(solid_body_count=1,volume_mm3=12000.0,surface_area_mm2=3800.0,centroid_mm=dict(x=0.0,y=0.0,z=0.0))
        for field in ('volume_mm3','surface_area_mm2'):
            after=deepcopy(before);after[field]=math.nextafter(after[field],math.inf)
            with self.assertRaises(ValueError):audit.geometry(before,after,comparison(before,after))
        after=deepcopy(before);after['solid_body_count']=True
        with self.assertRaises(ValueError):audit.geometry(before,after,comparison(before,after))

    def test_exact_centroid_limit_and_raw_false_hex_are_preserved(self):
        before=dict(solid_body_count=1,volume_mm3=12000.0,surface_area_mm2=3800.0,centroid_mm=dict(x=0.0,y=0.0,z=0.0))
        for axis in 'xyz':
            after=deepcopy(before);after['centroid_mm'][axis]=1e-12
            expected=comparison(before,after);audit.geometry(before,after,expected)
            changed=deepcopy(expected);changed['exact_equal']=True
            with self.assertRaises(ValueError):audit.geometry(before,after,changed)
            changed=deepcopy(expected);changed['differences']['centroid_mm.'+axis]['after_hex']='wrong'
            with self.assertRaises(ValueError):audit.geometry(before,after,changed)
            after['centroid_mm'][axis]=math.nextafter(1e-12,math.inf)
            with self.assertRaises(ValueError):audit.geometry(before,after,comparison(before,after))
