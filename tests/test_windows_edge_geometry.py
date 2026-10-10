"""Edge parameter evidence must not become guessed trim/closure semantics."""

import contextlib
import io
import json
import math
import os
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts.windows_edge_geometry import observe_edge_geometry
from swcli.hosts.windows_entity_geometry import EntityGeometryUnavailable
from swcli.hosts.native_trace import trace_native_request


class EdgeGeometryTests(unittest.TestCase):
    def setUp(self):
        self.curve = SimpleNamespace(
            IsLine=True, IsCircle=False,
            LineParams=(0.06, 0.045, 0.02, 0, 0, -1),
            CircleParams=(0.01, 0.02, 0.005, 0, 0, -1, 0.003),
        )
        self.parameters = SimpleNamespace(
            StartPoint=(0.06, 0.045, 0.02), EndPoint=(0.06, 0.045, 0),
            UMinValue=0.0, UMaxValue=0.02, Sense=True, CurveType=3001,
        )
        self.calls = []
        self.edge = SimpleNamespace(
            GetCurve=lambda: self.get_curve(), GetCurveParams3=lambda: self.get_parameters()
        )

    def get_curve(self):
        self.calls.append("curve")
        return self.curve

    def get_parameters(self):
        self.assertEqual(self.calls[-1], "curve")
        self.calls.append("parameters")
        return self.parameters

    def read(self):
        return observe_edge_geometry(self.edge)

    def circle(self):
        self.curve.IsLine, self.curve.IsCircle = False, True
        self.parameters.CurveType = 3002
        self.parameters.StartPoint = self.parameters.EndPoint = (0.013, 0.02, 0.005)
        self.parameters.UMaxValue = math.tau

    def test_line_is_separate_untrimmed_curve_and_raw_parameter_space(self):
        result = self.read()
        self.assertEqual(self.calls, ["curve", "parameters"])
        self.assertEqual(result["curve_kind"], "line")
        self.assertEqual(result["curve_geometry"]["line"], {
            "root_point_mm": [60.0, 45.0, 20.0], "direction": [0.0, 0.0, -1.0]
        })
        self.assertEqual(result["curve_geometry"]["boundary"], "untrimmed-curve")
        self.assertEqual(result["parameter_data"]["start_point_mm"], [60.0, 45.0, 20.0])
        self.assertEqual(result["parameter_data"]["u_max_native"], 0.02)
        json.dumps(result, allow_nan=False)

    def test_circle_does_not_claim_arc_or_closed_edge_from_equal_endpoints(self):
        self.circle()
        result = self.read()
        self.assertEqual(result["curve_geometry"]["circle"], {
            "center_mm": [10.0, 20.0, 5.0], "axis_direction": [0.0, 0.0, -1.0],
            "radius_mm": 3.0,
        })
        for forbidden in ("closed", "arc", "length_mm", "edge_start", "edge_end"):
            self.assertNotIn(forbidden, json.dumps(result))
        self.parameters.UMaxValue = math.pi
        self.assertEqual(self.read()["curve_geometry"], result["curve_geometry"])

    def test_opposite_sense_is_retained_without_swap_negation_or_length_calls(self):
        self.parameters.Sense = False
        self.parameters.UMinValue, self.parameters.UMaxValue = -10.0, -5.0
        self.curve.GetLength3 = mock.Mock(side_effect=AssertionError("not calibrated"))
        result = self.read()["parameter_data"]
        self.assertEqual((result["u_min_native"], result["u_max_native"]), (-10.0, -5.0))
        self.assertFalse(result["curve_and_edge_same_direction"])
        self.assertEqual(result["start_point_mm"], [60.0, 45.0, 20.0])
        self.curve.GetLength3.assert_not_called()

    def test_unsupported_kind_is_explicit_without_reading_line_or_circle_params(self):
        self.curve = SimpleNamespace(IsLine=False, IsCircle=False)
        self.parameters.CurveType = 3005
        result = self.read()
        self.assertEqual(result["curve_kind"], "unclassified")
        self.assertEqual(result["curve_geometry"], {
            "available": False, "reason": "unsupported-curve-kind"
        })

    def test_curve_is_required_before_parameters_and_no_null_is_absence_proof(self):
        self.curve = None
        with self.assertRaisesRegex(EntityGeometryUnavailable, "curve is absent"):
            self.read()
        self.assertEqual(self.calls, ["curve"])
        self.curve = object()
        self.parameters = None
        with self.assertRaisesRegex(EntityGeometryUnavailable, "parameters are absent"):
            self.read()

    def test_classification_and_native_type_must_agree(self):
        for line, circle, curve_type in (
            (True, True, 3001), (1, False, 3001), (False, None, 3005),
            (True, False, 3002), (False, True, 3001), (False, False, 3001),
            (False, False, 3002), (True, False, True), (True, False, 3001.0),
            (True, False, "3001"), (True, False, 0), (True, False, -1),
        ):
            with self.subTest(line=line, circle=circle, curve_type=curve_type):
                self.curve.IsLine, self.curve.IsCircle = line, circle
                self.parameters.CurveType = curve_type
                with self.assertRaises(EntityGeometryUnavailable):
                    self.read()

    def test_sense_is_strict_boolean(self):
        for sense in (None, 0, 1, 1.0, "false"):
            with self.subTest(sense=sense), mock.patch.object(self.parameters, "Sense", sense):
                with self.assertRaises(EntityGeometryUnavailable):
                    self.read()

    def test_arrays_and_scalars_reject_malformed_nonfinite_boolean_and_overflow(self):
        for member, length in (("StartPoint", 3), ("EndPoint", 3)):
            for value in (None, (), [0] * (length + 1), "000", b"000",
                          [True, 0, 0], [float("nan"), 0, 0], [10**1000, 0, 0],
                          [1e308, 0, 0]):
                with self.subTest(member=member, value=str(value)), mock.patch.object(self.parameters, member, value):
                    with self.assertRaises(EntityGeometryUnavailable):
                        self.read()
        for member in ("UMinValue", "UMaxValue"):
            for value in (None, True, "0", float("nan"), float("inf"), 10**1000):
                with self.subTest(member=member, value=str(value)), mock.patch.object(self.parameters, member, value):
                    with self.assertRaises(EntityGeometryUnavailable):
                        self.read()
        for low, high in ((0, 0), (1, 0)):
            self.parameters.UMinValue, self.parameters.UMaxValue = low, high
            with self.assertRaisesRegex(EntityGeometryUnavailable, "interval"):
                self.read()

    def test_supported_geometry_does_not_silently_repair_directions_or_radius(self):
        for value in (None, (), (0, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, 2),
                      (0, 0, 0, 0, True, 1), (1e308, 0, 0, 0, 0, 1)):
            with mock.patch.object(self.curve, "LineParams", value):
                with self.assertRaises(EntityGeometryUnavailable):
                    self.read()
        self.circle()
        for value in (None, (), (0, 0, 0, 0, 0, 1, 0), (0, 0, 0, 0, 0, 1, -1),
                      (0, 0, 0, 0, 0, 2, 0.003), (0, 0, 0, 0, 0, 1, 1e308)):
            with mock.patch.object(self.curve, "CircleParams", value):
                with self.assertRaises(EntityGeometryUnavailable):
                    self.read()

    def test_trace_has_paired_method_boundaries_without_native_values(self):
        stream = io.StringIO()
        # Telemetry may legitimately contain the same digits as an edge value.
        # Keep that collision deterministic and check the structured payload.
        with mock.patch.dict(os.environ, {"SWCLI_TRACE_NATIVE_CALLS": "1"}), contextlib.redirect_stderr(stream), mock.patch(
            "swcli.hosts.native_trace.time.monotonic", return_value=0.045
        ):
            with trace_native_request("edge-read", "internal.edge-read"):
                self.read()
        records = [json.loads(line) for line in stream.getvalue().splitlines()]
        calls = [record["call"] for record in records if record["phase"] == "begin"]
        self.assertLess(calls.index("IEdge.GetCurve"), calls.index("IEdge.GetCurveParams3"))
        begins = {r["sequence"]: r["call"] for r in records if r["phase"] == "begin"}
        ends = {r["sequence"]: r["call"] for r in records if r["phase"] == "end"}
        self.assertEqual(begins, ends)
        fields = {"event", "request_id", "operation", "worker_pid", "sequence",
                  "stage", "call", "phase", "monotonic_seconds"}
        for record in records:
            self.assertEqual(fields | ({"duration_ms"} if record["phase"] == "end" else set()), set(record))
            self.assertEqual("swcli.native-call", record["event"])
            self.assertEqual("edge-read", record["request_id"])
            self.assertEqual("internal.edge-read", record["operation"])
            self.assertEqual(0.045, record["monotonic_seconds"])
        metadata = [{key: value for key, value in record.items()
                     if key not in {"monotonic_seconds", "duration_ms"}} for record in records]
        self.assertNotIn("0.045", json.dumps(metadata))

    def test_native_exception_is_preserved_not_downgraded_to_unsupported(self):
        def fail():
            raise RuntimeError("native parameter failure")
        self.edge.GetCurveParams3 = fail
        with self.assertRaisesRegex(RuntimeError, "native parameter failure"):
            self.read()


if __name__ == "__main__":
    unittest.main()
