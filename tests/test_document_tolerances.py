"""Portable behavioral tests; fake COM does not imply native acceptance."""
from copy import deepcopy
from types import SimpleNamespace
import json
import unittest
from unittest import mock

from swcli.cli import build_parser, _typed_operation
from swcli.daemon.documents import DocumentRegistry, DocumentLeaseConflict
from swcli.daemon.operations import execute_operation, DocumentUpdateConflict
from swcli.hosts import windows_document_tolerances as adapter
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import validate_operation_result, OperationResultInvalid


class ToleranceTests(unittest.TestCase):
    def setUp(self):
        self.codes = {"swDetailingLinearDimension": 110, "swDetailingToleranceStyle": 201,
                      "swDetailingLinearTolPrecision": 202}  # Deliberately fake IDs.
        self.native = {201: 0, 202: 2}
        self.dirty, self.stamp = False, 7
        self.extension = SimpleNamespace(
            GetUserPreferenceInteger=mock.Mock(side_effect=lambda p,o:self.native[p]),
            SetUserPreferenceInteger=mock.Mock(side_effect=self.apply))
        self.document = SimpleNamespace(
            GetType=lambda: 1, GetSaveFlag=lambda: self.dirty, GetUpdateStamp=lambda:self.stamp,
            GetActiveConfiguration=lambda:SimpleNamespace(Name="Default"), GetTitle=lambda:"Background",
            GetPathName=lambda:"", IsOpenedReadOnly=lambda:False, IsOpenedViewOnly=lambda:False,
            SketchManager=SimpleNamespace(ActiveSketch=None), Extension=self.extension,
            SetSaveFlag=mock.Mock(side_effect=lambda:setattr(self,"dirty",True)))
        self.foreground = SimpleNamespace(GetType=lambda:1, GetSaveFlag=lambda:False,
            GetUpdateStamp=lambda:9, GetTitle=lambda:"Foreground", GetPathName=lambda:"")
        self.app = SimpleNamespace(ActiveDoc=self.foreground, GetDocuments=lambda:(self.document,self.foreground),
            IsSame=lambda a,b:int(a is b), ActivateDoc3=mock.Mock(), SetUserPreferenceIntegerValue=mock.Mock())
        self.registry=DocumentRegistry(self.app)
        self.entry=self.registry.register(self.document)
        self.registry.register(self.foreground)
        self.lease=self.registry.acquire_lease(self.entry,session_id="writer",ttl_seconds=600)["lease_id"]
        self.patch=mock.patch.object(adapter,"native_constants",return_value=self.codes)
        self.patch.start(); self.addCleanup(self.patch.stop)

    def apply(self,p,o,v):
        self.native[p]=v
        return True

    def call(self,operation="document.tolerances",values=None,**context):
        return execute_operation(self.app,operation,values or {},documents=self.registry,
            session_id=context.get("session","writer"),document_id=self.entry.document_id,
            expected_update_stamp=context.get("stamp",7),lease_id=context.get("lease",self.lease) if operation.endswith("-set") else None)

    def edit(self,field="linear.type",value="basic",expected=None):
        expected=self.call()["options"] if expected is None else expected
        return self.call("document.tolerance-set",dict(field=field,value=value,expected_options=expected))

    def enabled(self):
        return mock.patch.object(adapter,"PUBLIC_WRITE_FIELDS",frozenset(("linear.type","linear.precision")))

    def assert_no_mutation(self):
        self.extension.SetUserPreferenceInteger.assert_not_called()
        self.document.SetSaveFlag.assert_not_called()
        self.app.ActivateDoc3.assert_not_called()
        self.app.SetUserPreferenceIntegerValue.assert_not_called()

    def test_background_read_document_defaults_unknown_values_and_no_setters(self):
        self.native[201]=900
        result=self.call(session="observer")
        self.assertTrue(result["ok"],result)
        self.assertEqual(result["scope"],"document_defaults_linear")
        self.assertEqual(result["options"]["linear.type"],dict(value="other",native_value=900))
        self.assertFalse(result["write_enabled"])
        validate_operation_result("document.tolerances",result)
        self.extension.GetUserPreferenceInteger.assert_any_call(201,110)
        self.extension.GetUserPreferenceInteger.assert_any_call(202,110)
        self.assertIs(self.app.ActiveDoc,self.foreground)
        self.assert_no_mutation()

    def test_public_writer_is_closed_including_noop_and_has_partial_receipt(self):
        for value in ("basic","none"):
            result=self.edit(value=value)
            self.assertFalse(result["ok"])
            self.assertIn("native public acceptance",result["error"]["message"])
            self.assertEqual(result["mutation"],dict(attempted=False,may_have_changed=False))
            validate_operation_result("document.tolerance-set",result)
        self.assert_no_mutation()

    def test_writer_requires_all_context_and_rejects_wire_calibration_bypass(self):
        values=dict(field="linear.type",value="basic",expected_options=self.call()["options"])
        context=dict(document_id=self.entry.document_id,expected_update_stamp=7,lease_id=self.lease)
        for key in context:
            bad=context.copy(); bad[key]=None
            with self.assertRaises(ValueError): validate_operation_request("document.tolerance-set",values,**bad)
        with self.assertRaises(ValueError):
            validate_operation_request("document.tolerance-set",dict(values,_calibration=True),**context)
        with self.assertRaises(DocumentLeaseConflict): self.call("document.tolerance-set",values,session="other")
        with self.assertRaises(DocumentUpdateConflict): self.call("document.tolerance-set",values,stamp=6)
        self.assertTrue(OPERATION_CATALOG["document.tolerance-set"].lease_guarded)
        self.assertFalse(OPERATION_CATALOG["document.tolerance-set"].temporary_activation)
        self.assert_no_mutation()

    def test_candidates_roundtrip_single_setter_and_noop_without_dirty_repair(self):
        for field,value,code in (("linear.type","basic",201),("linear.precision","4",202)):
            with self.subTest(field=field):
                self.setUp()
                with self.enabled():
                    result=self.edit(field,value)
                    self.assertTrue(result["ok"],result)
                    validate_operation_result("document.tolerance-set",result)
                    self.extension.SetUserPreferenceInteger.assert_called_once_with(code,110,1 if code==201 else 4)
                    self.assertEqual(result["mutation"],dict(attempted=True,may_have_changed=True))
                    self.extension.SetUserPreferenceInteger.reset_mock(); self.document.SetSaveFlag.reset_mock()
                    result=self.edit(field,value)
                    self.assertTrue(result["ok"],result); self.assertFalse(result["changed"])
                    validate_operation_result("document.tolerance-set",result)
                    self.assert_no_mutation()

    def test_complete_snapshot_cas_even_if_stamp_and_selected_value_match(self):
        expected=self.call()["options"]
        self.native[202]=3
        with self.enabled(): result=self.edit(expected=expected)
        self.assertFalse(result["ok"]); self.assertIn("snapshot",result["error"]["message"])
        self.assert_no_mutation()

    def test_readonly_viewonly_sketch_and_context_drift_refuse(self):
        for defect in (lambda:setattr(self.document,"IsOpenedReadOnly",lambda:True),
                       lambda:setattr(self.document,"IsOpenedViewOnly",lambda:True),
                       lambda:setattr(self.document.SketchManager,"ActiveSketch",object())):
            self.setUp(); defect()
            with self.enabled(): result=self.edit()
            self.assertFalse(result["ok"],result); self.assert_no_mutation()
        self.setUp()
        def read(p,o):
            self.app.ActiveDoc=self.document
            return self.native[p]
        expected=self.call()["options"]
        self.extension.GetUserPreferenceInteger.side_effect=read
        with self.enabled(): result=self.edit(expected=expected)
        self.assertFalse(result["ok"]); self.assert_no_mutation()

    def test_false_exception_wrong_roundtrip_and_unrequested_change_never_retry(self):
        def changed_false(p,o,v): self.native[p]=v; return False
        def throws(p,o,v): self.native[p]=v; raise RuntimeError("partial failure")
        def changes_other(p,o,v): self.native[p]=v; self.native[202]=6; return True
        for effect in (changed_false,throws,lambda p,o,v:True,changes_other):
            self.setUp(); self.extension.SetUserPreferenceInteger.side_effect=effect
            with self.enabled(): result=self.edit()
            self.assertFalse(result["ok"],result)
            self.assertEqual(result["mutation"],dict(attempted=True,may_have_changed=True))
            self.extension.SetUserPreferenceInteger.assert_called_once()
            validate_operation_result("document.tolerance-set",result)

    def test_stamp_drift_during_postsetter_observation_is_not_repaired(self):
        reads=0
        def read(p,o):
            nonlocal reads
            reads+=1
            if reads==5: self.stamp+=1
            return self.native[p]
        self.extension.GetUserPreferenceInteger.side_effect=read
        with self.enabled(): result=self.edit()
        self.assertFalse(result["ok"],result)
        self.extension.SetUserPreferenceInteger.assert_called_once()
        self.document.SetSaveFlag.assert_not_called()

    def test_bool_missing_and_mismapped_result_or_incomplete_cas_rejected(self):
        result=self.call()
        for mutate in (lambda r:r["options"].pop("linear.type"),
                       lambda r:r["options"]["linear.type"].update(native_value=1),
                       lambda r:r["options"]["linear.type"].update(native_value=True)):
            bad=deepcopy(result); mutate(bad)
            with self.assertRaises(OperationResultInvalid): validate_operation_result("document.tolerances",bad)
        for options in ({}, {"linear.type":result["options"]["linear.type"]}):
            with self.assertRaises(ValueError): self.edit(expected=options)

    def test_drawing_guard_accepts_only_normal_sheet_and_never_enters_edit_mode(self):
        for defect in (None,"format","view","foreign_sketch"):
            self.setUp()
            sheet_sketch,template_sketch=object(),object()
            sheet=SimpleNamespace(GetName=lambda:"Sheet1",GetTemplateSketch=lambda:template_sketch)
            view=SimpleNamespace(GetName2=lambda:"Sheet1",GetSketch=lambda:sheet_sketch,GetReferencedModelName=lambda:"")
            self.document.GetType=lambda:3
            self.document.GetCurrentSheet=lambda:sheet
            self.document.GetFirstView=lambda:view
            self.document.GetEditSheet=lambda: defect!="format"
            self.document.ActiveDrawingView=object() if defect=="view" else None
            self.document.SketchManager.ActiveSketch=object() if defect=="foreign_sketch" else sheet_sketch
            self.registry=DocumentRegistry(self.app)
            self.entry=self.registry.register(self.document)
            self.registry.register(self.foreground)
            self.lease=self.registry.acquire_lease(self.entry,session_id="writer",ttl_seconds=600)["lease_id"]
            with self.enabled():result=self.edit()
            self.assertEqual(result["ok"],defect is None,result)
            if defect is not None:self.assert_no_mutation()

    def test_official_constants_missing_duplicate_and_noninteger_fail_closed(self):
        import sys
        from swcli.document_tolerances import native_constants
        names=list(self.codes)
        for entries,valid in ((list(self.codes.items()),True),
                              (list(self.codes.items())[:-1],False),
                              (list(self.codes.items())+[(names[0],9)],False),
                              ([(name,True) for name in names],False)):
            info=SimpleNamespace(GetTypeAttr=lambda:SimpleNamespace(typekind=0,cVars=len(entries)),
                GetVarDesc=lambda i:SimpleNamespace(value=entries[i][1]),
                GetDocumentation=lambda descriptor:())
            # pywin32 VARDESC exposes index access plus .value.
            class Descriptor:
                def __init__(self,index):self.index=index;self.value=entries[index][1]
                def __getitem__(self,index):return self.index
            info.GetVarDesc=Descriptor
            info.GetDocumentation=lambda i:(entries[i][0],)
            library=SimpleNamespace(GetTypeInfoCount=lambda:1,GetTypeInfo=lambda i:info)
            loader=mock.Mock(return_value=library)
            native_constants.cache_clear()
            with mock.patch.dict(sys.modules,{"pythoncom":SimpleNamespace(TKIND_ENUM=0,LoadTypeLib=loader)}):
                if valid:self.assertEqual(native_constants(),self.codes)
                else:
                    with self.assertRaises(RuntimeError):native_constants()
            loader.assert_called_once()
        native_constants.cache_clear()

    def test_cli_preserves_complete_snapshot_and_guards(self):
        expected=self.call()["options"]
        args=build_parser().parse_args(["document","tolerance-set","linear.precision","4",
            "--if-options",json.dumps(expected),"--document",self.entry.document_id,
            "--lease",self.lease,"--if-update-stamp","7","--json"])
        op,values,*_= _typed_operation(args)
        self.assertEqual(op,"document.tolerance-set")
        self.assertEqual(values,dict(field="linear.precision",value="4",expected_options=expected))


if __name__=="__main__": unittest.main()
