"""Portable public-gate orchestration/provenance faults, never native evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('docprops_public_gate', ROOT / 'scripts/ci/verify-document-properties-public.py')
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)


class NativePrerequisites(unittest.TestCase):
    def proof(self):
        return {'host_revision': '33.5.0', 'native_group_complete': True, 'completed_transitions': 36, 'full_acceptance_eligible': False,
                'transitions': sorted(public.finite_transitions()), 'run_id': 42, 'run_attempt': 1,
                'source_head': 'a' * 40, 'artifact_id': 777, 'artifact_sha256': 'b' * 64}

    def test_missing_native_success_proof_keeps_public_entry_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, 'proof missing'):
                public.verified_proof(Path(folder) / 'absent.json')

    def test_empty_whitelist_and_partial_proof_cannot_open_public_gate(self):
        from swcli import document_drafting_standard as model
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'portable-only-proof.json'
            path.write_text(json.dumps(self.proof()))
            with patch.object(model, 'CALIBRATED_DRAFTING_TRANSITIONS', ()):
                with self.assertRaisesRegex(RuntimeError, 'whitelist'):
                    public.verified_proof(path)
            proof = self.proof(); proof['completed_transitions'] = 30
            path.write_text(json.dumps(proof))
            with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                public.verified_proof(path)

    def test_exact_whitelist_requires_all_and_only_36_typed_transitions(self):
        from swcli import document_drafting_standard as model
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'portable-only-proof.json'; path.write_text(json.dumps(self.proof()))
            transitions = tuple(public.finite_transitions())
            with patch.object(model, 'CALIBRATED_DRAFTING_TRANSITIONS', transitions):
                self.assertEqual(public.verified_proof(path)['completed_transitions'], 36)
            with patch.object(model, 'CALIBRATED_DRAFTING_TRANSITIONS', transitions + ((1, 1, 2, 'drafting-defaults-v1'),)):
                with self.assertRaisesRegex(RuntimeError, 'whitelist'):
                    public.verified_proof(path)

    def test_metadata_checks_pin_success_run_head_attempt_and_digest(self):
        proof = self.proof()
        run = {'id': 42, 'status': 'completed', 'conclusion': 'success', 'event': 'workflow_dispatch',
               'workflow_id': public.WORKFLOW_ID, 'head_sha': proof['source_head'], 'run_attempt': 1,
               'head_branch': 'codex/docprops-calibration-performance'}
        artifact = {'id': 777, 'expired': False, 'digest': 'sha256:' + proof['artifact_sha256'],
                    'workflow_run': {'head_sha': proof['source_head']}, 'name': 'swcli-docprops-performance-42-1'}
        def check(r, a):
            with patch.object(public, 'gh_json', side_effect=[r, {'artifacts': [a]}]):
                return public.validate_dependency(proof)
        self.assertEqual(check(run, artifact)['artifact_id'], 777)
        for key, value in [('conclusion', 'failure'), ('event', 'pull_request'), ('head_sha', 'c' * 40), ('run_attempt', 2)]:
            with self.subTest(key=key), self.assertRaises(RuntimeError): check({**run, key: value}, artifact)
        for key, value in [('expired', True), ('digest', 'sha256:' + 'c' * 64), ('id', 778)]:
            with self.subTest(key=key), self.assertRaises(RuntimeError): check(run, {**artifact, key: value})


class PreparedNativeInputs(unittest.TestCase):
    def test_only_hashed_baseline_files_are_copied_with_windows_path_mapping(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); raw = root / 'raw'; native = raw / 'standards-36'
            native.mkdir(parents=True); (raw / 'standards-36-driver').mkdir()
            original = r'C:\Workspace\run-42\standards-36'
            cases = []
            for kind, suffix in [('part', 'SLDPRT'), ('assembly', 'SLDASM'), ('drawing', 'SLDDRW')]:
                data = (kind * 100).encode(); path = native / ('baseline.' + suffix); path.write_bytes(data)
                cases.append({'kind': kind, 'baseline': {'path': original + '\\' + path.name,
                             'sha256': hashlib.sha256(data).hexdigest()}})
            (native / 'report.json').write_text(json.dumps({'cases': cases}))
            (raw / 'standards-36-driver/driver.json').write_text(json.dumps({'output': original}))
            result = {'native_group_complete': True, 'manifest_sha256': 'test-manifest', 'source_hashes': {'test': 'test'}}
            proof = {'source_head': 'a' * 40, 'manifest_sha256': 'test-manifest', 'source_hashes': {'test': 'test'}}
            auditor = SimpleNamespace(audit=lambda *args: result)
            with patch.object(public, 'load_script', return_value=auditor):
                prepared = public.prepare_fixtures(raw, root / 'fixtures', proof)
            self.assertEqual(len(prepared['fixtures']), 3)
            for item in prepared['fixtures']:
                self.assertEqual(hashlib.sha256(Path(item['path']).read_bytes()).hexdigest(), item['sha256'])
            (native / 'baseline.SLDPRT').write_bytes(b'tampered')
            with patch.object(public, 'load_script', return_value=auditor), self.assertRaisesRegex(RuntimeError, 'baseline bytes'):
                public.prepare_fixtures(raw, root / 'tampered-fixtures', proof)


class PublicProcessGroups(unittest.TestCase):
    def run_fixture(self, output, fail_kind=None, changed_host=False):
        commands = []
        class Daemon:
            pid = 7000
            def __init__(self, command, **kwargs):
                commands.append(('daemon', command))
                kwargs['stdout'].write(b'{"action": "daemon.serve"}\n'); kwargs['stdout'].flush()
            def poll(self): return None
            def wait(self, timeout): return 0
        def run(command, **kwargs):
            if '--run-gate' in command:
                kind = int(command[command.index('--kind') + 1]); commands.append(('kind', kind, kwargs['timeout']))
                if fail_kind == kind: return SimpleNamespace(returncode=1)
                directory = Path(command[command.index('--output-dir') + 1]); directory.mkdir()
                host = {'process_id': 8000 + int(changed_host and kind == 2)}
                (directory / 'document-preferences-standards.json').write_text(json.dumps({'success': True, 'host': host,
                    'host_after': host, 'preference_cases': [{'writes': [{}]*12, 'saved_copies': [{}]*12}],
                    'sdk_mcp_contracts': [{}]}))
                return SimpleNamespace(returncode=0)
            commands.append(('stop', command, kwargs['timeout'])); return SimpleNamespace(returncode=0)
        with patch.object(public.subprocess, 'Popen', side_effect=Daemon), patch.object(public.subprocess, 'run', side_effect=run):
            code = public.run_public(output, output.parent / 'fixtures', 'a' * 40)
        return code, json.loads((output / 'public-report.json').read_text()), commands

    def test_first_failed_kind_stops_remaining_groups_without_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            code, report, calls = self.run_fixture(Path(folder) / 'output', fail_kind=1)
            self.assertEqual(code, 1); self.assertFalse(report['success'])
            self.assertEqual([c for c in calls if c[0]=='kind'], [('kind', 1, 1800)])
            self.assertEqual(sum(c[0]=='daemon' for c in calls), 1)
            self.assertEqual(sum(c[0]=='stop' for c in calls), 1)

    def test_success_requires_three_independent_kind_groups_same_owned_host(self):
        with tempfile.TemporaryDirectory() as folder:
            code, report, calls = self.run_fixture(Path(folder) / 'output')
            self.assertEqual(code, 0); self.assertTrue(report['success'])
            self.assertEqual([c for c in calls if c[0]=='kind'], [('kind', 1, 1800), ('kind', 2, 1800), ('kind', 3, 1800)])
            self.assertFalse(report['full_acceptance_eligible'])
        with tempfile.TemporaryDirectory() as folder:
            code, report, calls = self.run_fixture(Path(folder) / 'output', changed_host=True)
            self.assertEqual(code, 1)
            self.assertEqual([c[1] for c in calls if c[0]=='kind'], [1, 2])

    def test_original_public_gate_default_remains_all_document_kinds(self):
        module = public.load_script('_public_gate_default_test', 'scripts/ci/verify-document-preferences.py')
        import inspect
        self.assertEqual(inspect.signature(module.run).parameters['kinds'].default, module.KINDS)
        with self.assertRaisesRegex(RuntimeError, 'finite unique'):
            module.run(None, Path('/absent'), None, 'standards', kinds=(('BAD', 99),))


class LiveTransportContractComposition(unittest.TestCase):
    def result(self):
        import test_document_drafting_standard as portable_standard
        fixture = portable_standard.DocumentDraftingStandardTests(); fixture.setUp()
        result = fixture.read()
        self.assertTrue(result['ok'])
        result.update(session_id='portable-contract', document={'document_id': 'd-ab12cd', 'title': 'part', 'path': '',
            'type': 1, 'modified': False, 'update_stamp': 19, 'active': False, 'current': False})
        return result

    def probe(self, mcp_drift=False):
        from copy import deepcopy
        before = self.result()
        sdk_result = deepcopy(before)
        mcp_result = {**deepcopy(before), 'request_id': 'portable-mcp-request'}
        if mcp_drift: mcp_result['document']['update_stamp'] += 1
        fake_client = SimpleNamespace(
            daemon=SimpleNamespace(capabilities=lambda **kwargs: SimpleNamespace(require_result=lambda: {
                'operation_schemas': {'document.drafting-standard-set': {'required': ['value', 'expected_snapshot']}}})),
            document=SimpleNamespace(drafting_standard=lambda **kwargs: SimpleNamespace(
                require_result=lambda: sdk_result, request_id='portable-sdk-request')))
        proofs = []
        def verify(gate, profile):
            request = gate.record['events'][-1]['result']['request_id']
            self.assertNotIn(request, proofs); proofs.append(request)
            return {'request_id': request, 'native_setters': []}
        def mock_async(coro):
            coro.close()
            return mcp_result
        with tempfile.TemporaryDirectory() as folder:
            gate = SimpleNamespace(endpoint='127.0.0.1:1', session='portable-contract', directory=Path(folder),
                record={'events': []}, background=lambda result, doc: self.assertFalse(result['document']['active']),
                checkpoint=lambda stage: None)
            with patch('swcli.sdk.Client', return_value=fake_client), patch.object(public.asyncio, 'run', side_effect=mock_async):
                public.contract_probe(gate, SimpleNamespace(verify=verify), 'standards', 'd-ab12cd', before)
            return gate, proofs

    def test_sdk_mcp_envelope_request_ids_are_evidence_not_native_result_fields(self):
        gate, proofs = self.probe()
        self.assertEqual(proofs, ['portable-sdk-request', 'portable-mcp-request'])
        self.assertEqual(len(gate.record['sdk_mcp_contracts']), 1)

    def test_transport_read_may_not_adopt_changed_document_state(self):
        with self.assertRaisesRegex(RuntimeError, 'snapshot/state'):
            self.probe(mcp_drift=True)
