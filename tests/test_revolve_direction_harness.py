"""Offline direction harness/route controls; never a native execution."""
from copy import deepcopy
import importlib.util
import json
import math
import os
from pathlib import Path
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
        return dict(angle_rad=math.pi/2,reverse=False,kind=0,boss=True,thin=False,merge=True,
            axis_type=10,contour_count=0,axis_matches=True,axis_points_mm=deepcopy(self.points),cleanup_errors=[])
    def create(self,case):
        self.calls.append("create")
        metrics=protocol.sector_expectation(case["bounds_mm"],protocol.IDENTITY,case["angle_deg"],rotation_sign=case["rotation_sign"])
        self.creation=dict(ok=True,angle_deg=90,axis_mm=case["axis_mm"],expected_profile_mm=case["bounds_mm"],
            mutation=dict(attempted=True,creation_returned=True,may_have_changed=True),
            candidate=dict(rotation_sign=-1,axis_direction=1,axis_points_mm=deepcopy(self.points)),
            feature=dict(name="Revolve",type="Revolution"),definition=self.definition(),
            model_to_sketch_transform=protocol.IDENTITY[:],expected_metrics=deepcopy(metrics),metrics=metrics,
            verified=True,diagnostics=dict(healthy=True,truncated=False),cleanup_errors=[])
        if self.fault:self.fault(self.creation)
        return self.creation,True
    def save(self):self.calls.append("save");return dict(save=dict(ok=True),file_size_bytes=42,file_sha256="abc",path="fake.SLDPRT")
    def close(self):self.calls.append("close")
    def reopen(self,saved,creation,case,observed):
        self.calls.append("reopen")
        observed.update(reopen=dict(ok=True,api_errors=0,api_warnings=0),feature_count=1,profile_count=1,body_count=1,
            bounds_mm=case["bounds_mm"][:],axis_points_mm=deepcopy(self.points),model_to_sketch_transform=protocol.IDENTITY[:],
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
