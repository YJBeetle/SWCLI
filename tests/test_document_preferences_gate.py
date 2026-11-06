"""Portable controls for the public gate's actual native-evidence checks."""
import importlib.util
import json
import io
import os
from contextlib import redirect_stderr
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_preferences_gate_test', ROOT / 'scripts/ci/verify-document-preferences.py')
gate_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate_module)


class PreferenceGateProofTests(unittest.TestCase):
    def records(self, calls=(), *, operation='document.annotation-font'):
        rows = [{'event': 'swcli.native-call', 'request_id': 'request-1', 'operation': operation,
                 'worker_pid': 10, 'sequence': 0, 'call': operation, 'phase': 'begin'}]
        for sequence, call in enumerate(calls, 1):
            for phase in ('begin', 'end'):
                rows.append({**rows[0], 'sequence': sequence, 'call': call, 'phase': phase, 'duration_ms': 1})
        rows.append({**rows[0], 'phase': 'end', 'duration_ms': 4})
        return rows

    def check(self, rows, profile='fonts', command='annotation-font', *, result=None, **options):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'native.log'
            path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
            verifier = gate_module.PreferenceTrace(path)
            gate = SimpleNamespace(record={'events': [{'command': ['sw-cli', 'document', command],
                                                       'result': {'request_id': 'request-1', 'ok': True, **(result or {})}}]})
            return verifier.verify(gate, profile, **options)

    def test_noop_rejects_even_one_text_format_property_assignment(self):
        rows = self.records(('ITextFormat.Bold.set',))
        with self.assertRaisesRegex(RuntimeError, 'mutation count'):
            self.check(rows)

    def test_noop_rejects_save_flag(self):
        with self.assertRaisesRegex(RuntimeError, 'mutation count'):
            self.check(self.records(('IModelDoc2.SetSaveFlag',)))

    def test_trace_rejects_native_error_even_when_result_claims_success(self):
        rows = self.records(('ITextFormat.Bold.get',))
        rows[2]['phase'] = 'error'
        with self.assertRaises(RuntimeError):
            self.check(rows)

    def test_trace_rejects_wrong_sequence_and_host(self):
        for key, value in (('sequence', 10), ('worker_pid', 11)):
            rows = self.records(('ITextFormat.Bold.get',))
            rows[2][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): self.check(rows)

    def test_trace_rejects_missing_or_nonfinite_call_duration(self):
        for value in (None, float('nan'), float('inf'), 600000):
            rows = self.records(('ITextFormat.Bold.get',))
            rows[2]['duration_ms'] = value
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'budget'): self.check(rows)

    def test_read_evidence_zero_mutation_is_retained(self):
        from swcli.document_annotation_fonts import ANNOTATION_FONT_MEMBERS
        calls = ['IModelDocExtension.GetUserPreferenceTextFormat'] + ['ITextFormat.' + member + ('' if member == 'IsHeightSpecifiedInPts' else '.get') for member in ANNOTATION_FONT_MEMBERS.values()]
        proof = self.check(self.records(calls))
        self.assertEqual(proof['native_setters'], [])
        self.assertEqual(proof['set_save_flag_calls'], 0)

    def test_incomplete_read_cycle_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'order is incomplete'):
            self.check(self.records(('ITextFormat.Bold.get',)))

    def test_public_stale_font_snapshot_changes_only_cas_input(self):
        before = {'font': {'bold': False, 'height_mm': 3.5}}
        old = json.loads(json.dumps(before))
        args = gate_module.arguments('fonts', before, 'bold', True, stale=True)
        self.assertEqual(before, old)
        self.assertEqual(json.loads(args[-1]), {'bold': True, 'height_mm': 3.5})

    def test_finite_standard_plan_has_all_gb_named_directions(self):
        plan = gate_module.targets('standards', {'standard': {'value': 'gb'}})
        self.assertEqual([name for _, name in plan], ['ansi', 'gb', 'iso', 'gb', 'din', 'gb', 'jis', 'gb', 'bsi', 'gb', 'gost', 'gb'])
        with self.assertRaises(RuntimeError): gate_module.targets('standards', {'standard': {'value': 'custom'}})
        for initial in ('ansi', 'iso', 'din', 'jis', 'bsi', 'gost'):
            with self.subTest(initial=initial):
                planned = gate_module.targets('standards', {'standard': {'value': initial}})
                self.assertEqual(planned, [(None, 'gb')] + plan)
        with self.assertRaises(RuntimeError): gate_module.targets('standards', {'standard': {'value': 'other'}})



class PreferenceGateLeaseAndJsonOrderRegressions(unittest.TestCase):
    def fixture(self, kind=1):
        spec = importlib.util.spec_from_file_location(
            "_preference_gate_real_reader_fixture",
            Path(__file__).with_name("test_document_drafting_standard.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fixture = module.DocumentDraftingStandardTests()
        fixture.setUp()
        if kind == 3:
            fixture.drawing()
        else:
            fixture.document.GetType = lambda: kind
        return fixture

    def actual_read_trace(self, profile, kind):
        from swcli.hosts import windows_document_display_options as display
        from swcli.hosts import windows_document_drafting_standard as standard
        from swcli.hosts.native_trace import trace_native_request
        fixture = self.fixture(kind)
        operation = "document." + gate_module.READS[profile]
        buffer = io.StringIO()
        reader = (display.read_document_display_options_windows if profile == "display"
                  else standard.read_document_drafting_standard_windows)
        # Real reader/trace composition with native-object fakes; no COM.
        with mock.patch.dict(os.environ, {"SWCLI_TRACE_NATIVE_CALLS": "1"}), redirect_stderr(buffer):
            with trace_native_request("request-1", operation):
                result = reader(app=fixture.app, document=fixture.document)
        self.assertTrue(result["ok"], result)
        records = [json.loads(line) for line in buffer.getvalue().splitlines()]
        # Reproduce the actual CLI presentation, which recursively sorts keys.
        presented = json.loads(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return records, presented

    def test_cli_sorted_display_and_standard_json_accept_real_catalog_order_trace(self):
        helper = PreferenceGateProofTests()
        for profile in ("display", "standards"):
            for kind in (1, 2, 3):
                with self.subTest(profile=profile, kind=kind):
                    records, result = self.actual_read_trace(profile, kind)
                    proof = helper.check(records, profile=profile, command=gate_module.READS[profile], result=result)
                    self.assertEqual(proof["native_setters"], [])
                    self.assertGreater(proof["native_call_count"], 0)

    def test_json_key_order_must_not_be_used_as_native_getter_order(self):
        from swcli.document_display_options import DISPLAY_FIELDS
        helper = PreferenceGateProofTests()
        records, result = self.actual_read_trace("display", 1)
        sorted_getters = ["IModelDocExtension.GetUserPreference" + DISPLAY_FIELDS[field]["kind"]
                          for field in result["options"]]
        actual_getters = [row["call"] for row in records if row["phase"] == "begin"
                          and row["call"].startswith("IModelDocExtension.GetUserPreference")]
        self.assertNotEqual(sorted_getters, actual_getters)  # concrete regression precondition
        wrong_rows = helper.records(sorted_getters, operation="document.display-options")
        with self.assertRaisesRegex(RuntimeError, "order is incomplete"):
            helper.check(wrong_rows, profile="display", command="display-options", result=result)

    def test_acquire_requires_recorded_explicit_lease_instead_of_renewing_nothing(self):
        gate = SimpleNamespace(leases={}, command=mock.Mock(return_value={"ok": True}))
        with self.assertRaisesRegex(RuntimeError, "explicit write lease"):
            gate_module.acquire(gate, "d-aaaaaa")
        gate.command.assert_called_once_with(
            "document", "lease", "acquire", "--ttl-seconds", 600, document="d-aaaaaa")

    def test_readonly_target_acquires_real_registry_lease_through_actual_gate_command_tracking(self):
        from swcli.daemon.documents import DocumentRegistry
        from swcli.daemon.operations import execute_operation
        document = SimpleNamespace(
            GetTitle=lambda: "Readonly prepared target", GetPathName=lambda: "",
            GetType=lambda: 1, GetSaveFlag=lambda: False, GetUpdateStamp=lambda: 0,
            IsOpenedReadOnly=lambda: True, IsOpenedViewOnly=lambda: False,
            SetSaveFlag=mock.Mock())
        app = SimpleNamespace(ActiveDoc=document, GetDocuments=lambda: (document,),
                              IsSame=lambda first, second: int(first is second), ActivateDoc3=mock.Mock())
        documents = DocumentRegistry(app)
        entry = documents.register(document)
        with tempfile.TemporaryDirectory() as folder:
            gate = gate_module.support.AnnotationSmoke(
                directory=Path(folder), host_directory=folder, endpoint="127.0.0.1:1", cli=["sw-cli"])
            gate.owned[entry.document_id] = gate.session
            self.assertIsNone(gate.renew(entry.document_id))  # old behavior did not acquire anything
            self.assertEqual(gate.leases, {})
            def transport(command, **options):
                self.assertEqual(command[command.index("document"):command.index("document") + 3],
                                 ["document", "lease", "acquire"])
                result = execute_operation(
                    app, "document.lease.acquire", {"ttl_seconds": 600},
                    documents=documents, session_id=command[command.index("--session") + 1],
                    document_id=command[command.index("--document") + 1])
                result["request_id"] = "lease-policy-1"
                return SimpleNamespace(returncode=0, stdout=json.dumps(result).encode("utf-8"), stderr=b"")
            with mock.patch.object(gate_module.support.modeling.subprocess, "run", side_effect=transport) as run:
                gate_module.acquire(gate, entry.document_id)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(gate.leases[entry.document_id], documents.active_lease(entry)["lease_id"])
            self.assertEqual(documents.active_lease(entry)["session_id"], gate.session)
            self.assertTrue(document.IsOpenedReadOnly())
            self.assertFalse(document.GetSaveFlag())
            document.SetSaveFlag.assert_not_called()
            app.ActivateDoc3.assert_not_called()


if __name__ == '__main__': unittest.main()
