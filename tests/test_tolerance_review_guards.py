"""Regression tests for native host, CI combinations and post-mutation receipts."""
import ast
from copy import deepcopy
import importlib.util
from itertools import product
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tests import test_document_tolerances as fixtures
from swcli.daemon import operations,server
from swcli.hosts import windows_document_tolerances as adapter
from swcli.result_schemas import validate_operation_result

ROOT=Path(__file__).resolve().parents[1]
REAL_NATIVE_WINDOWS=adapter._native_windows
spec=importlib.util.spec_from_file_location("_tolerance_profile_contract",ROOT/"scripts/ci/tolerance-profile.py")
profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)


class NativeWindowsProbeTests(unittest.TestCase):
    def test_native_wine_nonwindows_and_unknown_probe(self):
        with mock.patch.object(adapter.sys,"platform","darwin"),mock.patch.object(adapter.ctypes,"WinDLL",create=True) as loader:
            self.assertFalse(REAL_NATIVE_WINDOWS());loader.assert_not_called()
        for dll,expected in ((SimpleNamespace(),True),(SimpleNamespace(wine_get_version=object()),False)):
            with mock.patch.object(adapter.sys,"platform","win32"),mock.patch.object(adapter.ctypes,"WinDLL",return_value=dll,create=True) as loader:
                self.assertIs(REAL_NATIVE_WINDOWS(),expected);loader.assert_called_once_with("ntdll")
        with mock.patch.object(adapter.sys,"platform","win32"),mock.patch.object(adapter.ctypes,"WinDLL",side_effect=OSError("probe unavailable"),create=True):
            with self.assertRaises(OSError):REAL_NATIVE_WINDOWS()


class ReceiptAndIdentityTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ToleranceTests("test_cli_preserves_complete_snapshot_and_guards")
        self.f.setUp();self.addCleanup(self.f.doCleanups)

    def test_same_revision_wine_reads_disabled_and_writes_never_call_setter(self):
        with mock.patch.object(adapter,"_native_windows",side_effect=REAL_NATIVE_WINDOWS), \
             mock.patch.object(adapter.sys,"platform","win32"), \
             mock.patch.object(adapter.ctypes,"WinDLL",return_value=SimpleNamespace(wine_get_version=object()),create=True):
            observed=self.f.call();self.assertTrue(observed["ok"]);self.assertFalse(observed["write_enabled"])
            refused=self.f.edit(expected=observed["options"])
            self.assertFalse(refused["ok"]);self.assertEqual(refused["mutation"],dict(attempted=False,may_have_changed=False))
            self.f.assert_no_mutation()

    def test_successful_setter_descriptor_exception_preserves_partial_receipt(self):
        expected=self.f.call()["options"];original=self.f.registry.describe;count=0
        def describe(*args,**kwargs):
            nonlocal count
            count+=1
            if count==2:raise RuntimeError("final descriptor observation failed")
            return original(*args,**kwargs)
        with mock.patch.object(self.f.registry,"describe",side_effect=describe):result=self.f.edit(expected=expected)
        self.assertFalse(result["ok"]);self.assertEqual(result["error"]["type"],"DocumentObservationFailed")
        self.assertEqual(result["mutation"],dict(attempted=True,may_have_changed=True))
        self.assertNotIn("document",result);self.assertEqual(result["options"]["linear.type"]["value"],"basic")
        self.assertTrue(self.f.dirty);self.assertEqual(self.f.native[201],1)
        self.f.extension.SetUserPreferenceInteger.assert_called_once();validate_operation_result("document.tolerance-set",result)

    def test_first_native_failure_is_not_overwritten_by_descriptor_failure(self):
        expected=self.f.call()["options"];original=self.f.registry.describe;count=0
        def describe(*args,**kwargs):
            nonlocal count
            count+=1
            if count==2:raise RuntimeError("final descriptor observation failed")
            return original(*args,**kwargs)
        def native_false(*args):self.f.apply(*args);return False
        self.f.extension.SetUserPreferenceInteger.side_effect=native_false
        with mock.patch.object(self.f.registry,"describe",side_effect=describe):result=self.f.edit(expected=expected)
        self.assertFalse(result["ok"]);self.assertEqual(result["error"]["message"],"native tolerance setter did not return success")
        self.assertIn("document_observation_error",result["error"])
        self.assertEqual(result["mutation"],dict(attempted=True,may_have_changed=True))
        self.f.extension.SetUserPreferenceInteger.assert_called_once();self.f.document.SetSaveFlag.assert_not_called()
        validate_operation_result("document.tolerance-set",result)

    def test_identity_or_background_foreground_state_drift_refuse_before_mutation(self):
        expected=self.f.call()["options"]
        def reader(preference,option):
            self.f.document.GetPathName=lambda:"changed.SLDPRT"
            return self.f.native[preference]
        self.f.extension.GetUserPreferenceInteger.side_effect=reader
        result=self.f.edit(expected=expected)
        self.assertFalse(result["ok"]);self.f.assert_no_mutation()
        self.f.document.GetPathName=lambda:""
        def reader(preference,option):
            self.f.foreground.GetSaveFlag=lambda:True
            return self.f.native[preference]
        self.f.extension.GetUserPreferenceInteger.side_effect=reader
        result=self.f.edit(expected=expected)
        self.assertFalse(result["ok"]);self.f.assert_no_mutation()

    def test_identity_drift_after_setter_keeps_possible_mutation_without_repair(self):
        expected=self.f.call()["options"]
        def apply(preference,option,value):
            self.f.apply(preference,option,value)
            self.f.document.GetTitle=lambda:"changed identity"
            return True
        self.f.extension.SetUserPreferenceInteger.side_effect=apply
        result=self.f.edit(expected=expected)
        self.assertFalse(result["ok"])
        self.assertEqual(result["mutation"],dict(attempted=True,may_have_changed=True))
        self.f.extension.SetUserPreferenceInteger.assert_called_once()
        self.f.document.SetSaveFlag.assert_not_called()

    def test_worker_restore_failure_after_result_keeps_receipt_and_stops_dispatch(self):
        from tests import test_native_sequence as sequence
        for business_failed in (False,True):
            with self.subTest(business_failed=business_failed):
                class App:
                    value=False
                    GetProcessID=lambda self:1234
                    RevisionNumber="33.5.0"
                    ActiveDoc=object()
                    @property
                    def CommandInProgress(self):return self.value
                    @CommandInProgress.setter
                    def CommandInProgress(self,value):
                        if not value:raise RuntimeError("restore after setter failed")
                        self.value=value
                app=App()
                result=dict(ok=not business_failed,action="document.tolerance-set",scope="document_defaults_linear",
                            mutation=dict(attempted=True,may_have_changed=True))
                if business_failed:result["error"]=dict(type="NativeFailure",message="first native error")
                request=dict(request_id="once",operation="document.tolerance-set",parameters={})
                fixture=sequence.NativeSequenceTests("test_worker_restore_failure_ends_dispatch_and_reports_recovery")
                execute=mock.Mock(return_value=result)
                responses,lifecycle,wait=fixture.run_worker(app,True,execute,[request,request,None])
                reply=responses.put.call_args.args[0]
                self.assertFalse(reply["success"])
                self.assertEqual(reply["error"]["code"],"NativeCommandRestoreFailed")
                self.assertEqual(reply["result"]["mutation"],dict(attempted=True,may_have_changed=True))
                self.assertFalse(reply["result"]["ok"])
                if business_failed:self.assertEqual(reply["result"]["error"]["message"],"first native error")
                execute.assert_called_once();self.assertEqual(wait.call_count,1)
                self.assertEqual(lifecycle.put.call_args.args[0]["event"],"host-disconnected")

    def test_worker_new_request_exception_cannot_reuse_previous_mutation_receipt(self):
        from tests import test_native_sequence as sequence
        app=SimpleNamespace(CommandInProgress=False,GetProcessID=lambda:1234,RevisionNumber="33.5.0",ActiveDoc=object())
        first=dict(request_id="first",operation="document.tolerance-set",parameters={})
        second=dict(first,request_id="second")
        receipt=dict(ok=True,action="document.tolerance-set",scope="document_defaults_linear",
                     mutation=dict(attempted=True,may_have_changed=True))
        execute=mock.Mock(side_effect=[receipt,RuntimeError("second request before any result")])
        fixture=sequence.NativeSequenceTests("test_worker_restores_before_next_request_and_shutdown")
        responses,lifecycle,wait=fixture.run_worker(app,True,execute,[first,second,None])
        replies=[call.args[0] for call in responses.put.call_args_list]
        self.assertTrue(replies[0]["success"]);self.assertEqual(replies[0]["request_id"],"first")
        self.assertEqual(replies[0]["result"]["mutation"],dict(attempted=True,may_have_changed=True))
        self.assertFalse(replies[1]["success"]);self.assertEqual(replies[1]["request_id"],"second")
        self.assertNotIn("result",replies[1]);self.assertEqual(execute.call_count,2);self.assertEqual(wait.call_count,3)

    def test_worker_restore_or_validation_error_keeps_receipt_and_primary_error(self):
        result=self.f.edit();self.assertTrue(result["ok"])
        response=server._error_response("request","RuntimeError","worker wrapper failed")
        preserved=server._preserve_tolerance_receipt(response,"document.tolerance-set",result,RuntimeError("worker wrapper failed"))
        self.assertFalse(preserved["result"]["ok"])
        self.assertEqual(preserved["result"]["mutation"],dict(attempted=True,may_have_changed=True))
        self.assertTrue(result["ok"])
        original=deepcopy(preserved["result"]);original["error"]={"type":"NativeFailure","message":"first native error"}
        again=server._preserve_tolerance_receipt({},"document.tolerance-set",original,RuntimeError("worker wrapper failed"))
        self.assertEqual(again["result"]["error"]["message"],"first native error")
        self.assertIn("worker_error",again["result"]["error"])
        self.assertNotIn("result",server._preserve_tolerance_receipt({},"document.inspect",result,RuntimeError("other")))
        validate_operation_result("document.tolerance-set",preserved["result"])


class ExclusiveNativeProfileTests(unittest.TestCase):
    def test_all_boolean_modes_and_branch_event_combinations(self):
        for event,ref in (("workflow_dispatch",profile.BRANCH),("workflow_dispatch","refs/heads/main"),
                          ("workflow_dispatch","refs/heads/other"),("push","refs/tags/v0.2.4"),
                          ("push",profile.BRANCH),("pull_request",profile.BRANCH)):
            for full,calibrate,accept in product((False,True),repeat=3):
                with self.subTest(event=event,ref=ref,full=full,calibrate=calibrate,accept=accept):
                    if calibrate or accept:
                        if event!="workflow_dispatch" or ref!=profile.BRANCH or full or (calibrate and accept):
                            with self.assertRaises(ValueError):profile.resolve_profile(event,ref,native_full=full,calibrate=calibrate,accept=accept)
                        else:self.assertEqual(profile.resolve_profile(event,ref,native_full=full,calibrate=calibrate,accept=accept),
                                             "tolerances-calibration" if calibrate else "tolerances-public")
                    else:
                        wanted="full" if (event=="workflow_dispatch" and full) or (event=="push" and ref.startswith("refs/tags/v")) else "portable"
                        self.assertEqual(profile.resolve_profile(event,ref,native_full=full),wanted)

    def test_cli_rejects_original_main_mixed_mode_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary)/"output"
            result=subprocess.run([sys.executable,str(ROOT/"scripts/ci/tolerance-profile.py"),"--event","workflow_dispatch",
                "--ref","refs/heads/main","--native-full","true","--calibrate","true","--accept","false",
                "--github-output",str(out)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertFalse(out.exists())
            result=subprocess.run([sys.executable,str(ROOT/"scripts/ci/tolerance-profile.py"),"--event","workflow_dispatch",
                "--ref",profile.BRANCH,"--native-full","false","--calibrate","false","--accept","true",
                "--github-output",str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(out.read_text(),"profile=tolerances-public\n")

    def test_actual_gate_conditions_select_only_the_validated_profile(self):
        source=(ROOT/".github/workflows/ci.yml").read_text()
        job=source.split("  solidworks-e2e:",1)[1].split("  release:",1)[0]
        self.assertIn("needs: [test, package, tag-policy, native-profile, units-route]",job)
        self.assertIn("needs.native-profile.result == 'success'",job)
        self.assertNotIn("inputs.calibrate_tolerances",job);self.assertNotIn("inputs.accept_tolerances",job)
        identifiers=("property_fixtures","annotation_fixtures","tolerance_calibration","tolerance_acceptance","native_tests")
        for mode,wanted in (("full",{"property_fixtures","annotation_fixtures","native_tests"}),
                            ("tolerances-calibration",{"tolerance_calibration"}),
                            ("tolerances-public",{"annotation_fixtures","tolerance_acceptance"}),
                            ("portable",set()),("",set())):
            selected=set()
            for ident in identifiers:
                block=job.split("        id: "+ident+"\n",1)[1].split("      - name:",1)[0]
                expression=next(line.strip()[len("if: ${{ "):-len(" }}")] for line in block.splitlines() if line.strip().startswith("if: ${{ "))
                expression=expression.replace("needs.native-profile.outputs.profile",repr(mode)).replace("||","or").replace("&&","and")
                tree=ast.parse(expression,mode="eval")
                self.assertTrue(all(isinstance(n,(ast.Expression,ast.BoolOp,ast.Or,ast.And,ast.Compare,ast.Eq,ast.Constant,ast.Load)) for n in ast.walk(tree)))
                if eval(compile(tree,"profile condition","eval"),{"__builtins__":{}},{}):selected.add(ident)
            self.assertEqual(selected,wanted)
        preflight=source.split("  native-profile:",1)[1].split("  solidworks-e2e:",1)[0]
        self.assertNotIn("secrets.",preflight);self.assertIn("validate-native-profile.py",preflight)
        self.assertIn("SWCLI_NATIVE_PROFILE",job)


if __name__=="__main__":unittest.main()
