"""Only the explicitly approved centroid bound may absorb float roundoff."""
from copy import deepcopy
import importlib.util
from math import nextafter
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location("_approved_tolerance_geometry",Path(__file__).resolve().parents[1]/"scripts/ci/gate_support/tolerance_geometry.py")
geometry=importlib.util.module_from_spec(spec);spec.loader.exec_module(geometry)


class ApprovedGeometryTests(unittest.TestCase):
    def setUp(self):
        self.before=dict(solid_body_count=1,volume_mm3=11999.999999999998,surface_area_mm2=3799.9999999999995,
                         centroid_mm=dict(x=0.,y=5.514537417020185e-16,z=5.))

    def test_observed_roundoff_and_exact_boundary_pass(self):
        after=deepcopy(self.before);after["centroid_mm"]["y"]=8.271806125530278e-16
        geometry.verify_unchanged_geometry(self.before,after)
        self.before["centroid_mm"]["y"]=0.
        after["centroid_mm"]["y"]=1e-12
        geometry.verify_unchanged_geometry(self.before,after)

    def test_volume_area_one_ulp_and_body_count_still_fail(self):
        for field in ("volume_mm3","surface_area_mm2","solid_body_count"):
            after=deepcopy(self.before)
            after[field]=nextafter(after[field],float("inf")) if field!="solid_body_count" else 2
            with self.subTest(field=field),self.assertRaises(RuntimeError):geometry.verify_unchanged_geometry(self.before,after)

    def test_centroid_beyond_bound_or_nonfinite_fail(self):
        for value in (nextafter(1e-12,float("inf")),float("nan"),float("inf")):
            after=deepcopy(self.before);after["centroid_mm"]["x"]=value
            with self.subTest(value=value),self.assertRaises(RuntimeError):geometry.verify_unchanged_geometry(self.before,after)

    def test_equal_but_wrong_analytic_centroid_does_not_pass(self):
        before=deepcopy(self.before);before["centroid_mm"]["z"]=6.
        with self.assertRaises(RuntimeError):geometry.verify_unchanged_geometry(before,before)


if __name__=="__main__":unittest.main()
