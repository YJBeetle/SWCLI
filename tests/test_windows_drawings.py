"""Portable adapter guards; native proof is a separate CI gate."""
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
from unittest.mock import Mock, patch
from swcli.hosts import windows_drawings as drawing


class DrawingTests(unittest.TestCase):
    def test_created_native_shape_passes_result_contract(self):
        from swcli.result_schemas import validate_operation_result
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "fixture.drwdot"
            path.write_bytes(b"fixture")
            sheet = NS(SetProperties2=Mock())
            doc = NS(ForceRebuild3=lambda flag: True)
            state = dict(name="Sheet1", properties=[6,12,1,1,1,.297,.21,1], unit="meter",
                format_path="", format_available=False, projection="first-angle")
            def observe(document, result):
                result.update(sheet=state.copy(), views=[])
            diagnostic = dict(healthy=True, issues=[], issue_count=0, scanned_feature_count=0, truncated=False, limit=500)
            with patch.object(drawing, "_active"), patch.object(drawing, "_empty_target", side_effect=observe), patch.object(drawing, "_observe", side_effect=observe), patch.object(drawing, "_sheet", return_value=(sheet,state)), patch.object(drawing, "_healthy", return_value=diagnostic), patch.object(drawing, "_describe_document", return_value=dict(title="Drawing",path="",type=3,modified=True,update_stamp=1)):
                result, handle = drawing.create_drawing_windows_with_handle(app=NS(NewDocument=lambda *args:doc), template=str(path), projection="first-angle")
            self.assertTrue(result["ok"], result)
            validate_operation_result("document.create", result)

    def test_bad_template_does_not_create(self):
        app = Mock()
        result, handle = drawing.create_drawing_windows_with_handle(app=app, template="missing.drwdot", projection="first-angle")
        self.assertFalse(result["ok"])
        self.assertIsNone(handle)
        app.NewDocument.assert_not_called()

    def test_handle_retained_after_creation_failure(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "fixture.drwdot"
            path.write_bytes(b"fixture")
            handle = object()
            app = NS(NewDocument=Mock(return_value=handle))
            with patch.object(drawing, "_describe_document", return_value={}), patch.object(drawing, "_active", side_effect=RuntimeError("wrong active")):
                result, actual = drawing.create_drawing_windows_with_handle(app=app, template=str(path), projection="first-angle")
            self.assertFalse(result["ok"])
            self.assertIs(actual, handle)
            app.NewDocument.assert_called_once_with(str(path.resolve()), 6, 0.0, 0.0)

    def test_unsafe_target_stops_before_source_or_mutation(self):
        app = NS(ActiveDoc=object(), IsSame=lambda a,b: 0)
        source = Mock()
        result = drawing.insert_standard_views_windows(app=app, document=Mock(), source_document=source, configuration="Default")
        self.assertFalse(result["ok"])
        self.assertFalse(result["mutation"]["attempted"])
        source.assert_not_called()

    def test_short_properties_are_rejected(self):
        with patch.object(drawing, "_get", side_effect=[object(), [6]]):
            with self.assertRaisesRegex(RuntimeError, "length"):
                drawing._sheet(object())

    def test_readonly_target_is_refused_before_views(self):
        doc = NS(GetType=3, IsOpenedReadOnly=True)
        with patch.object(drawing, "_observe") as observe:
            with self.assertRaisesRegex(RuntimeError, "writable"):
                drawing._empty_target(doc, {})
            observe.assert_not_called()

    def test_unknown_edit_mode_is_not_clean(self):
        doc = NS(GetType=3, IsOpenedReadOnly=False, IsOpenedViewOnly=False, GetEditSheet=None)
        with self.assertRaisesRegex(RuntimeError, "editing mode"):
            drawing._empty_target(doc, {})

    def test_unknown_source_stamp_is_not_clean(self):
        doc = NS(GetPathName="part.sldprt", GetType=1, GetSaveFlag=False, GetUpdateStamp=None,
            Extension=NS(NeedsRebuild2=0), ConfigurationManager=NS(ActiveConfiguration=NS(Name="Default")))
        with self.assertRaisesRegex(RuntimeError, "state unavailable"):
            drawing._source(doc)

    def test_insertion_failure_keeps_first_error_and_partial_evidence(self):
        source = dict(path="source", type=1, modified=False, update_stamp=1, needs_rebuild=0, configuration="Default")
        doc = NS(Create1stAngleViews2=Mock(return_value=False))
        def empty(document, result):
            result["sheet"] = dict(projection="first-angle")
        with patch.object(drawing, "_active"), patch.object(drawing, "_empty_target", side_effect=empty), patch.object(drawing, "_source", return_value=source), patch.object(drawing.Path, "is_file", return_value=True), patch.object(drawing, "_healthy"), patch.object(drawing, "_get", side_effect=[NS(), None]), patch.object(drawing, "_observe", side_effect=RuntimeError("cleanup")):
            result = drawing.insert_standard_views_windows(app=NS(), document=doc, source_document=NS(), configuration="Default")
        self.assertFalse(result["ok"])
        self.assertIn("do not retry", result["error"]["message"])
        self.assertTrue(result["mutation"]["may_have_changed"])
        self.assertEqual(result["cleanup_errors"][0]["stage"], "observe-partial-drawing")
        doc.Create1stAngleViews2.assert_called_once()


if __name__ == "__main__":
    unittest.main()
