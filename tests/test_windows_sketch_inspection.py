import copy
import math
import unittest
from types import SimpleNamespace
from unittest import mock

from swcli.hosts.windows_sketch_inspection import inspect_sketch_windows
from swcli.result_schemas import OperationResultInvalid, validate_operation_result


def point(x, y, z=0):
    return SimpleNamespace(X=x, Y=y, Z=z)


class SketchInspectionTests(unittest.TestCase):
    def setUp(self):
        self.line = SimpleNamespace(
            GetType=lambda: 0,
            ConstructionGeometry=False,
            GetStartPoint2=lambda: point(0, 0),
            GetEndPoint2=lambda: point(0.1, 0.05),
        )
        self.circle = SimpleNamespace(
            GetType=lambda: 1,
            ConstructionGeometry=True,
            IsCircle=lambda: 1,
            GetRadius=lambda: 0.004,
            GetCenterPoint2=lambda: point(0.01, 0.02),
        )
        self.sketch = SimpleNamespace(
            GetSketchSegments=lambda: (self.line, self.circle),
            GetConstrainedStatus=lambda: 2,
            ModelToSketchTransform=SimpleNamespace(
                ArrayData=[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
            ),
        )
        self.feature = SimpleNamespace(
            Name="renamed-sketch",
            GetTypeName2=lambda: "ProfileFeature",
            GetSpecificFeature2=lambda: self.sketch,
            GetOwnerFeature=lambda: None,
            GetNextFeature=lambda: None,
        )
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            FirstFeature=lambda: self.feature,
            SketchManager=SimpleNamespace(ActiveSketch=None),
            ClearSelection2=mock.Mock(),
            EditRebuild3=mock.Mock(),
        )
        self.app = SimpleNamespace(IsSame=lambda first, second: int(first is second))

    def call(self, **kwargs):
        return inspect_sketch_windows(
            app=self.app, document=self.document, sketch_feature=self.feature, **kwargs
        )

    def schema_check(self, result):
        result = copy.deepcopy(result)
        if "sketch" in result:
            result["sketch"]["sketch_id"] = "s-ab12cd"
        result["document"] = {
            "title": "Part1",
            "path": "",
            "type": 1,
            "modified": True,
            "update_stamp": 0,
        }
        validate_operation_result("sketch.inspect", result)
        return result

    def test_decodes_lines_circles_construction_and_native_constraint_code_without_writes(
        self,
    ):
        result = self.call()
        self.assertTrue(result["ok"])
        self.assertTrue(result["geometry_complete"])
        self.assertEqual(result["segment_count"], 2)
        self.assertEqual(result["profile_segment_count"], 1)
        self.assertEqual(result["sketch"]["constraint_status"], 2)
        self.assertFalse(result["sketch"]["absorbed"] or result["editing"])
        self.assertIsNone(result["sketch"]["owner"])
        self.assertEqual(
            result["segments"][0]["geometry"]["end_mm"], {"x": 100, "y": 50, "z": 0}
        )
        self.assertEqual(
            result["segments"][1]["geometry"],
            {
                "kind": "arc",
                "complete_circle": True,
                "radius_mm": 4,
                "center_mm": {"x": 10, "y": 20, "z": 0},
            },
        )
        self.document.ClearSelection2.assert_not_called()
        self.document.EditRebuild3.assert_not_called()
        self.schema_check(result)

    def test_absorbed_sketch_remains_readable_with_native_owner_identity(self):
        owner = SimpleNamespace(Name="renamed-boss", GetTypeName2=lambda: "ICE")
        self.feature.GetOwnerFeature = lambda: owner
        result = self.call()
        self.assertTrue(result["ok"] and result["sketch"]["absorbed"])
        self.assertEqual(
            result["sketch"]["owner"], {"name": "renamed-boss", "type": "ICE"}
        )
        self.schema_check(result)

    def test_editing_flag_uses_exact_sketch_not_any_active_sketch(self):
        self.document.SketchManager.ActiveSketch = self.sketch
        self.assertTrue(self.call()["editing"])
        self.document.SketchManager.ActiveSketch = object()
        self.assertFalse(self.call()["editing"])

    def test_open_arc_reports_endpoints_and_contract_requires_them(self):
        self.circle.IsCircle = lambda: 0
        self.circle.GetStartPoint2 = lambda: point(0.014, 0.02)
        self.circle.GetEndPoint2 = lambda: point(0.01, 0.024)
        result = self.schema_check(self.call())
        self.assertFalse(result["segments"][1]["geometry"]["complete_circle"])
        del result["segments"][1]["geometry"]["end_mm"]
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("sketch.inspect", result)

    def test_unreported_types_have_metadata_and_explicit_incomplete_warning(self):
        self.line.GetType = lambda: 3
        result = self.call()
        self.assertTrue(result["ok"])
        self.assertFalse(result["geometry_complete"])
        self.assertEqual(result["segments"][0]["type_code"], 3)
        self.assertIsNone(result["segments"][0]["geometry"])
        self.assertEqual(result["warnings"][0]["code"], "sketch-geometry-not-reported")
        self.schema_check(result)

    def test_empty_sketch_is_successfully_observed_without_guessing_geometry(self):
        self.sketch.GetSketchSegments = lambda: None
        result = self.call()
        self.assertTrue(result["ok"] and result["geometry_complete"])
        self.assertEqual(result["segments"], [])
        self.schema_check(result)

    def test_limits_reject_incomplete_inspection_before_decoding(self):
        for limit in (0, -1, True, 1.5):
            with self.subTest(limit=limit):
                self.assertEqual(
                    self.call(max_segments=limit)["error"]["type"], "InvalidArgument"
                )
        result = self.call(max_segments=1)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "SketchInspectionLimitExceeded")
        self.assertNotIn("segments", result)
        self.schema_check(result)

    def test_stale_cross_document_or_nonprofile_handle_is_rejected(self):
        self.document.FirstFeature = lambda: None
        self.assertEqual(self.call()["error"]["type"], "SketchUnavailable")
        self.document.FirstFeature = lambda: self.feature
        self.feature.GetTypeName2 = lambda: "Boss"
        self.assertEqual(self.call()["error"]["type"], "SketchUnavailable")
        self.document.GetType = lambda: 2
        self.assertEqual(self.call()["error"]["type"], "UnsupportedDocumentType")

    def test_native_read_failures_nonfinite_geometry_and_bad_transform_fail_closed(
        self,
    ):
        for change in ("coordinates", "radius", "constraint", "transform"):
            with self.subTest(change=change):
                self.setUp()
                if change == "coordinates":
                    self.line.GetEndPoint2 = lambda: point(math.inf, 0)
                elif change == "radius":
                    self.circle.GetRadius = lambda: math.nan
                elif change == "constraint":
                    self.sketch.GetConstrainedStatus = mock.Mock(
                        side_effect=RuntimeError("COM unavailable")
                    )
                else:
                    self.sketch.ModelToSketchTransform.ArrayData = [0] * 15
                result = self.call()
                self.assertFalse(result["ok"])
                self.assertNotIn("geometry_complete", result)
                self.schema_check(result)


if __name__ == "__main__":
    unittest.main()
