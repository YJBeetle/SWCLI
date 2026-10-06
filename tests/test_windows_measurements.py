import copy
import math
import unittest
from types import SimpleNamespace
from unittest import mock

from swcli.hosts.windows_measurements import measure_part_windows
from swcli.result_schemas import OperationResultInvalid, validate_operation_result


class PartMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.first = self.body((0.01, 0.02, 0.03), 4e-5, 0.012)
        self.document = SimpleNamespace(
            GetType=lambda: 1,
            GetBodies2=mock.Mock(return_value=[self.first]),
            ClearSelection2=mock.Mock(),
            EditRebuild3=mock.Mock(),
        )

    def body(self, center, volume, area):
        return SimpleNamespace(
            GetMassProperties=mock.Mock(
                return_value=[*center, volume, area, volume, 0, 0, 0, 0, 0, 0]
            )
        )

    def measure(self, **arguments):
        return measure_part_windows(document=self.document, **arguments)

    def test_native_units_and_all_hidden_solids_without_selection_or_rebuild(self):
        result = self.measure()
        self.assertTrue(result["ok"], result)
        self.assertEqual(
            result["metrics"],
            {
                "solid_body_count": 1,
                "volume_mm3": 40000,
                "surface_area_mm2": 12000,
                "centroid_mm": {"x": 10, "y": 20, "z": 30},
            },
        )
        self.document.GetBodies2.assert_called_once_with(0, False)
        self.first.GetMassProperties.assert_called_once_with(1.0)
        self.document.ClearSelection2.assert_not_called()
        self.document.EditRebuild3.assert_not_called()
        self.assertNotIn("mass", result["metrics"])

    def test_multiple_bodies_are_summed_not_unioned_and_centroid_is_volume_weighted(
        self,
    ):
        self.document.GetBodies2.return_value.append(
            self.body((0.05, 0.06, 0.07), 1e-5, 0.003)
        )
        result = self.measure()
        self.assertEqual(result["scope"], "sum-of-solid-bodies")
        self.assertAlmostEqual(result["metrics"]["volume_mm3"], 50000)
        self.assertAlmostEqual(result["metrics"]["surface_area_mm2"], 15000)
        self.assertEqual(result["metrics"]["centroid_mm"], {"x": 18, "y": 28, "z": 38})
        self.assertEqual([body["index"] for body in result["bodies"]], [0, 1])

    def test_invalid_limit_does_not_read_native_geometry(self):
        for limit in (0, -1, True, 1.5):
            self.assertEqual(
                self.measure(max_bodies=limit)["error"]["type"], "InvalidArgument"
            )
        self.document.GetBodies2.assert_not_called()

    def test_non_part_empty_part_or_limit_fail_without_reading_body_properties(self):
        self.document.GetType = lambda: 2
        self.assertEqual(self.measure()["error"]["type"], "UnsupportedDocumentType")
        self.document.GetType = lambda: 1
        self.document.GetBodies2.return_value = []
        self.assertEqual(self.measure()["error"]["type"], "NoSolidBodies")
        self.document.GetBodies2.return_value = [self.first, self.first]
        self.assertEqual(
            self.measure(max_bodies=1)["error"]["type"], "MeasurementLimitExceeded"
        )
        self.first.GetMassProperties.assert_not_called()

    def test_missing_truncated_nonfinite_and_overflow_properties_do_not_report_totals(
        self,
    ):
        for properties in (
            None,
            [0] * 6,
            [0] * 12,
            [0, 0, math.inf, 1, 1, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, math.nan, 1, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 1e308, 1, 0, 0, 0, 0, 0, 0, 0],
        ):
            with self.subTest(properties=properties):
                self.first.GetMassProperties.return_value = properties
                result = self.measure()
                self.assertEqual(result["error"]["type"], "MeasurementUnavailable")
                self.assertNotIn("metrics", result)
                validate_operation_result("document.measure", result)

    def test_com_error_is_structured_without_changing_document(self):
        self.first.GetMassProperties.side_effect = RuntimeError(
            "native geometry unavailable"
        )
        result = self.measure()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["message"], "native geometry unavailable")
        self.document.ClearSelection2.assert_not_called()

    def test_result_schema_requires_positive_body_evidence_and_defined_centroid(self):
        result = self.measure()
        result["document"] = {
            "title": "Part1",
            "path": "",
            "type": 1,
            "modified": True,
            "update_stamp": 0,
        }
        validate_operation_result("document.measure", result)
        for key, value in (
            ("volume_mm3", 0),
            ("surface_area_mm2", -1),
            ("solid_body_count", 0),
            ("centroid_mm", None),
        ):
            invalid = copy.deepcopy(result)
            invalid["metrics"][key] = value
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result("document.measure", invalid)
        invalid = copy.deepcopy(result)
        invalid["bodies"] = []
        with self.assertRaises(OperationResultInvalid):
            validate_operation_result("document.measure", invalid)
