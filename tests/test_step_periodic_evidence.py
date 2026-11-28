"""Synthetic AST/mass evidence only; these fixtures are never native CAD artifacts."""
from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/ci'))
from gate_support.step_periodic_evidence import audit_cylinder_topology,verify_cylinder_mass


def synthetic(split):
    rows=["#1=SHAPE_DEFINITION_REPRESENTATION(#2,#3);","#2=PRODUCT_DEFINITION_SHAPE('','',#3);",
          "#3=ADVANCED_BREP_SHAPE_REPRESENTATION('',(#4),#5);","#4=MANIFOLD_SOLID_BREP('',#6);",
          "#5=GEOMETRIC_REPRESENTATION_CONTEXT(3);", "#6=CLOSED_SHELL('',("+','.join('#'+str(i) for i in ([7,8,9,10] if split else [7,8,9]))+"));",
          "#7=ADVANCED_FACE('',(),#11,.T.);","#8=ADVANCED_FACE('',(),#12,.T.);","#9=ADVANCED_FACE('',(),#12,.T.);",
          "#11=CYLINDRICAL_SURFACE('',#5,10.);","#12=PLANE('',#5);"]
    if split:rows.append("#10=ADVANCED_FACE('',(),#11,.T.);")
    return ("ISO-10303-21;\nHEADER;FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));ENDSEC;\nDATA;"+'\n'.join(rows)+"ENDSEC;END-ISO-10303-21;").encode()


class CylinderOracleTests(unittest.TestCase):
    def test_counts_faces_even_when_cylindrical_surface_record_is_reused(self):
        for split,count in ((False,3),(True,4)):
            with self.subTest(split=split):
                result=audit_cylinder_topology(synthetic(split),split)
                self.assertEqual(result['face_count'],count);self.assertEqual(result['face_surface_counts']['CYLINDRICAL_SURFACE'],count-2)

    def test_cylinder_oracle_uses_structure_outside_text_and_comments(self):
        raw = synthetic(False)
        label = "圆柱'' ; ENDSEC; #9999;".encode("utf-8")
        localized = raw.replace(
            b"HEADER;", b"HEADER;FILE_NAME('" + label + b"');/* DATA; ENDSEC; */"
        ).replace(b"MANIFOLD_SOLID_BREP('',", b"MANIFOLD_SOLID_BREP('" + label + b"',")
        self.assertEqual(audit_cylinder_topology(localized, False), audit_cylinder_topology(raw, False))
        for bad in (
            localized.replace("圆".encode("utf-8"), b"\xe6"),
            localized.replace(b"#7=", "#７=".encode("utf-8")),
            localized.replace(b"END-ISO-10303-21;", b"END-ISO-10303-21;\x00"),
        ):
            with self.assertRaises(ValueError):
                audit_cylinder_topology(bad, False)

    def test_opposite_option_extra_face_dangling_duplicate_or_unknown_surface_fail(self):
        raw=synthetic(False)
        bad=[synthetic(True),raw.replace(b'(#7,#8,#9)',b'(#7,#7,#9)'),raw.replace(b'#12,.T.',b'#999,.T.'),
             raw.replace(b'#11=CYLINDRICAL_SURFACE',b'#11=B_SPLINE_SURFACE'),
             raw.replace(b'ENDSEC;END-ISO',b"#20=ADVANCED_FACE('',(),#12,.T.);ENDSEC;END-ISO"),
             raw.replace(b"#3=ADVANCED_BREP_SHAPE_REPRESENTATION('',(#4)",b"#3=ADVANCED_BREP_SHAPE_REPRESENTATION('',(#5)")]
        for value in bad:
            with self.subTest(raw=value),self.assertRaises(ValueError):audit_cylinder_topology(value,False)
        for value in (0,None,'false'):
            with self.assertRaises(ValueError):audit_cylinder_topology(raw,value)

    def mass(self):
        body=dict(volume_mm3=3000*math.pi,surface_area_mm2=800*math.pi,centroid_mm=dict(x=0,y=0,z=15))
        return dict(ok=True,method='native-body-mass-properties',metrics=dict(solid_body_count=1,**deepcopy(body)),bodies=[body])

    def test_exact_mass_both_levels_and_finite_centroid_tolerance(self):
        value=self.mass();self.assertIs(verify_cylinder_mass(value),value)
        value['bodies'][0]['centroid_mm']['x']=2.76e-16;verify_cylinder_mass(value)
        for path,key,bad in (('metrics','volume_mm3',3000),('bodies','surface_area_mm2',float('nan'))):
            value=self.mass();row=value[path] if path=='metrics' else value[path][0];row[key]=bad
            with self.assertRaises(ValueError):verify_cylinder_mass(value)
        value=self.mass();value['metrics']['centroid_mm']['z']=15.00000001
        with self.assertRaises(ValueError):verify_cylinder_mass(value)
        value=self.mass();value['metrics']['solid_body_count']=True
        with self.assertRaises(ValueError):verify_cylinder_mass(value)
