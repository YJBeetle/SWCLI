"""Offline direction harness/route controls; never a native execution."""
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts/ci"))
from gate_support import revolve_direction as protocol


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


entry=load("direction_entry_offline",ROOT/"scripts/ci/verify-revolve-partial-next.py")
route=load("direction_route_offline",ROOT/"scripts/ci/validate-native-profile.py")


class FakeBackend:
    def __init__(self):
        self.calls=[];self.fault=None;self.cleanup_errors=[]
        self.points=[(0,-5,0),(0,15,0)]
    def start(self):self.calls.append("start");return dict(revision="33.5.0")
    def fixture(self,case):self.calls.append("fixture");return dict(configuration="Default")
    def definition(self):
        return dict(angle_rad=math.radians(self.case["angle_deg"]),reverse=False,kind=0,boss=True,thin=False,merge=True,
            axis_type=10,contour_count=0,axis_matches=True,axis_points_mm=deepcopy(self.points),cleanup_errors=[])
    def create(self,case):
        self.calls.append("create")
        self.case = deepcopy(case)
        frame = list(protocol.PLANES[case["plane"]])
        metrics=protocol.sector_expectation(case["bounds_mm"],frame,case["angle_deg"],rotation_sign=case["rotation_sign"])
        self.creation=dict(ok=True,angle_deg=case["angle_deg"],axis_mm=case["axis_mm"],expected_profile_mm=case["bounds_mm"],
            mutation=dict(attempted=True,creation_returned=True,may_have_changed=True),
            candidate=dict(rotation_sign=-1,axis_direction=1,axis_points_mm=deepcopy(self.points)),
            feature=dict(name="Revolve",type="Revolution"),definition=self.definition(),
            model_to_sketch_transform=frame,expected_metrics=deepcopy(metrics),metrics=metrics,
            verified=True,diagnostics=dict(healthy=True,truncated=False),cleanup_errors=[])
        if self.fault:self.fault(self.creation)
        return self.creation,True
    def save(self,case,*,filename=None):self.calls.append("save");return dict(save=dict(ok=True),file_size_bytes=42,file_sha256="abc",path="fake.SLDPRT")
    def close(self):self.calls.append("close")
    def reopen(self,saved,creation,case,observed):
        self.calls.append("reopen")
        observed.update(reopen=dict(ok=True,api_errors=0,api_warnings=0),feature_count=1,profile_count=1,body_count=1,
            bounds_mm=case["bounds_mm"][:],axis_points_mm=deepcopy(self.points),model_to_sketch_transform=list(protocol.PLANES[case["plane"]]),
            definition=self.definition(),measurement=dict(ok=True,metrics=deepcopy(creation["metrics"])),
            diagnostics=dict(healthy=True,truncated=False),file_sha256="abc",
            state=dict(read_only=True,modified=False,editing=False,selected=0,foreground_same=1,
                       configurations=["Default"],active_configuration="Default"))
    def cleanup(self):self.calls.append("cleanup");return self.cleanup_errors


class DirectionProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.output=Path(self.temp.name);self.backend=FakeBackend();self.evidence=protocol.Evidence(self.output)
    def run_case(self):return protocol.run_direction(self.backend,self.evidence,"a"*40)
    def test_one_preregistered_case_saves_reopens_and_cleans_before_success(self):
        report=self.run_case()
        self.assertTrue(report["success"],report)
        self.assertEqual(self.backend.calls,["start","fixture","create","save","close","reopen","close","cleanup"])
        self.assertEqual(report["case"],protocol.CASE)
        self.assertFalse(report["public_acceptance"])
        self.assertFalse(report["matrix_enabled"])
        self.assertTrue(report["owned_cleanup_completed"])
        events=[json.loads(line) for line in (self.output/"boundaries.jsonl").read_text().splitlines()]
        self.assertEqual(sum(e["call"]=="create-once" and e["phase"]=="begin" for e in events),1)
        self.assertEqual(json.loads((self.output/"report.json").read_text())["reopened"]["file_sha256"],"abc")
    def test_wrong_signed_centroid_stops_before_save_without_second_hypothesis(self):
        self.backend.fault=lambda r:r["metrics"]["centroid_mm"].update(z=-r["metrics"]["centroid_mm"]["z"])
        report=self.run_case()
        self.assertFalse(report["success"])
        self.assertIn("analytic sector",report["failure"]["message"])
        self.assertTrue(report["feature_handle_retained"])
        self.assertNotIn("save",self.backend.calls)
        self.assertEqual(self.backend.calls.count("create"),1)
    def test_native_first_error_and_partial_receipt_survive_cleanup_failure(self):
        def fail(result):result.update(ok=False,error=dict(type="FirstNativeFailure",message="original native observation"))
        self.backend.fault=fail;self.backend.cleanup_errors=[dict(stage="ExitApp",error="secondary cleanup")]
        report=self.run_case()
        self.assertEqual(report["failure"]["type"],"FirstNativeFailure")
        self.assertEqual(report["failure"]["message"],"original native observation")
        self.assertEqual(report["cleanup_errors"][0]["error"],"secondary cleanup")
        self.assertTrue(all(report["creation"]["mutation"].values()))
        self.assertTrue(report["feature_handle_retained"])
        self.assertEqual(self.backend.calls.count("create"),1)
    def test_reopen_actual_is_checkpointed_before_metrics_assertion(self):
        original=self.backend.reopen
        def corrupt(*args):
            original(*args);args[-1]["measurement"]["metrics"]["volume_mm3"]+=1
        self.backend.reopen=corrupt
        report=self.run_case();disk=json.loads((self.output/"report.json").read_text())
        self.assertFalse(report["success"])
        self.assertEqual(disk["reopened"]["measurement"]["metrics"]["volume_mm3"],500*math.pi+1)
        self.assertEqual(self.backend.calls.count("create"),1)
    def test_failed_reopen_measurement_preserves_native_error_without_metrics(self):
        reopen = self.backend.reopen
        failed = dict(ok=False, error=dict(type="MeasurementUnavailable", message="native mass properties missing"))

        def fail(*args):
            reopen(*args)
            args[-1]["measurement"] = failed

        self.backend.reopen = fail
        self.backend.cleanup_errors = [dict(stage="ExitApp", error="secondary cleanup failure")]
        self.run_case()
        disk = json.loads((self.output / "report.json").read_text())
        self.assertFalse(disk["success"])
        self.assertEqual(disk["reopened"]["measurement"], failed)
        self.assertEqual(disk["failure"]["type"], "MeasurementUnavailable")
        self.assertEqual(disk["failure"]["message"], "native mass properties missing")
        self.assertEqual(disk["cleanup_errors"][0]["stage"], "ExitApp")

    def test_definition_angle_axis_and_state_drift_each_fail_closed(self):
        original=self.backend.reopen
        mutations=(lambda r:r["definition"].update(angle_rad=math.pi),
                   lambda r:r["axis_points_mm"].reverse(),
                   lambda r:r["state"].update(modified=True),
                   lambda r:r.update(file_sha256="changed"))
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                def corrupt(*args):original(*args);mutate(args[-1])
                self.backend.reopen=corrupt
                report=self.run_case()
                self.assertFalse(report["success"])
    def test_initial_fsync_failure_prevents_host_acquisition(self):
        with mock.patch.object(protocol.os,"fsync",side_effect=OSError("disk unavailable")):
            report=self.run_case()
        self.assertFalse(report["success"])
        self.assertNotIn("start",self.backend.calls)
        self.assertEqual(self.backend.calls,["cleanup"])
        self.assertEqual(report["failure"]["message"],"disk unavailable")
    def test_end_boundary_disk_failure_retains_actual_creation_and_still_cleans_once(self):
        original=self.evidence.event
        def fail_end(value):
            if value["call"]=="create-once" and value["phase"]=="end":raise OSError("end record failure")
            return original(value)
        self.evidence.event=fail_end
        report=self.run_case()
        self.assertEqual(report["failure"]["message"],"end record failure")
        self.assertTrue(report["creation"]["ok"])
        self.assertTrue(report["feature_handle_retained"])
        self.assertNotIn("save",self.backend.calls)
        self.assertEqual(self.backend.calls.count("cleanup"),1)
    def test_cleanup_is_attempted_even_when_boundary_disk_is_unavailable(self):
        self.evidence.event=mock.Mock(side_effect=OSError("trace disk failure"))
        report=self.run_case()
        self.assertEqual(self.backend.calls,["cleanup"])
        self.assertTrue(report["evidence_errors"])
        self.assertFalse(report["success"])
    def test_native_watchdog_has_600_seconds_and_durable_timeout_without_api_retry(self):
        with mock.patch.object(protocol.threading,"Timer") as timer, mock.patch.object(protocol.os,"_exit") as stop:
            self.evidence.call("fake-native",lambda:7)
            self.assertEqual(timer.call_args.args[0],600)
            timer.call_args.args[1]()
            stop.assert_called_once_with(124)
            self.assertEqual(json.loads((self.output/"native-timeout.json").read_text())["seconds"],600)


class DirectionMatrixTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.output = Path(temp.name)
        self.evidence = protocol.Evidence(self.output)
        self.backend = FakeBackend()

    def run_plane(self, plane):
        return protocol.run_direction(self.backend, self.evidence, "a" * 40, matrix_plane=plane)

    def test_preregisters_all_four_before_host_and_uses_one_host(self):
        start = self.backend.start

        def preregistered_start():
            dry_report = json.loads((self.output / "report.json").read_text())
            self.assertEqual([c["angle_deg"] for c in dry_report["planned_cases"]], [90,45,180,270])
            self.assertEqual(dry_report["cases"], [])
            return start()

        self.backend.start = preregistered_start
        report = self.run_plane("top")
        self.assertTrue(report["success"], report.get("failure"))
        self.assertFalse(report["public_acceptance"])
        self.assertEqual(report["public_write_gate"], "closed")
        self.assertEqual(self.backend.calls.count("start"), 1)
        self.assertEqual(self.backend.calls.count("create"), 4)
        self.assertEqual(self.backend.calls.count("close"), 8)
        self.assertEqual(self.backend.calls.count("cleanup"), 1)
        centroid = report["cases"][0]["creation"]["metrics"]["centroid_mm"]
        self.assertAlmostEqual(centroid["x"], 40/(3*math.pi))
        self.assertAlmostEqual(centroid["y"], -40/(3*math.pi))
        self.assertAlmostEqual(centroid["z"], -5)

    def test_first_case_with_wrong_plane_stops_before_next_fixture(self):
        self.backend.fault = lambda result: result.update(model_to_sketch_transform=protocol.IDENTITY)
        report = self.run_plane("right")
        self.assertFalse(report["success"])
        self.assertEqual(report["failed_case"], "right-direction-90")
        self.assertIn("frame differs", report["failure"]["message"])
        self.assertEqual(len(report["planned_cases"]), 4)
        self.assertEqual(len(report["cases"]), 1)
        self.assertEqual(self.backend.calls, ["start","fixture","create","cleanup"])

    def test_matrix_host_success_requires_all_four_exact_cases(self):
        report = self.run_plane("front")
        child = mock.Mock()
        child.wait.return_value = 0
        with mock.patch.object(entry.subprocess, "Popen", return_value=child):
            self.assertEqual(entry.supervise(["fake"], self.output, matrix_plane="front"), 0)
            report["cases"].pop()
            protocol.durable(self.output / "report.json", report)
            with self.assertRaisesRegex(RuntimeError, "all scheduled"):
                entry.supervise(["fake"], self.output, matrix_plane="front")

    def test_ci_entry_rejects_matrix_argument_before_route_or_host(self):
        with mock.patch.object(entry, "exact_source") as proof:
            with self.assertRaises(SystemExit), mock.patch.object(sys, "stderr"):
                entry.main(["--matrix-plane", "top", "--output-dir", "evidence", "--expected-head", "a"*40])
        proof.assert_not_called()


class DirectionControlTests(unittest.TestCase):
    class Backend(FakeBackend):
        def prepare_refusal(self, name, case, receipt):
            self.control = name
            receipt.update(self.fixture(case))

        def save(self, case, *, filename=None):
            saved = super().save(case, filename=filename)
            saved['save'].update(save_attempted=True, api_saved=True, save_errors=0, save_warnings=0)
            return saved

        def snapshot(self):
            return dict(foreground_same=True, editing=False, selected=0, stamp=4,
                        read_only=self.control == 'private-read-only',
                        body_count=1 if self.control == 'private-existing-solid' else 0)

        def refusal(self, name, case, row):
            from gate_support import revolve_controls as controls
            row.update(receipt=dict(ok=False, error=dict(type=dict(controls.REFUSALS)[name]),
                                    mutation=dict(controls.ZERO_MUTATION)),
                       feature_handle_retained=False,
                       dispatcher_exception=name in ('public-stale-stamp','public-wrong-lease','public-missing-sketch'))

        def create_partial(self, case, row):
            from gate_support import revolve_controls as controls
            created, retained = self.create(case)
            created.update(ok=False, error=dict(type='RuntimeError', message=controls.INJECTED_MESSAGE))
            row.update(creation=created, feature_handle_retained=retained)

        def preserved_partial(self):
            return dict(exact_handle_matches=True, body_count=1, diagnostics=dict(healthy=True, truncated=False),
                        measurement=dict(ok=True, metrics=self.creation['metrics']))

    def setUp(self):
        from gate_support import revolve_controls as controls
        self.controls = controls
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name)
        self.backend = self.Backend()

    def run_controls(self):
        return self.controls.run_controls(self.backend, protocol.Evidence(self.path), 'a'*40)

    def test_ordered_refusals_and_one_partial_save_reopen(self):
        report = self.run_controls()
        self.assertTrue(report['success'], report.get('failure'))
        self.assertEqual([row['name'] for row in report['controls']], self.controls.control_plan())
        self.assertEqual(self.backend.calls.count('create'), 1)
        self.assertEqual(self.backend.calls.count('reopen'), 1)
        self.assertEqual(self.backend.calls.count('cleanup'), 1)
        self.assertFalse(report['public_acceptance'])
        self.assertEqual(report['controls'][-1]['creation']['mutation'], self.controls.PARTIAL_MUTATION)

    def test_state_mutation_on_refusal_stops_before_later_fixtures(self):
        before = dict(foreground_same=True, editing=False, selected=0, read_only=False, body_count=0, stamp=4)
        self.backend.snapshot = mock.Mock(side_effect=[before, dict(before, stamp=5)])
        report = self.run_controls()
        self.assertEqual(report['failed_control'], 'public-closed-angle')
        self.assertIn('changed live document', report['failure']['message'])
        self.assertEqual(self.backend.calls, ['start', 'fixture', 'cleanup'])
        raw = json.loads((self.path/'report.json').read_text())
        self.assertEqual(raw['controls'][0]['after']['stamp'], 5)

    def test_save_warning_is_preserved_and_stops_before_reopen(self):
        save = self.backend.save

        def warned(*args, **kwargs):
            saved = save(*args, **kwargs)
            saved['save']['save_warnings'] = 2
            return saved

        self.backend.save = warned
        report = self.run_controls()
        self.assertFalse(report['success'])
        self.assertIn('save_warnings=2', report['failure']['message'])
        self.assertEqual(report['controls'][-1]['saved']['save']['save_warnings'], 2)
        self.assertEqual(report['controls'][-1]['creation']['error']['message'], self.controls.INJECTED_MESSAGE)
        self.assertNotIn('reopen', self.backend.calls)

    def test_read_only_fixture_retains_save_before_failed_reopen(self):
        prepare = self.backend.prepare_refusal

        def failed_reopen(name, case, receipt):
            prepare(name, case, receipt)
            if name == 'private-read-only':
                receipt['saved'] = self.backend.save(case)
                raise RuntimeError('first fixture reopen failure')

        self.backend.prepare_refusal = failed_reopen
        report = self.run_controls()
        self.assertEqual(report['failed_control'], 'private-read-only')
        self.assertEqual(report['failure']['message'], 'first fixture reopen failure')
        self.assertEqual(report['controls'][-1]['fixture']['saved']['save']['save_warnings'], 0)
        self.assertEqual(self.backend.calls.count('create'), 0)

    def test_partial_first_failure_survives_cleanup_error(self):
        self.backend.cleanup_errors = [dict(stage='ExitApp', error='secondary cleanup failure')]
        report = self.run_controls()
        self.assertFalse(report['success'])
        self.assertEqual(report['controls'][-1]['creation']['error']['message'], self.controls.INJECTED_MESSAGE)
        self.assertEqual(report['failure']['type'], 'DirectionCleanupFailed')
        self.assertEqual(report['cleanup_errors'][0]['error'], 'secondary cleanup failure')

    def test_trace_requires_one_creation_after_refusals_and_logged_observation_error(self):
        path = self.path / 'stderr.log'
        events = []
        def add(request_id, stage, call, phase, **extra):
            events.append(dict(event='swcli.native-call', request_id=request_id,
                               stage=stage, call=call, phase=phase, **extra))
        for name, _ in self.controls.REFUSALS:
            add(name,'operation','feature.revolve.refusal-control','begin')
            add(name,'operation','feature.revolve.refusal-control','end')
        partial_id = protocol.case_name(protocol.CASE)
        add(partial_id,'operation','feature.revolve.internal-direction','begin')
        add(partial_id,'revolve','FeatureRevolve2','begin')
        add(partial_id,'revolve','FeatureRevolve2','end')
        add(partial_id,'revolve','read-definition','begin')
        add(partial_id,'revolve','read-definition','error',exception_type='RuntimeError')
        add(partial_id,'operation','feature.revolve.internal-direction','end')
        def write_trace():
            path.write_text('\n'.join(json.dumps(event) for event in events)+'\n')
        write_trace()
        self.controls.verify_control_trace(path)
        add('public-closed-angle','revolve','FeatureRevolve2','begin')
        write_trace()
        with self.assertRaisesRegex(RuntimeError, 'exactly one native creation'):
            self.controls.verify_control_trace(path)

    def test_supervisor_rejects_incomplete_controls_and_ci_route_rejects_option(self):
        report = self.run_controls()
        report['controls'].pop()
        protocol.durable(self.path/'report.json', report)
        child = mock.Mock()
        child.wait.return_value=0
        with mock.patch.object(entry.subprocess,'Popen',return_value=child):
            with self.assertRaisesRegex(RuntimeError, 'all scheduled refusal'):
                entry.supervise(['fake'],self.path,controls=True)
        with mock.patch.object(entry,'exact_source') as proof, mock.patch.object(sys,'stderr'):
            with self.assertRaises(SystemExit):
                entry.main(['--controls','--output-dir','evidence','--expected-head','a'*40])
        proof.assert_not_called()


class DirectionRouteAndSupervisorTests(unittest.TestCase):
    def test_exact_branch_head_manual_default_off_and_mixed_scopes(self):
        ref=route.FEATURE_REFS["native_revolve_direction"];head="a"*40
        self.assertEqual(route.resolve("workflow_dispatch",ref,{}),"portable")
        self.assertEqual(route.resolve("push",ref,{}),"portable")
        self.assertEqual(route.resolve("push","refs/tags/v0.2.4",{}),"full")
        good=dict(native_revolve_direction=True,revolve_direction_head=head)
        self.assertEqual(route.resolve("workflow_dispatch",ref,good,head=head),"native_revolve_direction")
        for event,target,inputs,actual in [("push",ref,good,head),("workflow_dispatch","refs/heads/main",good,head),
                ("workflow_dispatch",ref,{**good,"revolve_direction_head":"a"*7},head),
                ("workflow_dispatch",ref,good,"b"*40),
                *[("workflow_dispatch",ref,{**good,flag:True},head) for flag in (*route.FLAGS,"units_calibration","units_public_acceptance","units_write_calibration") if flag!="native_revolve_direction"]]:
            with self.subTest(event=event,ref=target,inputs=inputs),self.assertRaises(ValueError):
                route.resolve(event,target,inputs,head=actual)
    def test_entrypoint_rejects_unknown_head_before_native_backend(self):
        with mock.patch.dict(os.environ,{"GITHUB_EVENT_NAME":"workflow_dispatch","GITHUB_REF":route.FEATURE_REFS["native_revolve_direction"],"GITHUB_SHA":"b"*40}), \
             mock.patch.object(entry.subprocess,"check_output") as git:
            with self.assertRaisesRegex(ValueError,"exact selected"):
                entry.exact_source("a"*40)
        git.assert_not_called()
    def test_supervisor_1800_timeout_kills_worker_once_and_preserves_timeout_before_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp);child=mock.Mock(pid=12)
            child.wait.side_effect=[subprocess.TimeoutExpired("worker",1800),0]
            def cleanup(path):
                self.assertEqual(json.loads((path/"group-timeout.json").read_text())["seconds"],1800)
                raise RuntimeError("cleanup failed")
            with mock.patch.object(entry.subprocess,"Popen",return_value=child),mock.patch.object(entry,"stop_owned_after_timeout",side_effect=cleanup):
                self.assertEqual(entry.supervise(["fake-worker"],output),124)
            self.assertEqual(child.wait.call_args_list,[mock.call(timeout=1800),mock.call(timeout=10)])
            child.kill.assert_called_once()
            self.assertEqual(json.loads((output/"group-timeout.json").read_text())["cleanup_error"]["message"],"cleanup failed")
    def test_unknown_owned_identity_never_searches_for_or_terminates_a_host(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertFalse(entry.stop_owned_after_timeout(Path(temp))["terminated"])
    def test_workflow_default_off_exact_profile_and_no_matrix_entrypoint(self):
        import yaml
        original=yaml.safe_load((ROOT/".github/workflows/ci.yml").read_text())
        self.assertEqual(len(original.get("on",original.get(True))["workflow_dispatch"]["inputs"]),25)
        workflow=yaml.safe_load((ROOT/".github/workflows/revolve-direction-next.yml").read_text())
        trigger=workflow.get("on",workflow.get(True));inputs=trigger["workflow_dispatch"]["inputs"]
        self.assertIs(inputs["native_revolve_direction"]["default"],False)
        self.assertEqual(inputs["revolve_direction_head"]["default"],"")
        self.assertNotIn("pull_request_target",trigger)
        self.assertEqual(workflow["permissions"],dict(contents="read"))
        self.assertNotIn("secrets",json.dumps(workflow["jobs"]["route"]))
        self.assertIn("needs.route.outputs.profile == 'native_revolve_direction'",workflow["jobs"]["prepare"]["if"])
        job=workflow["jobs"]["native"]
        self.assertIn("github.event_name == 'workflow_dispatch'",job["if"])
        self.assertIn("refs/heads/codex/swcli-revolve-feature-next",job["if"])
        self.assertIn("inputs.revolve_direction_head == github.sha",job["if"])
        self.assertIn("swcli-revolve-direction-",job["concurrency"]["group"])
        self.assertIs(job["concurrency"]["cancel-in-progress"],False)
        step=next(s for s in job["steps"] if s.get("id")=="revolve_direction")
        self.assertEqual(step["timeout-minutes"],31)
        self.assertIn("--expected-head $env:SWCLI_REVOLVE_DIRECTION_HEAD",step["run"])
        self.assertNotIn("--matrix",step["run"])
        self.assertNotIn("release",workflow["jobs"])


class LocalDirectionAdmissionTests(unittest.TestCase):
    def test_local_route_refuses_non_windows_non_isolated_and_github_shell(self):
        windows = SimpleNamespace(platform="win32", flags=SimpleNamespace(isolated=1))
        with mock.patch.object(entry, "sys", windows), mock.patch.dict(os.environ, {}, clear=True):
            entry.require_local_route()
            with mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_dispatch"}):
                with self.assertRaisesRegex(RuntimeError, "without GitHub"):
                    entry.require_local_route()
            windows.flags.isolated = 0
            with self.assertRaisesRegex(RuntimeError, "python -I"):
                entry.require_local_route()
            windows.platform = "darwin"
            with self.assertRaisesRegex(RuntimeError, "requires Windows"):
                entry.require_local_route()

    def test_local_wheel_checks_archive_provenance_and_installed_resource_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source = root / "src/swcli"
            installed = root / "site/swcli"
            members = {"__init__.py": b"# module", "py.typed": b""}
            for package in (source, installed):
                package.mkdir(parents=True)
                for name, content in members.items():
                    (package / name).write_bytes(content)
            path = root / "swcli-1-py3-none-any.whl"
            with ZipFile(path, "w") as wheel:
                for name, content in members.items():
                    wheel.writestr("swcli/" + name, content)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            dist = mock.Mock(version="1")
            dist.locate_file.return_value = installed
            dist.read_text.return_value = json.dumps({"archive_info": {"hashes": {"sha256": digest}}})
            ls_tree = b"src/swcli/__init__.py\0src/swcli/py.typed\0"
            with mock.patch.object(entry, "distribution", return_value=dist), \
                 mock.patch.object(entry.subprocess, "check_output", return_value=ls_tree):
                proof = entry.verify_local_wheel(root, "a" * 40, installed, path, digest)
                self.assertEqual(proof["package_files_verified"], 2)
                with self.assertRaisesRegex(RuntimeError, "archive SHA256"):
                    entry.verify_local_wheel(root, "a" * 40, installed, path, "b" * 64)
                (installed / "py.typed").write_text("changed")
                with self.assertRaisesRegex(RuntimeError, "installed package differ: swcli/py.typed"):
                    entry.verify_local_wheel(root, "a" * 40, installed, path, digest)
                dist.read_text.return_value = '{"dir_info":{"editable":true}}'
                with self.assertRaisesRegex(RuntimeError, "install SWCLI from the declared wheel"):
                    entry.verify_local_wheel(root, "a" * 40, installed, path, digest)

    def test_local_installation_uses_registered_exe_and_rejects_missing_or_substitute_tlb(self):
        clsid = "{aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee}"
        local_server = "CLSID\\" + clsid + r"\LocalServer32"
        with tempfile.TemporaryDirectory() as temp:
            install = Path(temp).resolve() / "Program Files" / "SOLIDWORKS Corp" / "SOLIDWORKS"
            install.mkdir(parents=True)
            executable, swconst, sldworks = (install / name for name in ("SLDWORKS.exe", "swconst.tlb", "sldworks.tlb"))
            for path in (executable, swconst, sldworks):
                path.write_bytes(path.name.encode())
            registry = SimpleNamespace(HKEY_CLASSES_ROOT=object(), REG_SZ=1, REG_EXPAND_SZ=2)
            values = {(r"SldWorks.Application\CLSID", ""): (clsid, 1),
                      (local_server, ""): (f'"{executable}" /Embedding', 1),
                      (local_server, "ServerExecutable"): (str(executable), 1)}

            def read(key, member):
                try:
                    return values[key, member]
                except KeyError:
                    raise FileNotFoundError(member) from None

            registry.OpenKey = lambda root, key: nullcontext(key)
            registry.QueryValueEx = read
            alternative = install.parent / "sldworks.tlb"
            alternative.write_bytes(sldworks.read_bytes())
            with mock.patch.dict(sys.modules, winreg=registry):
                result = entry.require_local_installation(None, None)
                self.assertEqual(result["executable"], str(executable))
                self.assertEqual(result["libraries"]["sldworks.tlb"],
                                 dict(path=str(sldworks), sha256=hashlib.sha256(sldworks.read_bytes()).hexdigest()))
                with self.assertRaisesRegex(RuntimeError, "requires the installed type library"):
                    entry.require_local_installation(swconst, alternative)
                alternate_exe = install.parent / "SLDWORKS.exe"
                alternate_exe.touch()
                values[local_server, "ServerExecutable"] = (str(alternate_exe), 1)
                with self.assertRaisesRegex(RuntimeError, "ServerExecutable differs"):
                    entry.require_local_installation(None, None)
                del values[local_server, "ServerExecutable"]
                sldworks.unlink()
                with self.assertRaisesRegex(RuntimeError, "is missing .*sldworks.tlb"):
                    entry.require_local_installation(None, None)

    def test_local_parent_passes_registered_install_to_worker_and_supervisor(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            swconst, sldworks, executable = (root/name for name in ("swconst.tlb", "sldworks.tlb", "SLDWORKS.exe"))
            output = root / "result"
            wheel = root / "swcli.whl"
            head, digest = "a" * 40, "b" * 64
            args = ["--local-windows", "--wheel", str(wheel), "--wheel-sha256", digest,
                    "--expected-head", head, "--output-dir", str(output)]
            proof = dict(source_commit=head, entrypoint="local-windows", wheel_sha256=digest)
            install = dict(executable=str(executable), libraries={path.name: {"path": str(path)}
                                                                 for path in (swconst, sldworks)})
            with mock.patch.object(entry, "exact_source", side_effect=lambda *a, **kw: dict(proof)) as exact, \
                 mock.patch.object(entry, "require_local_installation", return_value=install) as installation, \
                 mock.patch.object(entry.subprocess, "run") as installed_check, \
                 mock.patch.object(entry, "supervise", return_value=0) as supervise:
                self.assertEqual(entry.main(args), 0)
                exact.assert_called_once_with(head, local_wheel=wheel, wheel_sha256=digest)
                installation.assert_called_once_with(None, None)
                self.assertTrue(installed_check.call_args.args[0][-1].endswith("verify-installed.py"))
                command = supervise.call_args.args[0]
                self.assertIn("--local-windows", command)
                self.assertEqual(supervise.call_args.kwargs, {"expected_image": str(executable)})
                self.assertEqual(command[command.index("--sldworks")+1], str(sldworks))
                self.assertEqual(json.loads((output / "source-proof-parent.json").read_text()), dict(proof, installation=install))
                installation.return_value = dict(install, executable=str(root / "another" / "SLDWORKS.exe"))
                with self.assertRaisesRegex(RuntimeError, "worker provenance differs"):
                    entry.main(["--worker", *args])
                self.assertFalse((output / "source-proof.json").exists())


class DirectionNativeBackendOfflineTests(unittest.TestCase):
    """Exercise backend bindings using plain objects; no pywin32/native host."""
    def test_non_windows_start_refuses_before_any_com_import(self):
        from gate_support.revolve_direction_native import NativeBackend
        backend=NativeBackend(Path('/unused'),'unused','unused')
        with mock.patch('sys.platform','darwin'):
            with self.assertRaisesRegex(RuntimeError,'native Windows'):backend.start()
    def test_failed_close_is_not_retried_during_separate_owned_cleanup(self):
        from types import SimpleNamespace as NS
        from gate_support.revolve_direction_native import NativeBackend
        from swcli.hosts.windows import _com_value
        backend=NativeBackend(Path('/unused'),'unused','unused')
        backend.document=NS(GetTitle='Owned');backend.owned=True;backend.value=_com_value
        backend.app=NS(CloseDoc=mock.Mock(side_effect=RuntimeError('first close error')),ExitApp=mock.Mock(spec=lambda:None))
        backend.inventory=mock.Mock(return_value=[])
        backend.call=lambda name,function,**options:function()
        with self.assertRaisesRegex(RuntimeError,'first close error'):backend.close()
        self.assertEqual(backend.cleanup(),[])
        backend.app.CloseDoc.assert_called_once_with('Owned')
        backend.app.ExitApp.assert_called_once()
    def test_native_reopen_binding_preserves_partial_definition_on_wrong_angle(self):
        from types import SimpleNamespace as NS
        from gate_support.revolve_direction_native import NativeBackend
        from swcli.hosts.windows import _com_value
        from swcli.hosts import windows_revolves,windows_documents,windows_sketches,windows_rectangle_profiles
        backend=NativeBackend(Path('/unused'),'unused','unused');backend.value=_com_value
        backend.app=NS();backend.constants=dict(windows_revolves._CALIBRATED_CONSTANTS)
        axis=NS(GetStartPoint2=NS(X=0,Y=-.005,Z=0),GetEndPoint2=NS(X=0,Y=.015,Z=0))
        definition=NS(AccessSelections=lambda *a:True,ReleaseSelectionAccess=mock.Mock(spec=lambda:None),
            GetRevolutionAngle=lambda forward:math.pi,ReverseDirection=False,Type=0,IsBossFeature=True,
            IsThinFeature=False,Merge=True,GetAxisType=10,GetContoursCount=0,Axis=axis)
        sketch=NS(ModelToSketchTransform=NS(ArrayData=protocol.IDENTITY))
        sub=NS(GetTypeName2='ProfileFeature',GetSpecificFeature2=sketch,GetNextSubFeature=None)
        feature=NS(GetTypeName2='Revolution',GetFirstSubFeature=sub,GetDefinition=definition)
        profile=NS(bounds_mm=(0,-5,10,15),left_edge=axis,construction_segment_count=2,native_segment_count=6)
        observed={};creation=dict(candidate=dict(axis_points_mm=[(0,-5,0),(0,15,0)]))
        with mock.patch.object(windows_documents,'open_windows_document_with_handle',return_value=(dict(ok=True,api_errors=0,api_warnings=0),object())), \
             mock.patch.object(windows_sketches,'_features',return_value=[feature]), \
             mock.patch.object(windows_rectangle_profiles,'observe_rectangle_profile',return_value=profile), \
             mock.patch.object(windows_revolves,'_null_dispatch',return_value=None), \
             mock.patch.object(windows_revolves,'_same',side_effect=lambda app,a,b:a is b):
            with self.assertRaisesRegex(Exception,'settings differ'):
                backend.reopen(dict(path='unused'),creation,protocol.CASE,observed)
        self.assertEqual(observed['definition']['angle_rad'],math.pi)
        self.assertEqual(observed['bounds_mm'],[0,-5,10,15])
        definition.ReleaseSelectionAccess.assert_called_once()
    def test_installed_source_or_dirty_checkout_mismatch_fails_before_native_setup(self):
        env={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF':route.FEATURE_REFS['native_revolve_direction'],'GITHUB_SHA':'a'*40}
        for outputs, message in ((['b'*40],'checkout head'),(['a'*40,' M scripts/example.py'],'not clean')):
            with mock.patch.dict(os.environ,env),mock.patch.object(entry.subprocess,'check_output',side_effect=outputs):
                with self.assertRaisesRegex(RuntimeError,message):entry.exact_source('a'*40)


class DirectionFailureCompletionTests(unittest.TestCase):
    def test_mutating_a_backend_case_cannot_rewrite_preregistered_hypothesis(self):
        with tempfile.TemporaryDirectory() as temp:
            backend=FakeBackend();original=backend.create
            def rewrite(case):case["rotation_sign"]=1;return original(case)
            backend.create=rewrite
            report=protocol.run_direction(backend,protocol.Evidence(Path(temp)),"a"*40)
            self.assertFalse(report["success"])
            self.assertEqual(report["case"]["rotation_sign"],-1)
            self.assertNotIn("save",backend.calls)
    def test_timeout_checkpoint_failure_still_stops_worker_and_attempts_owned_cleanup_once(self):
        with tempfile.TemporaryDirectory() as temp:
            child=mock.Mock(pid=12);child.wait.side_effect=[subprocess.TimeoutExpired("worker",1800),0]
            original=entry.durable
            attempts=[]
            def fail_first(path,value):
                attempts.append(path)
                if len(attempts)==1:raise OSError("timeout disk failure")
                return original(path,value)
            with mock.patch.object(entry.subprocess,"Popen",return_value=child), \
                 mock.patch.object(entry,"durable",side_effect=fail_first), \
                 mock.patch.object(entry,"stop_owned_after_timeout",return_value=dict(terminated=False)) as cleanup:
                self.assertEqual(entry.supervise(["fake"],Path(temp)),124)
            child.kill.assert_called_once();cleanup.assert_called_once()
            self.assertEqual(json.loads((Path(temp)/"group-timeout.json").read_text())["initial_evidence_error"],"timeout disk failure")
    def test_recycled_recorded_pid_is_never_terminated(self):
        from types import SimpleNamespace as NS
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp);protocol.durable(output/"owned-host.json",dict(identity=dict(pid=7,creation_timestamp=1),launch_timestamp=0))
            handle=mock.Mock();owner=NS(capture=mock.Mock(return_value=(handle,dict(pid=7,creation_timestamp=2))),terminate=mock.Mock())
            from gate_support import revolve_direction_native
            with mock.patch.object(revolve_direction_native,"load_script",return_value=owner):
                with self.assertRaisesRegex(RuntimeError,"identity changed"):entry.stop_owned_after_timeout(output)
            owner.terminate.assert_not_called();handle.Close.assert_called_once()
    def test_local_timeout_only_recaptures_the_parent_confirmed_registered_executable(self):
        from gate_support import revolve_direction_native
        image = r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            identity = dict(pid=7, creation_timestamp=1, image=image)
            protocol.durable(output / "owned-host.json", dict(identity=identity, launch_timestamp=0, expected_image=image))
            handle = mock.Mock()
            owner = SimpleNamespace(capture=mock.Mock(return_value=(handle, identity)), terminate=mock.Mock())
            event = SimpleNamespace(WaitForSingleObject=mock.Mock(return_value=0), WAIT_OBJECT_0=0)
            with mock.patch.object(revolve_direction_native, "load_script", return_value=owner), \
                 mock.patch.dict(sys.modules, win32event=event):
                with self.assertRaisesRegex(RuntimeError, "installation differs"):
                    entry.stop_owned_after_timeout(output, expected_image=r"C:\Other\SLDWORKS.exe")
                owner.capture.assert_not_called()
                self.assertTrue(entry.stop_owned_after_timeout(output, expected_image=image)["terminated"])
            self.assertEqual(owner.capture.call_args.kwargs["expected_image"], image)
            owner.terminate.assert_called_once_with(handle, identity)
            event.WaitForSingleObject.assert_called_once_with(handle, 10000)

    def test_zero_exit_without_report_is_refused_and_completed_failure_needs_no_second_host_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp);child=mock.Mock(pid=12);child.wait.return_value=0
            with mock.patch.object(entry.subprocess,"Popen",return_value=child):
                with self.assertRaisesRegex(RuntimeError,"without complete"):entry.supervise(["fake"],output)
            protocol.durable(output/"report.json",dict(success=False,owned_cleanup_completed=True))
            child.wait.return_value=1
            with mock.patch.object(entry.subprocess,"Popen",return_value=child), \
                 mock.patch.object(entry,"stop_owned_after_timeout") as cleanup:
                self.assertEqual(entry.supervise(["fake"],output),1)
            cleanup.assert_not_called()


if __name__=="__main__":unittest.main()
