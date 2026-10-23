"""Public gate selection, first-failure and no-retry policy without native COM."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci/verify-fillets.py"
spec = importlib.util.spec_from_file_location("fillet_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def edge(identifier="e-abcdef"):
    return {"entity_id": identifier, "curve_kind": "line",
            "parameter_data": {"start_point_mm": [20, 15, 0], "end_point_mm": [20, 15, 10]},
            "curve_geometry": {"line": {"direction": [0, 0, 1], "root_point_mm": [20, 15, 0]}}}


class FilletGateTests(unittest.TestCase):
    def test_selects_geometry_not_ordinal(self):
        wrong = edge("e-000000")
        wrong["parameter_data"]["end_point_mm"] = [20, 15, 9]
        self.assertEqual(gate.fixture_edge([wrong, edge()]), "e-abcdef")
        reverse = edge()
        reverse["parameter_data"]["start_point_mm"], reverse["parameter_data"]["end_point_mm"] = [20,15,10], [20,15,0]
        self.assertEqual(gate.fixture_edge([reverse]), "e-abcdef")

    def test_missing_ambiguous_or_wrong_line_fails(self):
        for values in ([], [edge(), edge()]):
            with self.assertRaises(RuntimeError):
                gate.fixture_edge(values)
        tilted = edge()
        tilted["curve_geometry"]["line"]["direction"] = [1, 0, 0]
        with self.assertRaises(RuntimeError):
            gate.fixture_edge([tilted])

    def test_first_native_failure_is_not_retried_or_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            smoke = gate.FilletSmoke(directory=Path(directory), host_directory="C:\\Gate", endpoint="localhost:1")
            smoke.health = lambda: {"host": {"process_id": 10}}
            smoke.require_empty = lambda **kwargs: None
            ids = iter(("d-aaaaaa", "d-bbbbbb"))
            smoke.create = lambda: next(ids)
            smoke.rectangle = lambda document: {"sketch": {"sketch_id": "s-aaaaaa"}}
            smoke.feature = lambda *args, **kwargs: None
            smoke.measure = lambda *args, **kwargs: None
            smoke.background = lambda *args: None
            calls = []
            failure = RuntimeError("first native failure")
            def command(*args, **kwargs):
                calls.append((args, kwargs))
                if args[:2] == ("entity", "list"):
                    return {"entities": [edge()], "document": {"update_stamp": 12}}
                if args[:2] == ("feature", "fillet") and not kwargs.get("expected_error"):
                    raise failure
                return {}
            smoke.command = command
            smoke.write = command
            with self.assertRaises(RuntimeError) as caught:
                smoke.run()
            self.assertIs(caught.exception, failure)
            attempts = [(a,k) for a,k in calls if a[:2] == ("feature", "fillet")]
            self.assertEqual(len(attempts), 4)
            self.assertEqual([k.get("expected_error") for _,k in attempts],
                             ["DocumentLeaseConflict", "DocumentLeaseConflict", "DocumentUpdateConflict", None])
            self.assertFalse(any(a[:2] == ("document", "save-as") for a,_ in calls))
            self.assertFalse(any(a[:1] == ("daemon",) for a,_ in calls))


if __name__ == "__main__":
    unittest.main()
