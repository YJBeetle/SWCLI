"""Public gate selection, first-failure and no-retry policy without native COM."""
import importlib.util
import math
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
    def exercise(self, directory, *, invalid_readback=False, refuse_failure=False):
        smoke = gate.FilletSmoke(directory=Path(directory), host_directory="C:\\Gate", endpoint="localhost:1")
        smoke.health = lambda: {"host": {"process_id": 10}}
        smoke.require_empty = lambda **kwargs: None
        ids = iter(("d-aaaaaa", "d-bbbbbb"))
        smoke.create = lambda: next(ids)
        smoke.rectangle = lambda document: {"sketch": {"sketch_id": "s-aaaaaa"}}
        smoke.feature = lambda *args, **kwargs: None
        smoke.background = lambda *args: None
        smoke.measure = lambda *args, **kwargs: {"metrics": {"solid_body_count": 1}}
        smoke.close = lambda *args: None
        calls = []
        expected = 12000 - (1 - math.pi / 4) * 40
        filleted = [False]
        def command(*args, **kwargs):
            calls.append((args, kwargs))
            if args[:1] == ("capabilities",):
                return {"operations": ["feature.fillet"]}
            if kwargs.get("expected_error"):
                if refuse_failure:
                    raise RuntimeError("guard did not reject")
                return {}
            if args[:2] == ("entity", "list"):
                return {"entities": [edge("e-111111" if filleted[0] else "e-abcdef")],
                        "document": {"update_stamp": 12},
                        "observation": {"after": {"editing": False}}}
            if args[:2] == ("feature", "fillet"):
                filleted[0] = True
                return {"entity_id": "e-abcdef", "radius_mm": 2,
                        "bodies": 1, "diagnostics": {"healthy": True, "truncated": False},
                        "mutation": {key: True for key in ("attempted", "creation_returned", "may_have_changed")},
                        "verification": {"passed": True, "edge_count": 1, "profile": "circular",
                                         "tangent_propagation": False, "radius_mm": 3 if invalid_readback else 2},
                        "feature": {"type": "Fillet"}, "rebuilt": True,
                        "before_volume_mm3": 12000, "after_volume_mm3": expected, "cleanup_errors": []}
            if args[:2] == ("document", "inspect"):
                return {"document": {"active": True, "current": True}}
            if args[:2] == ("document", "save-as"):
                (Path(directory) / "fillet.SLDPRT").write_bytes(b"x" * 512)
                return {"document": {"modified": False}}
            if args[:2] == ("document", "open"):
                return {"document": {"document_id": "d-cccccc", "type": 1, "modified": False}}
            return {}
        smoke.command = command
        smoke.write = command
        return smoke, calls

    def test_full_success_roundtrip_uses_one_mutation_and_stale_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            smoke, calls = self.exercise(directory)
            smoke.run()
            self.assertEqual(smoke.record["cases"], ["single-edge-fillet"])
            self.assertEqual(sum(a[:2] == ("feature", "fillet") and not k.get("expected_error") for a,k in calls), 1)
            stale = [k["expected_error"] for a,k in calls if a[:2] == ("entity", "inspect")]
            self.assertEqual(stale, ["EntityReferenceStale"])
            self.assertEqual(sum(a[:2] == ("document", "save-as") for a,_ in calls), 1)

    def test_readback_or_guard_failure_stops_before_save(self):
        for parameter, expected in (("invalid_readback", "radius"), ("refuse_failure", "guard")):
            with self.subTest(parameter=parameter), tempfile.TemporaryDirectory() as directory:
                smoke, calls = self.exercise(directory, **{parameter: True})
                with self.assertRaisesRegex(RuntimeError, expected):
                    smoke.run()
                self.assertFalse(any(a[:2] == ("document", "save-as") for a,_ in calls))

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
                if args[:1] == ("capabilities",):
                    return {"operations": ["feature.fillet"]}
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
