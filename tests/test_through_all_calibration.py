"""Independent oracle/failure coverage; fake COM is not native feasibility."""

import importlib.util
import json
import math
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci/verify-through-all-calibration.py"
spec = importlib.util.spec_from_file_location("through_all_calibration", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ThroughAllCalibrationTests(unittest.TestCase):
    def metrics(self, depth=10, cut=True):
        return dict(solid_body_count=1, volume_mm3=(1200 - (9*math.pi if cut else 0))*depth,
                    surface_area_mm2=2400+140*depth+(-18*math.pi+6*math.pi*depth if cut else 0))

    def test_analytic_oracle_detects_shallow_blind_and_unchanged_thickness(self):
        for depth in (10, 25):
            gate.verify_geometry(self.metrics(depth), depth, cut=True)
            gate.verify_geometry(self.metrics(depth, cut=False), depth, cut=False)
        shallow = self.metrics(10)
        shallow["volume_mm3"] = 12000 - math.pi*9  # A 1 mm blind hole, not through.
        for metrics, depth in ((shallow,10), (self.metrics(10),25),
                               (self.metrics(10,cut=False),10)):
            with self.subTest(metrics=metrics), self.assertRaises(RuntimeError):
                gate.verify_geometry(metrics, depth, cut=True)
        for key, value in (("volume_mm3",float("nan")),("surface_area_mm2",float("inf")),
                           ("solid_body_count",2)):
            metrics=self.metrics();metrics[key]=value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                gate.verify_geometry(metrics,10,cut=True)

    def test_native_cut_must_match_end_direction_scope_and_health(self):
        data = SimpleNamespace(GetEndCondition=lambda forward: 17, ReverseDirection=True,
            BothDirections=False, IsThinFeature=False, FeatureScope=False, FromType=0,
            GetDraftWhileExtruding=lambda forward: False)
        feature=SimpleNamespace(GetTypeName2="Cut",GetDefinition=data)
        document=SimpleNamespace(SelectionManager=SimpleNamespace(GetSelectedObjectCount2=lambda mark:0),
                                 Extension=SimpleNamespace(NeedsRebuild2=0))
        invoke=lambda name,fn:fn()
        with mock.patch.object(gate,"_diagnose_features",return_value={"healthy":True,"truncated":False}):
            gate.observe(document,feature,{"swEndCondThroughAll":17},False,invoke)
            for name,value in (("GetEndCondition",lambda forward:0),("ReverseDirection",False),
                               ("BothDirections",True),("IsThinFeature",True),
                               ("FeatureScope",True),("FromType",2),
                               ("GetDraftWhileExtruding",lambda forward:True)):
                before=getattr(data,name);setattr(data,name,value)
                with self.subTest(member=name),self.assertRaises(RuntimeError):
                    gate.observe(document,feature,{"swEndCondThroughAll":17},False,invoke)
                setattr(data,name,before)
        with mock.patch.object(gate,"_diagnose_features",return_value={"healthy":True,"truncated":True}):
            with self.assertRaisesRegex(RuntimeError,"incomplete"):
                gate.observe(document,feature,{"swEndCondThroughAll":17},False,invoke)

    def test_empty_selection_is_required_before_native_mutation(self):
        document=SimpleNamespace(SelectionManager=SimpleNamespace(GetSelectedObjectCount2=lambda mark:1))
        profile=SimpleNamespace(Select2=mock.Mock())
        with self.assertRaisesRegex(RuntimeError,"selection is not owned"):
            gate.create_cut(document,profile,{},False,lambda n,f:f(),{"cleanup_errors":[]})
        profile.Select2.assert_not_called()

    def test_failed_creation_is_never_retried_and_keeps_cleanup_evidence(self):
        cut=mock.Mock(side_effect=RuntimeError("first CAD failure"))
        document=SimpleNamespace(SelectionManager=SimpleNamespace(GetSelectedObjectCount2=lambda m:0),
            FeatureManager=SimpleNamespace(FeatureCut4=cut), SetPickMode=mock.Mock(),
            ClearSelection2=mock.Mock(side_effect=RuntimeError("clear failed")))
        report={"cleanup_errors":[]}
        with self.assertRaisesRegex(RuntimeError,"first CAD failure"):
            gate.create_cut(document,SimpleNamespace(Select2=lambda a,m:True),
                            {"swEndCondThroughAll":17,"swEndCondBlind":3},False,lambda n,f:f(),report)
        cut.assert_called_once();document.SetPickMode.assert_called_once()
        self.assertEqual(report["cleanup_errors"],[{"stage":"ClearSelection2","error":"clear failed"}])

    def test_first_case_failure_stops_plan_and_preserves_owned_cleanup_failure(self):
        com=ModuleType("pythoncom");com.CoInitialize=mock.Mock();com.CoUninitialize=mock.Mock()
        package=ModuleType("win32com");client=ModuleType("win32com.client");package.client=client
        handle=SimpleNamespace(Close=mock.Mock())
        exit_app=mock.Mock(side_effect=RuntimeError("exit failed"))
        app=SimpleNamespace(GetProcessID=123,RevisionNumber="33.5.0",GetDocumentCount=0,
                            ExitApp=lambda:exit_app())
        with tempfile.TemporaryDirectory() as tmp,mock.patch.dict("sys.modules",{
            "pythoncom":com,"win32com":package,"win32com.client":client}), \
            mock.patch.object(gate,"read_constants",return_value={}), \
            mock.patch.object(gate,"acquire_resident_app",return_value=(app,True)), \
            mock.patch.object(gate,"wait_windows_host_ready"), \
            mock.patch.object(gate,"capture_process",return_value=handle), \
            mock.patch.object(gate,"wait_process"), \
            mock.patch.object(gate,"calibrate_case",side_effect=RuntimeError("first case failed")) as case:
            self.assertEqual(gate.run(Path(tmp),Path("swconst.tlb"),False),1)
            report=json.loads((Path(tmp)/"report.json").read_text())
            self.assertFalse(report["success"]);self.assertFalse(report["full_acceptance_eligible"])
            self.assertEqual(report["failure"]["message"],"first case failed")
            self.assertEqual(report["cleanup_errors"],[{"stage":"ExitApp","error":"exit failed"}])
            case.assert_called_once();com.CoUninitialize.assert_called_once();handle.Close.assert_called_once()

    def test_attached_host_is_refused_without_exit_or_fixture_creation(self):
        com=ModuleType("pythoncom");com.CoInitialize=mock.Mock();com.CoUninitialize=mock.Mock()
        package=ModuleType("win32com");client=ModuleType("win32com.client");package.client=client
        app=SimpleNamespace(ExitApp=mock.Mock())
        with tempfile.TemporaryDirectory() as tmp,mock.patch.dict("sys.modules",{
            "pythoncom":com,"win32com":package,"win32com.client":client}), \
            mock.patch.object(gate,"read_constants",return_value={}), \
            mock.patch.object(gate,"acquire_resident_app",return_value=(app,False)), \
            mock.patch.object(gate,"calibrate_case") as case:
            self.assertEqual(gate.run(Path(tmp),Path("swconst.tlb"),False),1)
            app.ExitApp.assert_not_called();case.assert_not_called()

    def test_existing_output_and_missing_library_never_activate_com(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);library=root/"swconst.tlb";library.touch()
            with mock.patch.object(gate,"run") as run,mock.patch("sys.stderr"):
                for out,lib in ((root,library),(root/"new",root/"absent")):
                    with self.assertRaises(SystemExit):
                        gate.main(["--output-dir",str(out),"--swconst",str(lib)])
                run.assert_not_called()
            self.assertFalse((root/"new").exists())


if __name__ == "__main__":
    unittest.main()
