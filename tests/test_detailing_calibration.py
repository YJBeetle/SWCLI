"""Meaningful resource-budget and CI isolation checks for the opt-in calibration."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DetailingCalibrationTests(unittest.TestCase):
    def test_call_and_group_timeouts_stop_at_the_original_failure(self):
        spec = importlib.util.spec_from_file_location("detailing_watchdog", ROOT / "scripts/ci/run-detailing-calibration.py")
        watchdog = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(watchdog)
        begin = {"call": "native-setter", "phase": "begin", "time": 10}
        self.assertIsNone(watchdog.timeout_reason(0, 609, [begin]))
        self.assertIn("600-second", watchdog.timeout_reason(0, 611, [begin]))
        for phase in ("end", "error"):
            self.assertIsNone(watchdog.timeout_reason(0, 611, [begin, {"call": "native-setter", "phase": phase, "time": 11}]))
        self.assertIn("1800-second", watchdog.timeout_reason(0, 1801, []))

    def test_untraced_startup_or_registry_probe_cannot_use_the_group_budget(self):
        spec = importlib.util.spec_from_file_location("detailing_idle_watchdog", ROOT / "scripts/ci/run-detailing-calibration.py")
        watchdog = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(watchdog)
        self.assertIn("600-second", watchdog.timeout_reason(0, 601, []))
        records = [{"call": "completed-read", "phase": "end", "time": 20}]
        self.assertIsNone(watchdog.timeout_reason(0, 620, records))
        self.assertIn("600-second", watchdog.timeout_reason(0, 621, records))

    def test_no_wire_or_environment_override_can_enable_writes(self):
        from swcli.operation_schemas import validate_operation_request
        with self.assertRaises(ValueError):
            validate_operation_request("document.detailing-option-set", {"_calibration": True})


if __name__ == "__main__":
    unittest.main()
