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

    def test_rectangular_slot_uses_independent_volume_and_four_wall_area(self):
        for thickness in (10,25):
            metrics={'solid_body_count':1,'volume_mm3':1176*thickness,
                     'surface_area_mm2':2352+160*thickness}
            gate.verify_geometry(metrics,thickness,cut=True,profile_kind='rectangle')
            with self.assertRaises(RuntimeError):
                gate.verify_geometry(metrics,thickness,cut=True,profile_kind='circle')
            metrics['surface_area_mm2']-=24
            with self.assertRaises(RuntimeError):
                gate.verify_geometry(metrics,thickness,cut=True,profile_kind='rectangle')

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
                evidence={}
                with self.subTest(member=name),self.assertRaises(RuntimeError):
                    gate.observe(document,feature,{"swEndCondThroughAll":17},False,invoke,evidence)
                self.assertEqual(evidence["end_condition"],0 if name=="GetEndCondition" else 17)
                self.assertEqual(evidence["expected_settings"]["end_condition"],17)
                self.assertEqual(evidence["expected_settings"]["feature_scope"],False)
                self.assertNotIn("diagnostics",evidence)
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

    def test_all_body_creation_disables_auto_selection_instead_of_accepting_wrong_scope(self):
        feature=object()
        create=mock.Mock(return_value=feature)
        document=SimpleNamespace(SelectionManager=SimpleNamespace(GetSelectedObjectCount2=lambda mark:0),
            FeatureManager=SimpleNamespace(FeatureCut4=create), ClearSelection2=mock.Mock())
        for reverse in (False,True):
            self.assertIs(gate.create_cut(document,SimpleNamespace(Select2=lambda a,m:True),
                {"swEndCondThroughAll":1,"swEndCondBlind":0},reverse,lambda n,f:f(),{"cleanup_errors":[]}),feature)
            args=create.call_args.args
            self.assertEqual(len(args),27)
            self.assertIs(args[2],not reverse)
            self.assertEqual(args[3],1)
            self.assertIs(args[18],False)  # UseFeatScope
            self.assertIs(args[19],False)  # UseAutoSelect must not normalize to scoped selection.

    def test_exact_retained_catalog_cannot_hide_a_new_missing_or_replaced_document(self):
        a,b=object(),object()
        actual=[]
        app=SimpleNamespace(GetDocumentCount=lambda:len(actual),GetDocuments=lambda:actual,
                            IsSame=lambda x,y:int(x is y))
        invoke=lambda n,f:f()
        gate.require_catalog(app,(),invoke,'empty')
        actual[:]=[a]
        gate.require_catalog(app,(a,),invoke,'retained')
        for expected in ((),(b,),(a,b)):
            with self.subTest(expected=len(expected)),self.assertRaises(RuntimeError):
                gate.require_catalog(app,expected,invoke,'bad')
        actual[:]=[a,a]
        with self.assertRaises(RuntimeError):
            gate.require_catalog(app,(a,a),invoke,'duplicate')
        actual[:]=[a,b]
        with self.assertRaises(RuntimeError):
            gate.require_catalog(app,(a,a),invoke,'duplicate-retained')

    def test_fixture_growth_cleans_native_edit_selection_without_clearing_preexisting_selection(self):
        selected=[0]
        data=SimpleNamespace(SetDepth=mock.Mock(),GetDepth=lambda forward:0.025,
                             SetChangeToConfigurations=lambda scope,names:True)
        def commit(*args):
            selected[0]=1
            return True
        boss=SimpleNamespace(GetDefinition=lambda:data,ModifyDefinition=mock.Mock(side_effect=commit))
        document=SimpleNamespace(SelectionManager=SimpleNamespace(GetSelectedObjectCount2=lambda mark:selected[0]),
            EditRebuild3=lambda:True,ClearSelection2=lambda all_:selected.__setitem__(0,0))
        evidence={}
        with mock.patch.object(gate,'_empty_variant'),mock.patch.object(gate,'_null_dispatch'):
            gate.grow_fixture_boss(document,boss,{'swThisConfiguration':1},lambda n,f:f(),evidence)
            self.assertEqual(evidence['selection_count_before_owned_cleanup'],1)
            self.assertEqual(selected[0],0)
            boss.ModifyDefinition.assert_called_once()
            selected[0]=2
            with self.assertRaisesRegex(RuntimeError,'existing selection'):
                gate.grow_fixture_boss(document,boss,{'swThisConfiguration':1},lambda n,f:f(),{})
            self.assertEqual(selected[0],2)
            boss.ModifyDefinition.assert_called_once()

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
