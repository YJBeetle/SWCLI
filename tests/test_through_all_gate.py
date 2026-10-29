"""Portable public gate/oracle tests; not evidence of native CAD acceptance."""
import copy
import math
import unittest
from unittest import mock

# Loading the existing shared coordinator also resolves its gate_support root.
from test_modeling_smoke import gate
from gate_support.model_through_all import ThroughAllCases, verify_through_geometry


class ThroughAllGateTests(unittest.TestCase):
    def test_oracle_detects_shallow_holes_wrong_growth_and_wrong_wall_area(self):
        for profile in ("circle", "rectangle"):
            for thickness in (10, 25):
                area, perimeter = ((9 * math.pi, 6 * math.pi) if profile == "circle" else (24, 20))
                metrics = dict(solid_body_count=1, volume_mm3=(1200-area)*thickness,
                               surface_area_mm2=2*(1200-area)+(140+perimeter)*thickness)
                verify_through_geometry(metrics, thickness, profile)
                for field, value in (
                    ("volume_mm3", 1200*thickness-area),  # Only 1 mm blind removal.
                    ("volume_mm3", (1200-area)*(10 if thickness == 25 else 25)),
                    ("surface_area_mm2", metrics["surface_area_mm2"] - 2*area),
                    ("solid_body_count", 2), ("volume_mm3", float("nan")),
                    ("surface_area_mm2", float("inf")),
                ):
                    changed = {**metrics, field: value}
                    with self.subTest(profile=profile, thickness=thickness, field=field), self.assertRaises(RuntimeError):
                        verify_through_geometry(changed, thickness, profile)

    def test_all_twelve_cases_share_control_flow_and_first_failure_stops(self):
        harness = ThroughAllCases()
        harness.record = {}
        harness.require_empty = mock.Mock()
        harness._through_all_case = mock.Mock()
        harness.through_all_cut()
        cases = harness.record["through_all_cases"]
        self.assertEqual(len(cases), 12)
        self.assertEqual({(c["profile_kind"], c["plane"], c["reverse"]) for c in cases},
                         {(p, plane, reverse) for p in ("circle", "rectangle")
                          for plane in ("front", "top", "right") for reverse in (False, True)})
        self.assertTrue(all(c["success"] for c in cases))
        harness._through_all_case = mock.Mock(side_effect=RuntimeError("native failure"))
        with self.assertRaisesRegex(RuntimeError, "native failure"):
            harness.through_all_cut()
        self.assertEqual(len(harness.record["through_all_cases"]), 1)
        self.assertFalse(harness.record["through_all_cases"][0]["success"])
        harness._through_all_case.assert_called_once()

    def test_readback_refuses_scope_termination_direction_or_state_drift(self):
        harness = ThroughAllCases()
        result = dict(definition=dict(end_condition=1, reverse_direction=True,
            both_directions=False, thin=False, feature_scope=False, from_type=0,
            forward_draft=False, reverse_draft=False), observation={"unchanged": True})
        harness.command = mock.Mock(return_value=result)
        harness._observe_through_all("document", "feature", False)
        for member, value in (("end_condition", 0), ("reverse_direction", False),
                               ("both_directions", True), ("thin", True),
                               ("feature_scope", True), ("from_type", 1),
                               ("forward_draft", True), ("reverse_draft", True)):
            changed = copy.deepcopy(result); changed["definition"][member] = value
            harness.command.return_value = changed
            with self.subTest(member=member), self.assertRaises(RuntimeError):
                harness._observe_through_all("document", "feature", False)
        changed = copy.deepcopy(result); changed["observation"]["unchanged"] = False
        harness.command.return_value = changed
        with self.assertRaises(RuntimeError):
            harness._observe_through_all("document", "feature", False)
