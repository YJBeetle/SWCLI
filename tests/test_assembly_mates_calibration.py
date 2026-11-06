"""Calibration wiring/budgets/content comparisons; no native CAD proof."""
import copy
import importlib.util
from pathlib import Path
import unittest
import shutil
import subprocess
import tempfile
from types import SimpleNamespace as NS
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]


def load(filename):
    spec=importlib.util.spec_from_file_location(filename.replace('-','_').replace('.','_'), ROOT/'scripts/ci'/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class CalibrationTests(unittest.TestCase):
    def test_manual_branch_scoped_job_never_changes_default_native_gate_or_concurrency(self):
        workflow=(ROOT/'.github/workflows/ci.yml').read_text()
        job=workflow.split('  assembly-mates-calibration:\n',1)[1].split('\n\n  release:',1)[0]
        default=workflow.split('  solidworks-e2e:\n',1)[1].split('\n\n  assembly-mates-calibration:',1)[0]
        inputs=workflow.split('      assembly_mates_calibration:\n',1)[1].split('      native_full:',1)[0]
        self.assertIn('default: false',inputs)
        condition=next(line for line in job.splitlines() if line.startswith('    if:'))
        for part in ("github.event_name == 'workflow_dispatch'", "github.repository == 'YJBeetle/SWCLI'",
                     "github.ref == 'refs/heads/codex/swcli-assembly-mates'", 'inputs.assembly_mates_calibration'):
            self.assertIn(part,condition)
        self.assertNotIn('pull_request',condition)
        self.assertIn('group: swcli-assembly-mates-${{ github.ref }}',job)
        self.assertIn('cancel-in-progress: false',job)
        self.assertIn('group: swcli-hosted-windows-solidworks',default)
        self.assertNotIn('assembly_mates_calibration',default)
        self.assertIn('needs: [test, package]',job)
        self.assertIn('digest-mismatch: error',job)
        self.assertIn('pip install --force-reinstall $wheels[0].FullName',job)
        self.assertNotIn('pip install --force-reinstall',default)
        self.assertIn('timeout-minutes: 31',job)
        self.assertIn('run-assembly-mates-calibration.py',job)
        self.assertIn("inputs.assembly_mates_stage != 'public'",job)
        self.assertIn("inputs.assembly_mates_stage == 'public'",job)
        self.assertIn('--mode public',job)
        self.assertNotIn('smoke-solidworks.ps1',job)
        self.assertIn('if: always()',job)
        self.assertIn('${{ runner.temp }}\\swcli-native-smoke',job)
        self.assertIn('cleanup-hosted-solidworks.ps1',job)

    def test_private_calibration_refuses_before_host_when_public_writes_are_open(self):
        calibration=load('verify-assembly-mates-calibration.py')
        with mock.patch.object(calibration,'PUBLIC_MATE_WRITES_CALIBRATED',True), \
             mock.patch.object(calibration,'verify_installed_package') as package:
            with self.assertRaisesRegex(RuntimeError,'private calibration requires closed public writes'):
                calibration.read_official_types(None,None)
            package.assert_not_called()

    def test_catalog_must_be_complete_and_closes_only_known_clean_source_once(self):
        calibration=load('verify-assembly-mates-calibration.py')
        part=NS(GetTitle=lambda:'component',GetPathName=lambda:'source.SLDPRT',GetType=lambda:1,
                GetSaveFlag=lambda:False,GetUpdateStamp=lambda:3)
        app=NS(GetDocumentCount=lambda:1,GetDocuments=lambda:(part,),CloseDoc=mock.Mock())
        call=lambda label,function:function()
        catalog=calibration.document_catalog(app,call,'test')
        self.assertEqual(catalog['count'],1)
        calibration.close_known_source(app,Path('source.SLDPRT'),catalog,call,'close-source')
        app.CloseDoc.assert_called_once_with('component')
        unknown=dict(count=1,documents=[dict(path='unknown.SLDASM',title='unknown',type=2,modified=False)])
        app.CloseDoc.reset_mock()
        with self.assertRaises(RuntimeError):calibration.close_known_source(app,Path('source.SLDPRT'),unknown,call,'refuse')
        app.CloseDoc.assert_not_called()
        with mock.patch.object(part,'GetSaveFlag',lambda:None):
            with self.assertRaises(RuntimeError):calibration.document_catalog(app,call,'unknown-modified')
        for raw,count in ((None,1),(0,0),('bad',0),(None,False)):
            with mock.patch.object(app,'GetDocuments',lambda raw=raw:raw),mock.patch.object(app,'GetDocumentCount',lambda count=count:count):
                with self.assertRaises(RuntimeError):calibration.document_catalog(app,call,'bad')

    def test_external_watchdog_has_fixed_native_and_group_budgets_without_retry(self):
        watchdog=load('run-assembly-mates-calibration.py')
        self.assertEqual(watchdog.NATIVE_SECONDS,600)
        self.assertEqual(watchdog.GROUP_SECONDS,1800)
        self.assertIsNone(watchdog.budget_failure(599,0,0))
        self.assertEqual(watchdog.budget_failure(600,0,0),'native-call-budget-600-seconds')
        self.assertEqual(watchdog.budget_failure(1800,0,None),'group-budget-1800-seconds')
        self.assertIsNone(watchdog.budget_failure(1799,0,1700))
        source=(ROOT/'scripts/ci/run-assembly-mates-calibration.py').read_text()
        self.assertEqual(source.count('subprocess.Popen('),1)
        self.assertNotIn('taskkill',source)
        self.assertIn('TerminateProcess(host_handle,124)',source)
        self.assertIn('watchdog.json',source)
        self.assertIn('stdout.log',source)
        self.assertIn('stderr.log',source)

    def test_failed_host_cleanup_never_touches_success_unknown_or_an_exited_handle(self):
        watchdog=load('run-assembly-mates-calibration.py')
        handle=object();api=NS(TerminateProcess=mock.Mock())
        events=NS(WAIT_OBJECT_0=0,WAIT_TIMEOUT=258,WaitForSingleObject=mock.Mock(return_value=0))
        for selected,code in ((handle,0),(None,1),(handle,1)):
            proof={};watchdog.finish_failed_owned_host(selected,code,api,events,proof)
            self.assertFalse(proof['attempted'])
        api.TerminateProcess.assert_not_called()
        events.WaitForSingleObject.return_value=-1
        with self.assertRaises(RuntimeError):watchdog.finish_failed_owned_host(handle,1,api,events,{})
        api.TerminateProcess.assert_not_called()
        events.WaitForSingleObject.side_effect=[258,0]
        proof={};watchdog.finish_failed_owned_host(handle,1,api,events,proof)
        api.TerminateProcess.assert_called_once_with(handle,1)
        self.assertEqual(proof,dict(attempted=True,exit_confirmed=True))

    def test_failed_host_cleanup_does_not_repeat_termination_on_exit_timeout(self):
        watchdog=load('run-assembly-mates-calibration.py')
        api=NS(TerminateProcess=mock.Mock());handle=object()
        events=NS(WAIT_OBJECT_0=0,WAIT_TIMEOUT=258,WaitForSingleObject=mock.Mock(return_value=258))
        proof={}
        with self.assertRaises(RuntimeError):watchdog.finish_failed_owned_host(handle,1,api,events,proof)
        api.TerminateProcess.assert_called_once_with(handle,1)
        self.assertTrue(proof['attempted'])
        self.assertFalse(proof['exit_confirmed'])

    def test_save_reopen_compares_content_and_uses_new_face_ownership_not_old_session_tokens(self):
        calibration=load('verify-assembly-mates-calibration.py')
        content=dict(title='before',path='old',update_stamp=3,modified=True,configuration='Default',
            components=[dict(name='a',source_update_stamp=1,faces=[dict(index=0,reference_sha256='aaa')]),
                        dict(name='b',source_update_stamp=2,faces=[dict(index=0,reference_sha256='bbb')])],
            mates=[dict(references=['aaa','bbb'],distance_mm=0)])
        expected=calibration.persistent_shape(content)
        reopened=copy.deepcopy(content)
        reopened.update(title='saved',path='saved.SLDASM',update_stamp=8,modified=False)
        reopened['components'][0]['source_update_stamp']=99
        reopened['components'][0]['faces'][0]['reference_sha256']='fresh'
        reopened['mates'][0]['references'][0]='fresh'
        self.assertTrue(calibration.equivalent(calibration.persistent_shape(reopened),expected))
        reopened['mates'][0]['distance_mm']=.001
        self.assertFalse(calibration.equivalent(calibration.persistent_shape(reopened),expected))
        source=(ROOT/'scripts/ci/verify-assembly-mates-calibration.py').read_text()
        self.assertIn('GetDocumentCount',source)
        self.assertIn('read_only=True',source)
        self.assertIn('not-run-production-write-fail-closed',source)
        self.assertIn('pythoncom.LoadTypeLib',source)
        self.assertIn('REQUIRED_MEMBERS',source)
        self.assertIn('part_hash',source)


if __name__=='__main__':unittest.main()


@unittest.skipUnless(shutil.which('git'),'Git commit provenance fixture')
class InstalledPackageIdentityTests(unittest.TestCase):
    def test_exact_commit_bytes_survive_checkout_newline_changes_and_reject_stale_same_version(self):
        spec=importlib.util.spec_from_file_location('_package_identity',ROOT/'scripts/ci/gate_support/package_identity.py')
        identity=importlib.util.module_from_spec(spec);spec.loader.exec_module(identity)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);repo=root/'checkout';source=repo/'src/swcli';source.mkdir(parents=True)
            installed=root/'installed';installed.mkdir();hooks=root/'empty-hooks';hooks.mkdir()
            (source/'__init__.py').write_bytes(b'__version__="same"\n')
            (source/'adapter.py').write_bytes(b'correct_native_code=True\n')
            def git(*args):
                return subprocess.check_output(['git','-c','core.hooksPath='+str(hooks),'-c','commit.gpgsign=false',
                    '-c','user.name=fixture','-c','user.email=fixture@localhost',*args],cwd=repo,stderr=subprocess.DEVNULL)
            git('init','-q');git('-c','core.autocrlf=false','add','src');git('commit','-qm','fixture')
            head=git('rev-parse','HEAD').decode().strip()
            for path in source.glob('*.py'):(installed/path.name).write_bytes(path.read_bytes())
            (source/'adapter.py').write_bytes(b'correct_native_code=True\r\n')
            result=identity.verify_installed_package(repo,installed_root=installed,expected_commit=head)
            self.assertTrue(result['matches_source_commit'])
            self.assertEqual(result['verified_python_files'],2)
            (installed/'adapter.py').write_bytes(b'stale_native_code=True\n')
            with self.assertRaisesRegex(RuntimeError,'source differs'):
                identity.verify_installed_package(repo,installed_root=installed,expected_commit=head)
            with self.assertRaisesRegex(RuntimeError,'HEAD differs'):
                identity.verify_installed_package(repo,installed_root=installed,expected_commit='0'*40)
            with self.assertRaisesRegex(RuntimeError,'editable checkout'):
                identity.verify_installed_package(repo,installed_root=source,expected_commit=head)
