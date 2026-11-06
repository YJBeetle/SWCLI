"""Public mode must reject missing or mismatched provenance before runtime setup."""

from copy import deepcopy
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('table_proof_preflight_test', ROOT / 'scripts/ci/verify-table-defaults-proof.py')
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)


class TableProofPreflightTests(unittest.TestCase):
    def pinned(self):
        return dict(run_id=1, head='a' * 40, artifact_id=2, artifact_name='table-defaults-internal-1-1',
                    artifact_digest='sha256:' + 'b' * 64, report_sha256='c' * 64,
                    native_trace_sha256='d' * 64, harness_trace_sha256='e' * 64)

    def test_empty_proof_fails_before_remote_access(self):
        with mock.patch.object(proof, 'INTERNAL_PROOF', {}), mock.patch.object(proof, 'api') as remote:
            with self.assertRaisesRegex(RuntimeError, 'no independently audited'):
                proof.check_remote(None)
            remote.assert_not_called()

    def test_remote_checks_exact_head_branch_event_success_artifact_digest_and_ownership(self):
        for defect in (None, 'head', 'branch', 'event', 'failed', 'digest', 'expired', 'run'):
            pinned = self.pinned()
            run = dict(head_sha=pinned['head'], conclusion='success', event='workflow_dispatch', head_branch='codex/docprops-table-defaults')
            artifact = dict(name=pinned['artifact_name'], digest=pinned['artifact_digest'], expired=False, workflow_run={'id': 1})
            if defect == 'head': run['head_sha'] = 'f' * 40
            if defect == 'branch': run['head_branch'] = 'main'
            if defect == 'event': run['event'] = 'pull_request'
            if defect == 'failed': run['conclusion'] = 'failure'
            if defect == 'digest': artifact['digest'] = 'sha256:' + 'f' * 64
            if defect == 'expired': artifact['expired'] = True
            if defect == 'run': artifact['workflow_run']['id'] = 3
            with self.subTest(defect=defect), mock.patch.object(proof, 'INTERNAL_PROOF', pinned), \
                 mock.patch.object(proof, 'api', side_effect=[run, artifact]) as remote, redirect_stdout(io.StringIO()):
                if defect:
                    with self.assertRaises(RuntimeError): proof.check_remote(None)
                else:
                    with tempfile.TemporaryDirectory() as temporary:
                        output = Path(temporary) / 'environment'
                        proof.check_remote(output)
                        content = output.read_text()
                        self.assertIn('TABLE_INTERNAL_HEAD=' + pinned['head'], content)
                        self.assertNotIn('TOKEN', content)
                    self.assertEqual(remote.call_args_list[0].args, ('/repos/YJBeetle/SWCLI/actions/runs/1',))
                    self.assertEqual(remote.call_args_list[1].args, ('/repos/YJBeetle/SWCLI/actions/artifacts/2',))

    def test_local_profile_cannot_broaden_independently_audited_scope(self):
        pinned = self.pinned()
        audit = dict(revision='33.5.0', profiles={'1': {'bom.box_border': [[1, 2], [2, 2]]}},
                     native_trace_sha256=pinned['native_trace_sha256'], harness_trace_sha256=pinned['harness_trace_sha256'],
                     native_setter_calls=1)
        exact = {('33.5.0', 1): {'bom.box_border': [(1, 2), (2, 2)]}}
        for broaden in (False, True):
            profiles = deepcopy(exact)
            if broaden: profiles[('33.5.0', 1)]['bom.box_border'].append((2, 0))
            with self.subTest(broaden=broaden), tempfile.TemporaryDirectory() as temporary, \
                 mock.patch.object(proof, 'INTERNAL_PROOF', pinned), mock.patch.object(proof, 'PROFILES', profiles), \
                 mock.patch.object(proof.auditor, 'audit', return_value=audit), redirect_stdout(io.StringIO()):
                if broaden:
                    with self.assertRaisesRegex(RuntimeError, 'runtime transitions differ'):
                        proof.check_local(Path(temporary))
                else:
                    proof.check_local(Path(temporary))
                    self.assertTrue((Path(temporary) / 'independent-audit.json').is_file())
