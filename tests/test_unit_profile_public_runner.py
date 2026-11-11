"""Owned public-host lifecycle, no restart and no stop at an unproven endpoint."""
import importlib.util
import itertools
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('public_units_runner_test',ROOT/'scripts/ci/run-unit-profile-public.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class PublicRunnerTests(unittest.TestCase):
    def setup_case(self,*,ready=True,worker_code=0):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=Path(temp.name);fixtures=root/'fixtures';fixtures.mkdir();(fixtures/'report.json').write_text('{"success":true}')
        self.args=SimpleNamespace(fixture_dir=fixtures,output_dir=root/'output')
        self.daemon=SimpleNamespace(pid=321,returncode=None)
        self.daemon.poll=lambda:self.daemon.returncode
        self.daemon.wait=mock.Mock(side_effect=lambda timeout: self.daemon.returncode)
        self.daemon.terminate=mock.Mock(side_effect=lambda:setattr(self.daemon,'returncode',-15))
        def popen(command,**kw):
            if '-m' in command:
                if ready:kw['stdout'].write(b'{"action": "daemon.serve"}\n');kw['stdout'].flush()
                return self.daemon
            cli=self.args.output_dir/'cli';cli.mkdir()
            (cli/'public-unit-profile.json').write_text(json.dumps(dict(host=dict(process_id=123,owned_by_daemon=True,visible=False,shared_interactive=False))))
            return SimpleNamespace(pid=322,returncode=worker_code,poll=lambda:worker_code)
        self.popen=mock.Mock(side_effect=popen)
        def stop(command,**kw):
            self.daemon.returncode=0
            return SimpleNamespace(returncode=0,stdout=b'{"success":true}',stderr=b'')
        self.stop=mock.Mock(side_effect=stop)
        self.status_host=dict(process_id=123,owned_by_daemon=True,visible=False,shared_interactive=False)
        self.status=mock.Mock(side_effect=lambda *a,**k:SimpleNamespace(returncode=0,stdout=json.dumps(dict(success=True,result=dict(host_connected=True,recovery_required=False,host=self.status_host))).encode(),stderr=b''))
        self.run_process=lambda command,**options:(self.status if 'status' in command else self.stop)(command,**options)
        self.native_process=SimpleNamespace(Close=mock.Mock())
        self.capture=mock.Mock(return_value=self.native_process)
        self.native_wait=mock.Mock(side_effect=lambda handle:self.assertEqual(self.stop.call_count,1))
    def invoke(self,clock=None):
        with mock.patch.object(runner,'capture_owned_native_process',self.capture),mock.patch.object(runner,'wait_owned_native_process',self.native_wait),mock.patch.object(runner,'solidworks_process_ids',return_value=getattr(self,'inventory',[])),mock.patch.object(runner.subprocess,'Popen',self.popen),mock.patch.object(runner.subprocess,'run',self.run_process),mock.patch.object(runner.time,'monotonic',side_effect=itertools.chain(clock or [0,1],itertools.repeat((clock or [0,1])[-1]))):
            runner.execute(self.args)
    def test_success_creates_one_daemon_one_worker_and_shutdown_once(self):
        self.setup_case();self.invoke()
        self.assertEqual(self.popen.call_count,2)
        self.stop.assert_called_once()
        self.assertIn('stop',self.stop.call_args.args[0])
        self.assertNotIn('--attach',self.popen.call_args_list[0].args[0])
        self.daemon.terminate.assert_not_called()
    def test_worker_failure_keeps_first_error_stops_owned_daemon_no_restart(self):
        self.setup_case(worker_code=1)
        with self.assertRaisesRegex(RuntimeError,'public CLI acceptance failed'):self.invoke()
        self.assertEqual(self.popen.call_count,2)
        self.stop.assert_called_once()
    def test_startup_timeout_never_sends_shutdown_to_unproven_endpoint(self):
        self.setup_case(ready=False)
        with self.assertRaisesRegex(RuntimeError,'readiness deadline'):self.invoke(clock=[0,181])
        self.assertEqual(self.popen.call_count,1)
        self.stop.assert_not_called()
        self.daemon.terminate.assert_called_once()
    def test_group_budget_boundary(self):
        self.assertFalse(runner.group_expired(0,1800))
        self.assertTrue(runner.group_expired(0,1801))

    def test_native_process_exit_wait_is_once_after_shutdown_and_handle_closed(self):
        self.setup_case();self.invoke()
        self.capture.assert_called_once_with(123)
        self.native_wait.assert_called_once_with(self.native_process)
        self.native_process.Close.assert_called_once()
        report=json.loads((self.args.output_dir/'host-report.json').read_text())
        self.assertTrue(report['owned_native_exit_confirmed'])
    def test_native_exit_timeout_remains_failure_no_api_retry(self):
        self.setup_case();self.native_wait.side_effect=RuntimeError('native exit timeout')
        with self.assertRaisesRegex(RuntimeError,'native exit timeout'):self.invoke()
        self.stop.assert_called_once();self.native_wait.assert_called_once()
        self.native_process.Close.assert_called_once()
    def test_native_capture_failure_still_stops_daemon_once_and_preserves_first_failure(self):
        self.setup_case(worker_code=1);self.capture.side_effect=RuntimeError('capture failed')
        with self.assertRaisesRegex(RuntimeError,'public CLI acceptance failed'):self.invoke()
        self.stop.assert_called_once();self.native_wait.assert_not_called()


class WritePublicEmergencyExitTests(unittest.TestCase):
    setup_case=PublicRunnerTests.setup_case
    def invoke(self,clock=None):
        self.args.write_acceptance=True
        self.identity=dict(pid=123,image=runner.owned_native.EXPECTED_CI_IMAGE,creation_utc='this-run',creation_timestamp=1.0)
        self.verified_capture=mock.Mock(return_value=(self.native_process,self.identity),side_effect=getattr(self,'capture_side_effect',getattr(self,'capture_error',None)))
        self.emergency=mock.Mock();self.is_exited=mock.Mock(return_value=False)
        with mock.patch.object(runner.owned_native,'capture',self.verified_capture),mock.patch.object(runner.owned_native,'terminate',self.emergency),mock.patch.object(runner.owned_native,'exited',self.is_exited):
            return PublicRunnerTests.invoke(self,clock)

    def test_write_normal_exit_retains_identity_without_emergency_or_legacy_capture(self):
        self.setup_case();self.invoke();self.verified_capture.assert_called_once();self.capture.assert_not_called();self.emergency.assert_not_called()
        report=json.loads((self.args.output_dir/'host-report.json').read_text());self.assertTrue(report['native_handle_captured_early']);self.assertEqual(report['owned_native_identity'],self.identity)

    def test_budget_first_error_survives_active_document_and_single_proven_handle_termination(self):
        self.setup_case();original=self.popen.side_effect
        def popen(command,**options):
            result=original(command,**options)
            if '-m' not in command:
                result.returncode=None;result.poll=lambda:result.returncode
                result.kill=mock.Mock(side_effect=lambda:setattr(result,'returncode',-9));result.wait=mock.Mock(return_value=-9)
            return result
        self.popen.side_effect=popen
        self.stop.side_effect=lambda *a,**k:SimpleNamespace(returncode=1,stdout=b'{"success":false,"error":{"code":"ActiveDocument"}}',stderr=b'')
        with self.assertRaisesRegex(RuntimeError,'public group exceeded 1800s'):self.invoke(clock=[0,1,1,1,1,1801,1802])
        self.verified_capture.assert_called_once();self.stop.assert_called_once();self.daemon.terminate.assert_called_once();self.emergency.assert_called_once_with(self.native_process,self.identity);self.native_wait.assert_called_once_with(self.native_process)
        report=json.loads((self.args.output_dir/'host-report.json').read_text());self.assertFalse(report['success']);self.assertTrue(report['forced_native_termination_attempted']);self.assertTrue(report['owned_native_exit_confirmed']);self.assertEqual(report['pids_after'],[]);self.assertEqual(report['failure']['message'],'public group exceeded 1800s');self.assertTrue(report['cleanup_errors'])

    def test_capture_identity_failure_never_terminates_native(self):
        self.setup_case(worker_code=1);self.capture_error=RuntimeError('identity mismatch')
        with self.assertRaisesRegex(RuntimeError,'identity mismatch'):self.invoke()
        self.verified_capture.assert_called_once();self.emergency.assert_not_called();self.stop.assert_called_once();self.native_wait.assert_not_called()
        report=json.loads((self.args.output_dir/'host-report.json').read_text());self.assertFalse(report.get('owned_native_exit_confirmed',False));self.assertFalse(report.get('forced_native_termination_attempted',False))

    def test_unknown_host_ownership_never_opens_or_kills_a_native_handle(self):
        self.setup_case();self.status_host['shared_interactive']=True
        with self.assertRaisesRegex(RuntimeError,'ownership is not proven'):self.invoke()
        self.verified_capture.assert_not_called();self.emergency.assert_not_called();self.stop.assert_called_once();self.assertEqual(self.popen.call_count,1)

    def test_python_termination_error_does_not_replace_budget_first_error(self):
        self.setup_case();original=self.popen.side_effect
        def popen(command,**options):
            result=original(command,**options)
            if '-m' not in command:
                result.returncode=None;result.poll=lambda:result.returncode;result.kill=mock.Mock(side_effect=lambda:setattr(result,'returncode',-9));result.wait=mock.Mock(return_value=-9)
            return result
        self.popen.side_effect=popen
        self.stop.side_effect=lambda *a,**k:SimpleNamespace(returncode=1,stdout=b'{"success":false,"error":{"code":"ActiveDocument"}}',stderr=b'')
        self.daemon.terminate.side_effect=RuntimeError('retained Python exit denied')
        with self.assertRaisesRegex(RuntimeError,'public group exceeded 1800s'):self.invoke(clock=[0,1,1,1,1,1801,1802])
        report=json.loads((self.args.output_dir/'host-report.json').read_text());self.assertEqual(report['failure']['message'],'public group exceeded 1800s');self.assertTrue(any(e.get('message')=='retained Python exit denied' for e in report['cleanup_errors']));self.emergency.assert_called_once_with(self.native_process,self.identity);self.assertFalse(report['success'])

    def test_preexisting_native_pid_is_not_opened_or_terminated(self):
        self.setup_case();self.inventory=[123]
        with self.assertRaisesRegex(RuntimeError,'ownership is not proven'):self.invoke()
        self.verified_capture.assert_not_called();self.emergency.assert_not_called();self.stop.assert_called_once()

    def test_frontend_retained_readonly_handle_is_waited_once_without_termination_rights(self):
        import hashlib
        import sys
        self.setup_case();original=self.popen.side_effect;front=SimpleNamespace(Close=mock.Mock());helper=(ROOT/'scripts/ci/gate_support/unit_cli_worker.py').resolve()
        def popen(command,**options):
            result=original(command,**options)
            if '-m' not in command:
                path=self.args.output_dir/'cli/public-unit-profile.json';value=json.loads(path.read_text());value['cli_frontend']=dict(pid=999,ready=dict(pid=999),helper_path=str(helper),helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),launch_utc_timestamp=1.0,command=[sys.executable,'-I',str(helper)]);path.write_text(json.dumps(value))
                polls=iter([None,0]);result.poll=lambda:next(polls,0)
            return result
        self.popen.side_effect=popen
        self.capture_side_effect=lambda pid,*a,**k:(self.native_process,dict(pid=123)) if pid==123 else (front,dict(pid=999))
        with mock.patch.object(runner.time,'sleep'):self.invoke()
        self.assertEqual(self.verified_capture.call_count,2);self.assertIs(self.verified_capture.call_args_list[1].kwargs['terminate_right'],False);self.assertTrue(callable(self.verified_capture.call_args_list[1].kwargs['observe']))
        self.assertEqual(self.verified_capture.call_args_list[1].args,(999,1.0,sys.executable));self.assertEqual(self.native_wait.call_count,2);self.emergency.assert_not_called();front.Close.assert_called_once()
        report=json.loads((self.args.output_dir/'host-report.json').read_text());self.assertTrue(report['cli_frontend_exit_confirmed_by_wrapper'])


    def test_wrapper_keeps_observation_and_first_error_when_capture_fails(self):
        self.setup_case();self.args.write_acceptance=True
        value=dict(requested_pid=123,expected_image=runner.owned_native.EXPECTED_CI_IMAGE,observed_identity=dict(pid=123,image=r'C:\Other\SLDWORKS.exe',creation_timestamp=1.0),image_query=dict(returned_chars=29,image_length_py_chars=29))
        error=RuntimeError('native full image differs from this CI installation');error.identity_observation=value;error.identity_handle_close_error='close detail'
        def capture(*args,**options):options['observe'](value);raise error
        with mock.patch.object(runner.owned_native,'capture',side_effect=capture),mock.patch.object(runner.owned_native,'terminate') as terminate:
            with self.assertRaisesRegex(RuntimeError,'full image differs'):PublicRunnerTests.invoke(self)
        report=json.loads((self.args.output_dir/'host-report.json').read_text());self.assertEqual(report['failure']['message'],str(error));self.assertEqual(report['identity_observations'][0]['role'],'native-host');self.assertEqual(report['identity_observations'][0]['observed_identity']['image'],value['observed_identity']['image']);self.assertEqual(report['identity_capture_failure']['handle_close_error'],'close detail');terminate.assert_not_called()


    def test_preflight_raw_json_and_identity_are_durable_before_public_starts(self):
        import os
        self.setup_case();original=self.popen.side_effect;events=[];real_fsync=os.fsync
        def fsync(fd):
            for name in ('stdout','stderr'):
                path=self.args.output_dir/('identity-preflight.'+name)
                if path.exists() and os.fstat(fd).st_ino==path.stat().st_ino:events.append(name+'-fsync')
            real_fsync(fd)
        def capture(pid,launched,**options):
            durable=json.loads((self.args.output_dir/'host-report.json').read_bytes())
            self.assertEqual(durable['identity_preflight']['response']['result']['host'],self.status_host)
            self.assertEqual(durable['identity_preflight']['returncode'],0)
            self.assertEqual(events,['stdout-fsync','stderr-fsync'])
            options['observe'](dict(observed_identity=self.identity));events.append('identity-fsync')
            return self.native_process,self.identity
        def popen(command,**options):
            if '-m' not in command:
                self.assertEqual(events,['stdout-fsync','stderr-fsync','identity-fsync'])
                durable=json.loads((self.args.output_dir/'host-report.json').read_bytes())
                self.assertEqual(durable['identity_observations'][0]['observed_identity'],self.identity)
                self.assertEqual(durable['owned_native_identity'],self.identity);events.append('public-popen')
            return original(command,**options)
        self.capture_side_effect=capture;self.popen.side_effect=popen
        with mock.patch.object(runner.os,'fsync',side_effect=fsync):self.invoke()
        self.status.assert_called_once();self.stop.assert_called_once()
        command=self.status.call_args.args[0]
        self.assertEqual(command[-3:],['daemon','status','--json']);self.assertEqual(command[command.index('--request-timeout')+1],'600')
        self.assertEqual(self.status.call_args.kwargs['timeout'],600)
        report=json.loads((self.args.output_dir/'host-report.json').read_bytes());self.assertTrue(report['public_host_matches_preflight'])
        self.assertEqual(events[-1],'public-popen');self.verified_capture.assert_called_once()

    def test_status_raw_fsync_failure_prevents_capture_and_public(self):
        import os
        self.setup_case();real_fsync=os.fsync
        def fsync(fd):
            path=self.args.output_dir/'identity-preflight.stdout'
            if path.exists() and os.fstat(fd).st_ino==path.stat().st_ino:raise OSError('raw status fsync denied')
            real_fsync(fd)
        with mock.patch.object(runner.os,'fsync',side_effect=fsync):
            with self.assertRaisesRegex(OSError,'raw status fsync denied'):self.invoke()
        self.verified_capture.assert_not_called();self.emergency.assert_not_called();self.stop.assert_called_once();self.assertEqual(self.popen.call_count,1)

    def test_parsed_status_fsync_failure_prevents_capture_and_public(self):
        self.setup_case();original=runner.evidence.durable;failed=False
        def durable(path,value):
            nonlocal failed
            if path.name=='host-report.json' and 'response' in value.get('identity_preflight',{}) and not failed:
                failed=True;raise OSError('parsed status fsync denied')
            return original(path,value)
        with mock.patch.object(runner.evidence,'durable',side_effect=durable):
            with self.assertRaisesRegex(OSError,'parsed status fsync denied'):self.invoke()
        self.assertTrue(failed);self.verified_capture.assert_not_called();self.emergency.assert_not_called();self.stop.assert_called_once();self.assertEqual(self.popen.call_count,1)

    def test_identity_observation_fsync_failure_does_not_start_public(self):
        self.setup_case();original=runner.evidence.durable;failed=False
        def durable(path,value):
            nonlocal failed
            if path.name=='host-report.json' and value.get('identity_observations') and not failed:
                failed=True;raise OSError('identity observation fsync denied')
            return original(path,value)
        def capture(pid,launched,**options):
            options['observe'](dict(observed_identity=self.identity))
            self.fail('capture must not return after observation fsync error')
        self.capture_side_effect=capture
        with mock.patch.object(runner.evidence,'durable',side_effect=durable):
            with self.assertRaisesRegex(OSError,'identity observation fsync denied'):self.invoke()
        self.assertEqual(self.popen.call_count,1);self.stop.assert_called_once();self.emergency.assert_not_called();self.native_wait.assert_not_called()

    def test_bad_status_keeps_raw_and_never_captures_or_starts_public(self):
        for raw,code in ((b'not JSON\r\n',0),(b'{"success":false,"error":{"code":"Disconnected"}}\r\n',1)):
            with self.subTest(raw=raw):
                self.setup_case();self.status.side_effect=None;self.status.return_value=SimpleNamespace(returncode=code,stdout=raw,stderr=b'raw stderr\r\n')
                with self.assertRaises((json.JSONDecodeError,RuntimeError)):self.invoke()
                self.assertEqual((self.args.output_dir/'identity-preflight.stdout').read_bytes(),raw)
                self.assertEqual((self.args.output_dir/'identity-preflight.stderr').read_bytes(),b'raw stderr\r\n')
                self.verified_capture.assert_not_called();self.emergency.assert_not_called();self.stop.assert_called_once();self.assertEqual(self.popen.call_count,1)

    def test_disconnected_or_recovery_status_never_captures_or_starts_public(self):
        for state in (dict(host_connected=False,recovery_required=False),dict(host_connected=True,recovery_required=True)):
            with self.subTest(state=state):
                self.setup_case();self.status.side_effect=None;self.status.return_value=SimpleNamespace(returncode=0,stdout=json.dumps(dict(success=True,result=dict(host=self.status_host,**state))).encode(),stderr=b'')
                with self.assertRaisesRegex(RuntimeError,'already connected, unreplaced'):self.invoke()
                self.verified_capture.assert_not_called();self.stop.assert_called_once();self.assertEqual(self.popen.call_count,1)

    def test_status_timeout_preserves_partial_bytes_and_never_starts_public(self):
        self.setup_case();self.status.side_effect=runner.subprocess.TimeoutExpired(['daemon','status'],600,output=b'partial response',stderr=b'partial stderr')
        with self.assertRaises(runner.subprocess.TimeoutExpired):self.invoke()
        self.assertEqual((self.args.output_dir/'identity-preflight.stdout').read_bytes(),b'partial response')
        self.assertEqual((self.args.output_dir/'identity-preflight.stderr').read_bytes(),b'partial stderr')
        report=json.loads((self.args.output_dir/'host-report.json').read_bytes());self.assertTrue(report['identity_preflight']['outcome_unknown']);self.assertIsNone(report['identity_preflight']['returncode'])
        self.verified_capture.assert_not_called();self.emergency.assert_not_called();self.stop.assert_called_once();self.assertEqual(self.popen.call_count,1)

    def test_preflight_uses_remaining_original_group_budget_without_reset(self):
        self.setup_case();self.invoke(clock=[0,1,1500,1501,1502,1503,1504])
        self.assertEqual(self.status.call_args.kwargs['timeout'],300)
        report=json.loads((self.args.output_dir/'host-report.json').read_bytes());self.assertEqual(report['duration_seconds'],1504)
        self.assertEqual(report['identity_preflight']['requested_cli_timeout_seconds'],600)

    def test_real_cli_status_route_uses_fixed_health_timeout_despite_requested_600(self):
        import contextlib,io
        from importlib import import_module
        from swcli.cli import main
        self.setup_case();self.invoke()
        command=self.status.call_args.args[0]
        report=json.loads((self.args.output_dir/'host-report.json').read_bytes())['identity_preflight']
        self.assertNotIn('request_timeout_seconds',report)
        self.assertEqual(report['requested_cli_timeout_seconds'],600)
        self.assertEqual(report['process_timeout_seconds'],600)
        self.assertIn('swcli.daemon.main.run',report['health_rpc_timeout_contract'])
        response=dict(success=True,result=dict(host_connected=True,recovery_required=False,host=self.status_host))
        daemon=import_module('swcli.daemon.main');stdout=io.StringIO()
        with mock.patch.object(daemon,'call_daemon',return_value=response) as rpc,contextlib.redirect_stdout(stdout):
            code=main(command[4:])
        self.assertEqual(code,0);self.assertEqual(json.loads(stdout.getvalue()),response)
        rpc.assert_called_once_with('daemon.health',endpoint=command[command.index('--endpoint')+1],timeout_seconds=10.0,connect_timeout_seconds=1.0)
        self.assertEqual(report['effective_health_rpc_timeout_seconds'],rpc.call_args.kwargs['timeout_seconds'])
        self.assertEqual(report['effective_health_connect_timeout_seconds'],rpc.call_args.kwargs['connect_timeout_seconds'])

    def test_preflight_budget_exceeded_stops_before_capture_and_public(self):
        self.setup_case()
        with self.assertRaisesRegex(RuntimeError,'public group exceeded 1800s'):self.invoke(clock=[0,1,1,1801,1802])
        self.status.assert_called_once();self.verified_capture.assert_not_called();self.emergency.assert_not_called();self.stop.assert_called_once();self.assertEqual(self.popen.call_count,1)

    def test_public_pid_or_owner_drift_is_rejected_without_reopening_handle(self):
        for change in (dict(process_id=124),dict(owned_by_daemon=False),dict(visible=True),dict(shared_interactive=True)):
            with self.subTest(change=change):
                self.setup_case();original=self.popen.side_effect
                def popen(command,**options):
                    result=original(command,**options)
                    if '-m' not in command:
                        path=self.args.output_dir/'cli/public-unit-profile.json';value=json.loads(path.read_bytes());value['host'].update(change);path.write_text(json.dumps(value))
                    return result
                self.popen.side_effect=popen
                with self.assertRaisesRegex(RuntimeError,'ownership is not proven|differs from the retained'):self.invoke()
                self.verified_capture.assert_called_once();self.stop.assert_called_once();self.emergency.assert_not_called()

    def test_public_host_is_rechecked_after_an_initial_matching_report(self):
        self.setup_case();original=self.popen.side_effect
        def popen(command,**options):
            result=original(command,**options)
            if '-m' not in command:
                polls=iter([None,None,0])
                result.poll=lambda:next(polls,0)
                result.kill=mock.Mock();result.wait=mock.Mock(return_value=0)
            return result
        def drift(*_):
            path=self.args.output_dir/'cli/public-unit-profile.json';value=json.loads(path.read_bytes());value['host']['process_id']=124;path.write_text(json.dumps(value))
        self.popen.side_effect=popen
        with mock.patch.object(runner.time,'sleep',side_effect=drift):
            with self.assertRaisesRegex(RuntimeError,'differs from the retained'):self.invoke()
        self.verified_capture.assert_called_once();self.stop.assert_called_once()
        report=json.loads((self.args.output_dir/'host-report.json').read_bytes());self.assertTrue(report['public_host_matches_preflight']);self.assertFalse(report['success'])

    def test_status_timeout_remains_first_when_partial_evidence_fails(self):
        self.setup_case();original=runner.evidence.durable
        self.status.side_effect=runner.subprocess.TimeoutExpired(['daemon','status'],600,output=b'partial')
        def durable(path,value):
            if path.name=='host-report.json' and value.get('identity_preflight',{}).get('outcome_unknown'):raise OSError('timeout evidence unavailable')
            return original(path,value)
        with mock.patch.object(runner.evidence,'durable',side_effect=durable):
            with self.assertRaises(runner.subprocess.TimeoutExpired):self.invoke()
        self.verified_capture.assert_not_called();self.emergency.assert_not_called();self.stop.assert_called_once();self.assertEqual(self.popen.call_count,1)

    def test_identity_capture_time_is_included_before_public_start(self):
        self.setup_case()
        with self.assertRaisesRegex(RuntimeError,'public group exceeded 1800s'):self.invoke(clock=[0,1,1,2,1801,1802])
        self.verified_capture.assert_called_once();self.stop.assert_called_once();self.assertEqual(self.popen.call_count,1)

    def test_missing_public_ownership_report_is_not_skipped_after_preflight(self):
        self.setup_case();original=self.popen.side_effect
        def popen(command,**options):
            result=original(command,**options)
            if '-m' not in command:(self.args.output_dir/'cli/public-unit-profile.json').unlink()
            return result
        self.popen.side_effect=popen
        with self.assertRaisesRegex(RuntimeError,'native ownership report unavailable'):self.invoke()
        self.verified_capture.assert_called_once();self.stop.assert_called_once();self.emergency.assert_not_called()

    def test_preflight_identity_first_error_survives_stop_failure_without_native_kill(self):
        self.setup_case();self.capture_error=RuntimeError('identity mismatch before public')
        self.stop.side_effect=lambda *a,**k:SimpleNamespace(returncode=1,stdout=b'{"success":false}',stderr=b'stop denied')
        with self.assertRaisesRegex(RuntimeError,'identity mismatch before public'):self.invoke()
        self.assertEqual(self.popen.call_count,1);self.stop.assert_called_once();self.emergency.assert_not_called();self.native_wait.assert_not_called();self.capture.assert_not_called()
        report=json.loads((self.args.output_dir/'host-report.json').read_bytes());self.assertEqual(report['failure']['message'],'identity mismatch before public');self.assertTrue(any(e['message']=='owned daemon shutdown failed' for e in report['cleanup_errors']));self.assertFalse(report.get('owned_native_exit_confirmed',False))


class NativeIdentityTests(unittest.TestCase):
    def setUp(self):
        self.native=runner.owned_native;self.handle=SimpleNamespace(Close=mock.Mock())
        self.api=SimpleNamespace(OpenProcess=mock.Mock(return_value=self.handle),TerminateProcess=mock.Mock())
        self.constants=SimpleNamespace(SYNCHRONIZE=0x100000,PROCESS_TERMINATE=1)
        self.identity=dict(pid=123,image=self.native.EXPECTED_CI_IMAGE,creation_timestamp=200.0,creation_utc='identity')

    def capture(self,identity):
        with mock.patch.dict('sys.modules',win32api=self.api,win32con=self.constants),mock.patch.object(self.native,'process_identity',return_value=identity):
            return self.native.capture(123,100.0)

    def test_full_path_case_identity_validates_and_retains_exact_handle(self):
        handle,identity=self.capture(self.identity);self.assertIs(handle,self.handle);self.assertEqual(identity,self.identity);self.handle.Close.assert_not_called()

    def test_wrong_pid_old_or_future_creation_and_other_installation_close_without_kill(self):
        for change in (dict(pid=999),dict(creation_timestamp=99.0),dict(creation_timestamp=float('inf')),dict(image=r'C:\Other\SLDWORKS.exe')):
            self.handle.Close.reset_mock()
            with self.subTest(change=change),self.assertRaises(RuntimeError):self.capture({**self.identity,**change})
            self.handle.Close.assert_called_once();self.api.TerminateProcess.assert_not_called()

    def test_termination_rechecks_same_handle_identity_and_never_reopens_pid(self):
        with mock.patch.dict('sys.modules',win32api=self.api),mock.patch.object(self.native,'process_identity',return_value=self.identity):self.native.terminate(self.handle,self.identity)
        self.api.TerminateProcess.assert_called_once_with(self.handle,1);self.api.OpenProcess.assert_not_called()
        self.api.TerminateProcess.reset_mock()
        with mock.patch.dict('sys.modules',win32api=self.api),mock.patch.object(self.native,'process_identity',return_value={**self.identity,'creation_timestamp':201}):
            with self.assertRaisesRegex(RuntimeError,'identity changed'):self.native.terminate(self.handle,self.identity)
        self.api.TerminateProcess.assert_not_called()

    def test_frontend_handle_can_only_request_query_and_wait_rights(self):
        import sys
        with mock.patch.dict('sys.modules',win32api=self.api,win32con=self.constants),mock.patch.object(self.native,'process_identity',return_value={**self.identity,'image':sys.executable}):
            self.native.capture(123,100.0,sys.executable,terminate_right=False)
        self.assertEqual(self.api.OpenProcess.call_args.args[0]&self.constants.PROCESS_TERMINATE,0)

    def test_windows_identity_queries_pid_full_image_and_creation_on_the_same_handle(self):
        import ctypes
        from datetime import datetime,timezone
        query=mock.Mock(side_effect=lambda handle,flags,buffer,size:(setattr(buffer,'value',self.native.EXPECTED_CI_IMAGE) or True))
        kernel=SimpleNamespace(QueryFullProcessImageNameW=query)
        process=SimpleNamespace(GetProcessId=mock.Mock(return_value=123),GetProcessTimes=mock.Mock(return_value=dict(CreationTime=datetime(2026,11,10,tzinfo=timezone.utc))))
        with mock.patch.dict('sys.modules',win32process=process),mock.patch.object(ctypes,'WinDLL',return_value=kernel,create=True):identity=self.native.process_identity(4321)
        self.assertEqual(identity['pid'],123);self.assertEqual(identity['image'],self.native.EXPECTED_CI_IMAGE);self.assertEqual(query.call_args.args[:2],(4321,0));process.GetProcessId.assert_called_once_with(4321);process.GetProcessTimes.assert_called_once_with(4321)

    def test_observation_is_fsynced_before_exact_path_validation_and_no_handle_is_exposed(self):
        bad={**self.identity,'image':r'C:\Other\SLDWORKS.exe'}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'observation.json'
            def observe(value):
                self.assertNotIn('handle',value);self.assertNotIn('handle',value.get('image_query',{}))
                # JSON serialization rejects any accidental PyHANDLE capability.
                with path.open('w') as stream:
                    stream.write(json.dumps(value));stream.flush()
                    import os
                    os.fsync(stream.fileno())
            original=self.native.validate_identity
            def validate(*args):
                self.assertTrue(path.is_file());saved=json.loads(path.read_text());self.assertEqual(saved['observed_identity'],bad);self.assertEqual(saved['expected_image'],self.native.EXPECTED_CI_IMAGE);return original(*args)
            with mock.patch.dict('sys.modules',win32api=self.api,win32con=self.constants),mock.patch.object(self.native,'process_identity',return_value=bad),mock.patch.object(self.native,'validate_identity',side_effect=validate):
                with self.assertRaisesRegex(RuntimeError,'full image differs'):self.native.capture(123,100,observe=observe)
        self.handle.Close.assert_called_once();self.api.TerminateProcess.assert_not_called()

    def test_observation_write_failure_stops_before_validation_and_preserves_first_error(self):
        observe=mock.Mock(side_effect=OSError('observation fsync failed'))
        with mock.patch.dict('sys.modules',win32api=self.api,win32con=self.constants),mock.patch.object(self.native,'process_identity',return_value=self.identity),mock.patch.object(self.native,'validate_identity') as validate:
            with self.assertRaisesRegex(OSError,'observation fsync failed') as caught:self.native.capture(123,100,observe=observe)
        self.assertEqual(caught.exception.identity_observation['capture_status']['phase'],'persisting');validate.assert_not_called();observe.assert_called_once();self.handle.Close.assert_called_once();self.api.TerminateProcess.assert_not_called()

    def test_observer_cannot_mutate_identity_to_admit_another_image(self):
        bad={**self.identity,'image':r'C:\Other\SLDWORKS.exe'}
        def observe(value):value['observed_identity']['image']=self.native.EXPECTED_CI_IMAGE
        with mock.patch.dict('sys.modules',win32api=self.api,win32con=self.constants),mock.patch.object(self.native,'process_identity',return_value=bad):
            with self.assertRaisesRegex(RuntimeError,'full image differs'):self.native.capture(123,100,observe=observe)
        self.assertEqual(bad['image'],r'C:\Other\SLDWORKS.exe');self.handle.Close.assert_called_once();self.api.TerminateProcess.assert_not_called()

    def test_validation_error_remains_first_if_failed_handle_close_also_fails(self):
        self.handle.Close.side_effect=RuntimeError('handle close failed');bad={**self.identity,'image':r'C:\Other\SLDWORKS.exe'}
        with mock.patch.dict('sys.modules',win32api=self.api,win32con=self.constants),mock.patch.object(self.native,'process_identity',return_value=bad):
            with self.assertRaisesRegex(RuntimeError,'full image differs') as caught:self.native.capture(123,100,observe=mock.Mock())
        self.assertEqual(caught.exception.identity_handle_close_error,'handle close failed');self.api.TerminateProcess.assert_not_called()

    def test_query_observation_keeps_actual_size_raw_buffer_and_stable_identity_separate(self):
        import ctypes,base64
        from datetime import datetime,timezone
        image=self.native.EXPECTED_CI_IMAGE
        def query(handle,flags,buffer,size):buffer.value=image;size._obj.value=len(image);return True
        kernel=SimpleNamespace(QueryFullProcessImageNameW=mock.Mock(side_effect=query))
        process=SimpleNamespace(GetProcessId=mock.Mock(return_value=123),GetProcessTimes=mock.Mock(return_value=dict(CreationTime=datetime(2026,11,11,tzinfo=timezone.utc))))
        observation={}
        with mock.patch.dict('sys.modules',win32process=process),mock.patch.object(ctypes,'WinDLL',return_value=kernel,create=True):identity=self.native.process_identity(4321,observation=observation)
        self.assertEqual(set(identity),{'pid','image','creation_utc','creation_timestamp'})
        data=observation['image_query'];self.assertEqual(data['image'],image);self.assertEqual(data['returned_chars'],len(image));self.assertEqual(data['input_capacity_chars'],32768);self.assertTrue(data['nul_at_returned_index']);self.assertEqual(data['argtypes'],['HANDLE','DWORD','LPWSTR','PDWORD'])
        self.assertEqual(len(base64.b64decode(data['buffer_prefix_b64'],validate=True)),(len(image)+1)*ctypes.sizeof(ctypes.c_wchar));kernel.QueryFullProcessImageNameW.assert_called_once()

    @unittest.skipUnless(__import__('sys').platform=='win32','read-only actual Windows current-process API')
    def test_windows_current_process_query_has_complete_image_without_assuming_venv_entry_is_image(self):
        import ctypes,json,os,sys
        from ctypes import wintypes
        import win32api
        observation={};probe=dict(sys_executable=sys.executable,sys_base_executable=getattr(sys,'_base_executable',None))
        try:
            identity=self.native.process_identity(win32api.GetCurrentProcess(),observation=observation);probe['identity']=identity
            kernel=ctypes.WinDLL('kernel32',use_last_error=True);module=kernel.GetModuleFileNameW;module.argtypes=[wintypes.HMODULE,wintypes.LPWSTR,wintypes.DWORD];module.restype=wintypes.DWORD
            buffer=ctypes.create_unicode_buffer(32768);length=module(None,buffer,len(buffer));probe.update(module_image=buffer.value,module_returned_chars=length,module_last_error=None if length else ctypes.get_last_error())
        finally:
            # Even an API/comparison failure must leave the actual raw observation.
            print('units.current-process-image-observation '+json.dumps(dict(**probe,query=observation.get('image_query')),ensure_ascii=True))
        self.assertTrue(0<length<len(buffer));self.assertEqual(identity['pid'],os.getpid());self.assertTrue(os.path.samefile(identity['image'],buffer.value))
        query=observation['image_query'];self.assertEqual(query['ctypes_bytes']['DWORD'],4);self.assertEqual(query['ctypes_bytes']['BOOL'],4);self.assertEqual(query['ctypes_bytes']['wchar'],2);self.assertEqual(query['returned_chars'],len(identity['image'].encode('utf-16-le'))//2);self.assertTrue(query['nul_at_returned_index'])
        # sys.executable may be a venv redirector: it is recorded, never used as
        # a self-observer equality predicate or to weaken native SLDWORKS checks.
