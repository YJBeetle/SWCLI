"""Portable diagnostic-fixture checks; these do not establish native acceptance."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace, ModuleType
import unittest
from unittest import mock
from swcli.hosts.windows_dimensions import _DimensionError

ROOT = Path(__file__).resolve().parents[1]
def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/ci" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
getter = load("getter_configuration_test", "verify-native-getter-configurations.py")
stl = load("stl_configuration_trace_test", "verify-stl-options.py")


class Document:
    def __init__(self, *, values=None, readonly=False):
        self.configurations = {"A": SimpleNamespace(Name="A")}
        self.ConfigurationManager = SimpleNamespace(ActiveConfiguration=self.configurations["A"],
                                                    AddConfiguration2=self.add_configuration)
        self.values = values or {"A": .016}
        self.path, self.title, self.stamp = "", "Unsaved", 7
        self.readonly = readonly
        self.getters, self.setters, self.selections, self.rebuilds = [], [], [], []
        self.dimension = Dimension(self)
        self.SketchManager = SimpleNamespace(ActiveSketch=None)
        arc = SimpleNamespace(ConstructionGeometry=False, GetType=lambda:1, IsCircle=lambda:1,
                              GetRadius=lambda:self.values[self.ConfigurationManager.ActiveConfiguration.Name]/2,
                              GetCenterPoint2=lambda:SimpleNamespace(X=0.,Y=0.,Z=0.))
        self.native_sketch = SimpleNamespace(GetSketchSegments=lambda:(arc,))
        self.sketch_feature = SimpleNamespace(Name="Sketch", GetTypeName2=lambda:"ProfileFeature", GetSpecificFeature2=lambda:self.native_sketch)
    def GetType(self): return 1
    def GetUpdateStamp(self): return self.stamp
    def GetSaveFlag(self): return False
    def GetPathName(self): return self.path
    def GetTitle(self): return self.title
    def IsOpenedReadOnly(self): return self.readonly
    def GetConfigurationNames(self): return tuple(self.configurations)
    def EditRebuild3(self):
        self.rebuilds.append(True)
        return True
    def add_configuration(self, *args):
        assert args == ("Getter_B", "getter fixture", "", 0, "", "diagnostic only", True)
        name = args[0]
        self.configurations[name] = SimpleNamespace(Name=name)
        self.values[name] = self.values["A"]
        self.ConfigurationManager.ActiveConfiguration = self.configurations[name]
        return self.configurations[name]
    def ShowConfiguration2(self, name):
        self.selections.append(name)
        if self.ConfigurationManager.ActiveConfiguration.Name == name:
            return False
        self.ConfigurationManager.ActiveConfiguration = self.configurations[name]
        return True
    def FeatureByName(self, name):
        assert name == "Sketch"
        return self.sketch_feature
    def Parameter(self, name):
        assert name == self.dimension.FullName, "must bind saved name after rename"
        return self.dimension


class ArrayVariant:
    def __init__(self, varianttype, value):
        self.varianttype, self.value = varianttype, value


def variant_modules():
    return {"pythoncom":SimpleNamespace(VT_ARRAY=8192,VT_BSTR=8),
            "win32com":ModuleType("win32com"), "win32com.client":SimpleNamespace(VARIANT=ArrayVariant)}


class RebuildBinding:
    def __init__(self, binding, value=True, error=None):
        self.binding, self.value, self.error = binding, value, error
        self.reads = self.evaluations = 0
    def evaluate(self):
        self.evaluations += 1
        if self.error is not None:
            raise self.error
        return self.value
    @property
    def EditRebuild3(self):
        self.reads += 1
        return self.evaluate() if self.binding == "value" else self.evaluate


class Dimension:
    Name, DrivenState, ReadOnly = "D1", 2, False
    def __init__(self, document): self.document = document
    @property
    def FullName(self): return "D1@Sketch@" + self.document.title
    def GetType(self): return 0  # IDimension param type, not display-dimension enum.
    def GetSystemValue3(self, which, name):
        assert which == 3 and type(name) is str
        assert name == self.document.ConfigurationManager.ActiveConfiguration.Name
        self.document.getters.append((which, name))
        return (self.document.values[name],)
    def SetSystemValue3(self, value, which, name):
        assert name.varianttype == 8192 | 8 and tuple(name.value) == ("Getter_B",)
        self.document.setters.append((value, which, name))
        self.document.values[name.value[0]] = value
        return 0


def app_for(document):
    def identity(first, second):
        if hasattr(first, "Name") and hasattr(second, "Name") and first.Name != second.Name:
            return 2  # Unsupported is not a negative identity proof.
        return int(first is second)
    return SimpleNamespace(ActiveDoc=document, IsSame=identity, GetProcessID=lambda: 123,
                           GetDocumentCount=lambda: 0)


class GetterFixtureTests(unittest.TestCase):
    def setUp(self):
        self.stream = io.StringIO()
        self.trace = mock.patch("swcli.hosts.native_trace.sys.stderr", self.stream)
        self.trace.start(); self.addCleanup(self.trace.stop)
        self.env = mock.patch.dict(os.environ, {"SWCLI_TRACE_NATIVE_CALLS": "1"})
        self.env.start(); self.addCleanup(self.env.stop)

    def observe(self, document, app=None, record=None):
        row = {} if record is None else record
        getter.observe_current(app or app_for(document), document, document.dimension, "A", 16., row,
                               request_id="getters-saved-A", expected_native_name=document.dimension.FullName)
        return row

    def test_current_read_is_single_named_getter_without_mutation(self):
        document = Document()
        row = self.observe(document)
        self.assertTrue(row["success"])
        self.assertEqual(document.getters, [(3,"A")])
        self.assertEqual(document.setters, [])
        self.assertEqual(document.selections, [])
        self.assertEqual(row["get3_calls"][0]["values"], [.016])
        self.assertEqual(row["before"], row["after"])
        self.assertTrue(row["same_configuration_object"] and row["same_foreground_object"])

    def test_wrong_value_or_metadata_refuses_without_fallback(self):
        for kind in ("other-config-value", "scalar", "multiple", "name", "type", "driven", "readonly"):
            with self.subTest(kind=kind):
                doc = Document(); dimension = doc.dimension
                if kind == "other-config-value": doc.values["A"] = .020
                elif kind == "scalar": dimension.GetSystemValue3 = mock.Mock(return_value=.016)
                elif kind == "multiple": dimension.GetSystemValue3 = mock.Mock(return_value=(.016,.020))
                elif kind == "name": dimension.Name = "different"
                elif kind == "type": dimension.GetType = lambda: 1
                elif kind == "driven": dimension.DrivenState = 1
                else: dimension.ReadOnly = True
                with self.assertRaises(Exception): self.observe(doc)
                self.assertEqual(doc.setters, []); self.assertEqual(doc.selections, [])

    def test_stamp_config_identity_and_foreground_changes_refuse(self):
        for kind in ("stamp", "configuration-object", "foreground"):
            with self.subTest(kind=kind):
                doc = Document(); app = app_for(doc); original = doc.dimension.GetSystemValue3
                def changed(*args):
                    value = original(*args)
                    if kind == "stamp": doc.stamp += 1
                    elif kind == "configuration-object": doc.ConfigurationManager.ActiveConfiguration = SimpleNamespace(Name="A")
                    else: app.ActiveDoc = object()
                    return value
                doc.dimension.GetSystemValue3 = changed
                row = {}
                with self.assertRaisesRegex(RuntimeError, "read changed"): self.observe(doc, app, row)
                self.assertNotIn("success", row)
                self.assertEqual(doc.getters, [(3,"A")])

    def test_first_getter_exception_remains_one_attempt(self):
        doc = Document(); failure = RuntimeError("first native failure")
        doc.dimension.GetSystemValue3 = mock.Mock(side_effect=failure)
        with self.assertRaises(RuntimeError) as caught: self.observe(doc)
        self.assertIs(caught.exception, failure)
        doc.dimension.GetSystemValue3.assert_called_once_with(3,"A")
        self.assertEqual(doc.setters, []); self.assertEqual(doc.selections, [])

    def test_identity_records_exact_supported_results_and_role(self):
        for value, expected in ((0, False), (1, True)):
            with self.subTest(value=value):
                app = SimpleNamespace(IsSame=mock.Mock(return_value=value))
                row = {}
                self.assertIs(getter.same(app, object(), object(), row, "test-role"), expected)
                app.IsSame.assert_called_once()
                self.assertEqual(row["identity_checks"][0], dict(
                    role="test-role", attempted=True, return_type="int", return_value=value,
                    equality="same" if expected else "not-same"))

    def test_identity_unknown_and_invalid_results_are_durable_before_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/"report.json"
            for value in (2, True, False, None, 3, -1, 1.0, "1"):
                with self.subTest(value=value):
                    app = SimpleNamespace(IsSame=mock.Mock(return_value=value))
                    row = {}
                    def persist(): path.write_text(json.dumps(row))
                    with self.assertRaisesRegex(RuntimeError, "unreadable or unsupported"):
                        getter.same(app, object(), object(), row, "required-positive", persist=persist)
                    app.IsSame.assert_called_once()
                    saved = json.loads(path.read_text())["identity_checks"][0]
                    self.assertEqual(saved["return_type"], type(value).__name__)
                    self.assertEqual(saved["return_value"], value)
                    self.assertEqual(saved["role"], "required-positive")
                    self.assertNotIn("same", saved)
                    self.assertNotIn("success", row)

    def test_identity_exception_is_retained_even_if_checkpoint_fails(self):
        original = ValueError("first native identity failure")
        app = SimpleNamespace(IsSame=mock.Mock(side_effect=original))
        row = {}
        def persist(): raise OSError("checkpoint failure")
        with self.assertRaises(ValueError) as caught:
            getter.same(app, object(), object(), row, "failed-comparison", persist=persist)
        self.assertIs(caught.exception, original)
        app.IsSame.assert_called_once()
        saved = row["identity_checks"][0]
        self.assertEqual(saved["exception"]["message"], "first native identity failure")
        self.assertEqual(saved["persistence_exception"]["type"], "OSError")
        self.assertNotIn("return_value", saved)

    def test_identity_checkpoint_failure_refuses_without_native_retry(self):
        app = SimpleNamespace(IsSame=mock.Mock(return_value=1))
        row = {}
        def persist(): raise OSError("checkpoint failure")
        with self.assertRaisesRegex(OSError, "checkpoint failure"):
            getter.same(app, object(), object(), row, "durability-required", persist=persist)
        app.IsSame.assert_called_once()
        self.assertEqual(row["identity_checks"][0]["return_value"], 1)

    def test_switch_never_queries_cross_configuration_negative_identity(self):
        doc = Document(); doc.configurations["B"] = SimpleNamespace(Name="B")
        app = app_for(doc); comparisons = []; native = app.IsSame
        def identity(first, second):
            comparisons.append((first, second))
            return native(first, second)
        app.IsSame = identity
        row = {}
        getter.select_fixture_configuration(app, doc, "B", lambda name, fn: fn(), row, expected_names=("A", "B"))
        self.assertTrue(row["success"] and row["same_document_before"] and row["same_document_after"])
        self.assertFalse(any(hasattr(a, "Name") and hasattr(b, "Name") and a.Name != b.Name for a,b in comparisons))
        self.assertNotIn("same_before_after_object", row)
        self.assertEqual([r["role"] for r in row["identity_checks"]],
                         ["prepared-document-vs-foreground", "foreground-across-preparation", "stable-current-configuration"])

    def test_preparation_foreground_drift_refuses_before_or_after_single_show(self):
        for phase in ("before", "after"):
            with self.subTest(phase=phase):
                doc = Document(); doc.configurations["B"] = SimpleNamespace(Name="B")
                app = app_for(doc); native = doc.ShowConfiguration2
                if phase == "before": app.ActiveDoc = Document()
                def show(name):
                    result = native(name)
                    if phase == "after": app.ActiveDoc = Document()
                    return result
                doc.ShowConfiguration2 = mock.Mock(side_effect=show)
                row = {}
                with self.assertRaisesRegex(RuntimeError, "foreground document"):
                    getter.select_fixture_configuration(app, doc, "B", lambda name, fn: fn(), row, expected_names=("A", "B"))
                self.assertEqual(doc.ShowConfiguration2.call_count, int(phase == "after"))
                self.assertNotIn("success", row)
                self.assertEqual(row["before_name"], "A")
                if phase == "after": self.assertEqual(row["after_name"], "B")

    def test_preparation_configuration_set_drift_refuses_and_retains_reads(self):
        for phase in ("before", "after"):
            for names in (("A",), ("A", "B", "C"), ("A", "A"), ("A", 1), None):
                with self.subTest(phase=phase, names=names):
                    doc = Document(); doc.configurations["B"] = SimpleNamespace(Name="B")
                    counts = []
                    def read_names():
                        counts.append(1)
                        return names if phase == "before" or len(counts) == 2 else ("A", "B")
                    doc.GetConfigurationNames = read_names
                    native = doc.ShowConfiguration2
                    doc.ShowConfiguration2 = mock.Mock(side_effect=native)
                    row = {}
                    with self.assertRaisesRegex(RuntimeError, "configuration set changed"):
                        getter.select_fixture_configuration(app_for(doc), doc, "B", lambda name, fn: fn(), row, expected_names=("A", "B"))
                    self.assertEqual(doc.ShowConfiguration2.call_count, int(phase == "after"))
                    self.assertEqual(row[phase+"_configuration_names"], getter.json_value(names))
                    self.assertNotIn("success", row)
                    if phase == "after": self.assertEqual(row["show_return_value"], True)

    def test_late_identity_failure_preserves_earlier_preparation_fields_on_disk(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/"report.json"
            for value in (0, 2, True, None, 3):
                with self.subTest(value=value):
                    doc = Document(); doc.configurations["B"] = SimpleNamespace(Name="B")
                    app = app_for(doc); native = app.IsSame
                    def identity(first, second):
                        return value if hasattr(first, "Name") else native(first, second)
                    app.IsSame = identity
                    row = {}
                    def persist(): path.write_text(json.dumps(row))
                    with self.assertRaises(RuntimeError):
                        getter.select_fixture_configuration(app, doc, "B", lambda name, fn: fn(), row,
                                                            expected_names=("A", "B"), persist=persist)
                    saved = json.loads(path.read_text())
                    self.assertEqual((saved["before_name"], saved["after_name"]), ("A", "B"))
                    self.assertEqual(saved["show_return_type"], "bool")
                    self.assertIs(saved["show_return_value"], True)
                    self.assertEqual(saved["after_configuration_names"], ["A", "B"])
                    self.assertTrue(saved["same_document_before"] and saved["same_document_after"])
                    self.assertEqual(saved["identity_checks"][-1]["return_value"], value)
                    self.assertNotIn("success", saved)

    def test_late_identity_exception_is_durable_without_losing_prior_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/"report.json"
            doc = Document(); doc.configurations["B"] = SimpleNamespace(Name="B")
            app = app_for(doc); native = app.IsSame; original = ValueError("late identity failure")
            def identity(first, second):
                if hasattr(first, "Name"): raise original
                return native(first, second)
            app.IsSame = identity
            row = {}
            def persist(): path.write_text(json.dumps(row))
            with self.assertRaises(ValueError) as caught:
                getter.select_fixture_configuration(app, doc, "B", lambda name, fn: fn(), row,
                                                    expected_names=("A", "B"), persist=persist)
            self.assertIs(caught.exception, original)
            saved = json.loads(path.read_text())
            self.assertEqual((saved["before_name"], saved["after_name"]), ("A", "B"))
            self.assertIs(saved["show_return_value"], True)
            self.assertEqual(saved["identity_checks"][-1]["exception"]["message"], "late identity failure")
            self.assertNotIn("success", saved)

    def test_read_window_required_identities_still_reject_unknown_and_invalid(self):
        for role in ("configuration", "foreground"):
            for value in (2, True, False, None, 3):
                with self.subTest(role=role, value=value):
                    doc = Document(); app = app_for(doc); count = []
                    def identity(first, second):
                        count.append(1)
                        return value if len(count) == (1 if role == "configuration" else 2) else 1
                    app.IsSame = identity
                    row = {}
                    with self.assertRaisesRegex(RuntimeError, "unreadable or unsupported"):
                        self.observe(doc, app, row)
                    self.assertEqual(doc.getters, [(3, "A")])
                    self.assertEqual(doc.selections, [])
                    self.assertEqual(row["identity_checks"][-1]["return_value"], value)
                    self.assertNotIn("success", row)

    def test_preparation_invalid_expected_set_has_zero_native_selection(self):
        for expected in (("A",), ("A", "A"), ("A", 1), ("B", "C")):
            with self.subTest(expected=expected):
                doc = Document(); row = {}
                doc.ShowConfiguration2 = mock.Mock()
                with self.assertRaisesRegex(RuntimeError, "invalid expected"):
                    getter.select_fixture_configuration(app_for(doc), doc, "A", lambda name, fn: fn(), row, expected_names=expected)
                doc.ShowConfiguration2.assert_not_called()

    def test_already_active_configuration_skips_show_and_records_unchanged_identity(self):
        doc = Document()
        doc.configurations["B"] = SimpleNamespace(Name="B")
        doc.ShowConfiguration2 = mock.Mock(return_value=False)
        record = {}
        getter.select_fixture_configuration(app_for(doc), doc, "A", lambda name, fn: fn(), record, expected_names=("A", "B"))
        doc.ShowConfiguration2.assert_not_called()
        self.assertFalse(record["show_attempted"])
        self.assertTrue(record["skipped_already_current"] and record["same_before_after_object"])
        self.assertEqual((record["before_name"], record["after_name"]), ("A", "A"))
        self.assertNotIn("show_return_value", record)
        self.assertEqual(record["after_edit_state"], dict(status="observed", active_sketch=False))

    def test_different_configuration_selects_once_and_checks_post_state(self):
        doc = Document()
        doc.configurations["B"] = SimpleNamespace(Name="B")
        original = doc.ShowConfiguration2
        doc.ShowConfiguration2 = mock.Mock(side_effect=original)
        record = {}
        getter.select_fixture_configuration(app_for(doc), doc, "B", lambda name, fn: fn(), record, expected_names=("A", "B"))
        doc.ShowConfiguration2.assert_called_once_with("B")
        self.assertEqual((record["before_name"], record["after_name"]), ("A", "B"))
        self.assertEqual((record["show_return_type"], record["show_return_value"]), ("bool", True))
        self.assertTrue(record["same_active_object"])
        self.assertNotIn("same_before_after_object", record)

    def test_false_and_invalid_returns_never_read_after_or_retry_even_if_target_became_current(self):
        for value in (False, 1, -1, None, "True"):
            with self.subTest(value=value):
                doc = Document()
                doc.configurations["B"] = SimpleNamespace(Name="B")
                def misleading(name):
                    doc.ConfigurationManager.ActiveConfiguration = doc.configurations[name]
                    return value
                doc.ShowConfiguration2 = mock.Mock(side_effect=misleading)
                record = {}
                with mock.patch.object(getter, "configuration_object", wraps=getter.configuration_object) as read_config:
                    with self.assertRaisesRegex(RuntimeError, "configuration selection failed"):
                        getter.select_fixture_configuration(app_for(doc), doc, "B", lambda name, fn: fn(), record, expected_names=("A", "B"))
                self.assertEqual(read_config.call_count, 1)
                doc.ShowConfiguration2.assert_called_once_with("B")
                self.assertEqual(record["show_return_type"], type(value).__name__)
                self.assertEqual(record["show_return_value"], value)
                self.assertNotIn("after_name", record)
                self.assertNotIn("success", record)

    def test_true_return_with_name_or_object_drift_is_rejected(self):
        for drift in ("name", "active-object", "already-active-object"):
            with self.subTest(drift=drift):
                doc = Document()
                first = doc.configurations["A"]
                target = SimpleNamespace(Name="B")
                doc.configurations["B"] = target
                doc.ShowConfiguration2 = mock.Mock(return_value=True)
                record = {}
                if drift == "name":
                    reads = [first, first, first]
                elif drift == "active-object":
                    reads = [first, target, SimpleNamespace(Name="B")]
                else:
                    target = first
                    alias = SimpleNamespace(Name="A")
                    reads = [first, alias, alias]
                with mock.patch.object(getter, "configuration_object", side_effect=reads):
                    with self.assertRaises(RuntimeError):
                        getter.select_fixture_configuration(app_for(doc), doc, target.Name, lambda name, fn: fn(), record, expected_names=("A", "B"))
                self.assertNotIn("success", record)
                self.assertLessEqual(doc.ShowConfiguration2.call_count, 1)

    def test_first_show_exception_is_retained_without_postflight_calls(self):
        doc = Document()
        doc.configurations["B"] = SimpleNamespace(Name="B")
        original = ValueError("first selection exception")
        doc.ShowConfiguration2 = mock.Mock(side_effect=original)
        record = {}
        with mock.patch.object(getter, "configuration_object", wraps=getter.configuration_object) as read_config:
            with self.assertRaises(ValueError) as caught:
                getter.select_fixture_configuration(app_for(doc), doc, "B", lambda name, fn: fn(), record, expected_names=("A", "B"))
        self.assertIs(caught.exception, original)
        self.assertEqual(read_config.call_count, 1)
        doc.ShowConfiguration2.assert_called_once_with("B")
        self.assertEqual(record["show_exception"]["type"], "ValueError")
        self.assertNotIn("after_name", record)

    def test_preparation_rebuild_accepts_value_or_callable_once(self):
        for binding in ("value", "callable"):
            with self.subTest(binding=binding):
                doc, record, calls = RebuildBinding(binding), {}, []
                def call(name, function):
                    calls.append(name)
                    return function()
                getter.rebuild_fixture(doc, "B", call, record)
                self.assertEqual((doc.reads, doc.evaluations), (1, 1))
                self.assertEqual(calls, ["prepare-rebuild-B"])
                self.assertEqual(record, dict(attempted=True, return_type="bool", return_value=True, success=True))

    def test_preparation_rebuild_false_and_invalid_values_refuse_without_retry(self):
        for binding in ("value", "callable"):
            for value in (False, 0, 1, -1, None, "True"):
                with self.subTest(binding=binding, value=value):
                    doc, record = RebuildBinding(binding, value), {}
                    with self.assertRaisesRegex(RuntimeError, "B rebuild failed"):
                        getter.rebuild_fixture(doc, "B", lambda name, function: function(), record)
                    self.assertEqual((doc.reads, doc.evaluations), (1, 1))
                    self.assertEqual(record["return_type"], type(value).__name__)
                    self.assertEqual(record["return_value"], value)
                    self.assertNotIn("success", record)

    def test_preparation_rebuild_retains_first_exception_for_either_binding(self):
        for binding in ("value", "callable"):
            with self.subTest(binding=binding):
                original = ValueError("first rebuild failure")
                doc, record = RebuildBinding(binding, error=original), {}
                with self.assertRaises(ValueError) as caught:
                    getter.rebuild_fixture(doc, "A", lambda name, function: function(), record)
                self.assertIs(caught.exception, original)
                self.assertEqual((doc.reads, doc.evaluations), (1, 1))
                self.assertEqual(record, dict(attempted=True, exception=dict(type="ValueError", message="first rebuild failure")))
                self.assertNotIn("return_value", record)

    def test_seed_passes_explicit_single_BSTR_array_once_on_original_dimension(self):
        dimension = SimpleNamespace(SetSystemValue3=mock.Mock(return_value=0))
        row = {}; calls = []
        def call(name, function): calls.append(name); return function()
        with mock.patch.dict("sys.modules", variant_modules()):
            getter.seed_fixture_configuration(dimension,.020,3,"Getter_B",call,row)
        dimension.SetSystemValue3.assert_called_once()
        value,which,argument = dimension.SetSystemValue3.call_args.args
        self.assertEqual((value,which,argument.varianttype,argument.value),(.020,3,8200,("Getter_B",)))
        self.assertEqual(calls,["prepare-B-value"])
        self.assertEqual(row["config_names"],["Getter_B"])
        self.assertTrue(row["success"])

    def test_seed_rejects_status_or_exception_once_without_fallback(self):
        for status in (False,True,1,-1,None,0.0):
            with self.subTest(status=status):
                dimension = SimpleNamespace(SetSystemValue3=mock.Mock(return_value=status));row={}
                with mock.patch.dict("sys.modules",variant_modules()):
                    with self.assertRaisesRegex(RuntimeError,"B seed write failed"):
                        getter.seed_fixture_configuration(dimension,.020,3,"Getter_B",lambda name,fn:fn(),row)
                dimension.SetSystemValue3.assert_called_once()
                self.assertEqual(row["return_type"],type(status).__name__)
                self.assertEqual(row["return_value"],status)
                self.assertNotIn("success",row)
        original = ValueError("first seed exception")
        dimension = SimpleNamespace(SetSystemValue3=mock.Mock(side_effect=original));row={}
        def persist(): raise OSError("checkpoint failure")
        with mock.patch.dict("sys.modules",variant_modules()):
            with self.assertRaises(ValueError) as caught:
                getter.seed_fixture_configuration(dimension,.020,3,"Getter_B",lambda name,fn:fn(),row,persist=persist)
        self.assertIs(caught.exception,original)
        dimension.SetSystemValue3.assert_called_once()
        self.assertEqual(row["exception"]["message"],"first seed exception")
        self.assertEqual(row["persistence_exception"]["type"],"OSError")

    def test_seed_invalid_constructed_variant_refuses_before_mutation(self):
        for kind in ("variant-type","multiple-names","wrong-name"):
            with self.subTest(kind=kind):
                def variant(vt,value):
                    return ArrayVariant(12 if kind=="variant-type" else vt,
                                        ("Getter_B","A") if kind=="multiple-names" else ("A",) if kind=="wrong-name" else value)
                modules=variant_modules();modules["win32com.client"].VARIANT=variant
                dimension=SimpleNamespace(SetSystemValue3=mock.Mock());row={}
                with mock.patch.dict("sys.modules",modules):
                    with self.assertRaisesRegex(RuntimeError,"explicit BSTR array"):
                        getter.seed_fixture_configuration(dimension,.020,3,"Getter_B",lambda name,fn:fn(),row)
                dimension.SetSystemValue3.assert_not_called()
                self.assertFalse(row["attempted"])

    def prove_geometry(self, doc, app=None, row=None, **kwargs):
        row={} if row is None else row
        getter.observe_fixture_geometry(app or app_for(doc),doc,"Sketch","A",16.,row,
                                        request_id="test-independent-circle",**kwargs)
        return row

    def test_geometry_proof_is_independent_of_all_dimension_getters_and_writes(self):
        doc=Document()
        doc.dimension.GetSystemValue3=mock.Mock(side_effect=AssertionError("Get3 forbidden"))
        doc.dimension.SetSystemValue3=mock.Mock(side_effect=AssertionError("Set3 forbidden"))
        doc.EditRebuild3=mock.Mock(side_effect=AssertionError("rebuild forbidden"))
        with mock.patch.object(getter,"_descriptor",side_effect=AssertionError("descriptor forbidden")),              mock.patch.object(getter,"save_as_native_windows",side_effect=AssertionError("save forbidden")):
            row=self.prove_geometry(doc)
        self.assertTrue(row["success"])
        self.assertEqual(row["geometry"]["actual_radius_mm"],8.)
        self.assertEqual(row["before"],row["after"])
        self.assertEqual(len(row["identity_checks"]),3)
        doc.dimension.GetSystemValue3.assert_not_called();doc.dimension.SetSystemValue3.assert_not_called()
        doc.EditRebuild3.assert_not_called()

    def test_geometry_wrong_radius_circle_shape_or_feature_stops_before_Get3(self):
        for kind in ("A-is-20","construction","partial","multiple","nan","bool-radius","center","wrong-feature","missing-feature"):
            with self.subTest(kind=kind):
                doc=Document();row={};arc=doc.native_sketch.GetSketchSegments()[0]
                if kind=="A-is-20": doc.values["A"] = .020
                elif kind=="construction": arc.ConstructionGeometry=True
                elif kind=="partial": arc.IsCircle=lambda:0
                elif kind=="multiple": doc.native_sketch.GetSketchSegments=lambda:(arc,arc)
                elif kind=="nan": arc.GetRadius=lambda:float('nan')
                elif kind=="bool-radius": arc.GetRadius=lambda:True
                elif kind=="center": arc.GetCenterPoint2=lambda:SimpleNamespace(X=.001,Y=0.,Z=0.)
                elif kind=="wrong-feature": doc.sketch_feature.Name="Other"
                else: doc.FeatureByName=lambda name:None
                with self.assertRaises((RuntimeError, _DimensionError)): self.prove_geometry(doc,row=row)
                self.assertNotIn("success",row)
                self.assertEqual(doc.getters,[]);self.assertEqual(doc.setters,[]);self.assertEqual(doc.rebuilds,[])
                if kind=="A-is-20": self.assertEqual(row["geometry"]["actual_radius_mm"],10.)

    def test_geometry_state_config_foreground_and_unknown_identity_still_refuse(self):
        for kind in ("stamp","configuration-object","foreground","readonly","unknown-identity"):
            with self.subTest(kind=kind):
                doc=Document();app=app_for(doc);arc=doc.native_sketch.GetSketchSegments()[0];native=arc.GetRadius;row={}
                def radius():
                    value=native()
                    if kind=="stamp": doc.stamp+=1
                    elif kind=="configuration-object": doc.ConfigurationManager.ActiveConfiguration=SimpleNamespace(Name="A")
                    elif kind=="foreground": app.ActiveDoc=Document()
                    elif kind=="readonly": doc.readonly=True
                    return value
                arc.GetRadius=radius
                if kind=="unknown-identity": app.IsSame=lambda a,b:2
                with self.assertRaises(RuntimeError): self.prove_geometry(doc,app,row)
                self.assertNotIn("success",row)
                self.assertEqual(doc.getters,[]);self.assertEqual(doc.setters,[])

    def test_geometry_source_hash_and_native_exception_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            source=Path(temporary)/"source.SLDPRT";source.write_bytes(b"source bytes")
            digest=__import__('hashlib').sha256(source.read_bytes()).hexdigest()
            doc=Document();row={};arc=doc.native_sketch.GetSketchSegments()[0];native=arc.GetRadius
            def changed(): source.write_bytes(b"intervening bytes");return native()
            arc.GetRadius=changed
            with self.assertRaisesRegex(RuntimeError,"changed saved bytes"):
                self.prove_geometry(doc,row=row,source_path=source,expected_sha256=digest)
            self.assertNotEqual(row["source_sha256_before"],row["source_sha256_after"])
            self.assertNotIn("success",row)
        doc=Document();row={};error=ValueError("first radius error")
        doc.native_sketch.GetSketchSegments()[0].GetRadius=mock.Mock(spec=(),side_effect=error)
        with self.assertRaises(ValueError) as caught: self.prove_geometry(doc,row=row)
        self.assertIs(caught.exception,error)
        self.assertEqual(row["feature_name"],"Sketch")
        doc.native_sketch.GetSketchSegments()[0].GetRadius.assert_called_once()

    def test_geometry_failed_seed_cannot_reach_save_or_product_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary);swconst=output/"swconst.tlb";swconst.write_bytes(b"fixture typelib")
            doc=Document();app=app_for(doc);case={};report={"host":{"process_id":123},"cases":[case]};live={}
            native=doc.dimension.SetSystemValue3
            def wrong_scope(value,which,names):
                status=native(value,which,names)
                doc.values["A"]=value
                return status
            doc.dimension.SetSystemValue3=mock.Mock(side_effect=wrong_scope)
            with mock.patch.dict("sys.modules",variant_modules()),                  mock.patch.object(getter,"SWCONST",swconst,create=True),                  mock.patch.object(getter,"read_constants",return_value={"swSpecifyConfiguration":3,"swSetValue_InSpecificConfigurations":3}),                  mock.patch.object(getter,"create_part_windows_with_handle",return_value=({"ok":True},doc)),                  mock.patch.object(getter,"create_circle_sketch_windows_with_handle",return_value=({"ok":True},doc.sketch_feature)),                  mock.patch.object(getter,"create_circle_diameter_windows_with_handle",return_value=({"ok":True},doc.dimension)),                  mock.patch.object(getter,"save_as_native_windows") as save,                  mock.patch.object(getter,"observe_current") as observe:
                with self.assertRaisesRegex(RuntimeError,"independent circle geometry mismatch"):
                    getter.calibrate_case(app,output,{},"front",False,lambda name,fn:fn(),case,report,live,profile_kind="part")
            save.assert_not_called();observe.assert_not_called();doc.dimension.SetSystemValue3.assert_called_once()
            self.assertEqual(case["observations"],[])
            self.assertEqual([r["phase"] for r in case["geometry_proofs"]],["initial-A","seed-B","seed-A"])
            saved=json.loads((output/"report.json").read_text())["cases"][0]
            self.assertEqual(saved["geometry_proofs"][-1]["geometry"]["actual_radius_mm"],10.)
            self.assertNotIn("success",saved["geometry_proofs"][-1])

    def test_saved_and_reopened_distinct_values_and_renamed_fullname(self):
        self.assert_complete_saved_fixture(Document)

    def test_saved_fixture_with_boolean_noarg_rebuild_binding(self):
        class BooleanRebuildDocument(Document):
            @property
            def EditRebuild3(self):
                self.rebuilds.append(True)
                return True
        self.assert_complete_saved_fixture(BooleanRebuildDocument)

    def assert_complete_saved_fixture(self, document_type):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary); swconst = output / "swconst.tlb"; swconst.write_bytes(b"mock typelib")
            doc = document_type(); app = app_for(doc); documents = [doc]; live = {}; case = {}; report = {"host":{"process_id":123}, "cases":[case]}
            def save(path, *, document):
                Path(path).write_bytes(b"saved fixture")
                document.path, document.title = path, "two-configurations.SLDPRT"
                return dict(ok=True, api_saved=True, save_errors=0, save_warnings=0)
            def reopen(path, **kwargs):
                opened = document_type(values=doc.values.copy(), readonly=True)
                opened.configurations["Getter_B"] = SimpleNamespace(Name="Getter_B")
                opened.path, opened.title = path, doc.title
                documents.append(opened); app.ActiveDoc = opened
                return dict(ok=True, read_only=True, api_errors=0, api_warnings=0), opened
            app.CloseDoc = lambda title: None
            with mock.patch.dict("sys.modules", variant_modules()), \
                    mock.patch.object(getter,"SWCONST",swconst,create=True), \
                    mock.patch.object(getter,"read_constants",return_value={"swSpecifyConfiguration":3,"swSetValue_InSpecificConfigurations":3}), \
                    mock.patch.object(getter,"create_part_windows_with_handle",return_value=({"ok":True},doc)), \
                    mock.patch.object(getter,"create_circle_sketch_windows_with_handle",return_value=({"ok":True},doc.sketch_feature)), \
                    mock.patch.object(getter,"create_circle_diameter_windows_with_handle",return_value=({"ok":True},doc.dimension)), \
                    mock.patch.object(getter,"save_as_native_windows",side_effect=save), \
                    mock.patch.object(getter,"open_windows_document_with_handle",side_effect=reopen):
                getter.calibrate_case(app,output,{},"front",False,lambda name, fn:fn(),case,report,live,profile_kind="part")
            self.assertTrue(case["success"])
            saved_report = json.loads((output/"report.json").read_text())
            self.assertEqual(saved_report["native_call_worker_pid"], os.getpid())
            self.assertEqual(len(saved_report["cases"][0]["observations"]), 4)
            self.assertEqual(saved_report["cases"][0]["observations"][-1]["identity_checks"][-1]["return_value"], 1)
            self.assertEqual(doc.rebuilds, [True, True])
            self.assertEqual(case["rebuild_preparation"], [
                dict(label=label, attempted=True, return_type="bool", return_value=True, success=True)
                for label in ("B", "A")])
            self.assertEqual(documents[1].rebuilds, [])
            self.assertEqual(case["after_dimension_creation_edit_state"], dict(status="observed", active_sketch=False))
            self.assertEqual(case["preparation_complete_edit_state"], dict(status="observed", active_sketch=False))
            self.assertEqual(len(case["configuration_preparation"]), 6)
            self.assertEqual(sum(row["show_attempted"] for row in case["configuration_preparation"]), 3)
            self.assertEqual(case["configuration_preparation"][0]["before_name"], "Getter_B")
            self.assertFalse(case["configuration_preparation"][0]["show_attempted"])
            self.assertNotEqual(case["native_name"],case["unsaved_native_name"])
            self.assertEqual([d.getters for d in documents], [[(3,"A"),(3,"Getter_B")]]*2)
            self.assertEqual(len(doc.setters),1)
            self.assertEqual(doc.setters[0][:2],(.020,3))
            self.assertEqual((doc.setters[0][2].varianttype,doc.setters[0][2].value),(8200,("Getter_B",)))
            self.assertEqual([row["geometry"]["actual_radius_mm"] for row in case["geometry_proofs"]], [8.,10.,8.,8.,10.,8.,10.])
            self.assertEqual(documents[1].setters,[])
            self.assertEqual(case["saved_sha256"],case["final_sha256"])
            self.assertIsNone(live["document"])
            trace = output / "stderr.log"; trace.write_text(self.stream.getvalue())
            proof = getter.audit_read_trace(trace,case["observations"],os.getpid())
            self.assertEqual(len(proof),4)
            self.assertEqual(len(getter.audit_geometry_trace(trace,case["geometry_proofs"],os.getpid())),7)
            with self.assertRaisesRegex(RuntimeError,"seven independent"):
                getter.audit_geometry_trace(trace,case["geometry_proofs"][:-1],os.getpid())
            with self.assertRaisesRegex(RuntimeError,"worker/request"):
                getter.audit_geometry_trace(trace,case["geometry_proofs"],999)
            trace.write_text(self.stream.getvalue().replace('"call": "GetRadius"','"call": "IDimension.GetSystemValue3"'))
            with self.assertRaisesRegex(RuntimeError,"geometry proof contains"):
                getter.audit_geometry_trace(trace,case["geometry_proofs"],os.getpid())
            trace.write_text(self.stream.getvalue())
            with self.assertRaisesRegex(RuntimeError,"correlation"): getter.audit_read_trace(trace,case["observations"],999)
            with self.assertRaisesRegex(RuntimeError,"four distinct"): getter.audit_read_trace(trace,case["observations"][:3],os.getpid())
            bad = self.stream.getvalue().replace('"call": "IDimension.GetSystemValue3"','"call": "ShowConfiguration2"')
            trace.write_text(bad)
            with self.assertRaisesRegex(RuntimeError,"mutation"): getter.audit_read_trace(trace,case["observations"],os.getpid())

    def test_installed_constants_fail_closed_for_missing_duplicate_or_mismatch(self):
        def library(items):
            class Var(tuple):
                def __new__(cls,index,value):
                    obj=tuple.__new__(cls,(index,)); obj.value=value; return obj
            info=SimpleNamespace(GetTypeAttr=lambda:SimpleNamespace(typekind=0,cVars=len(items)),
                GetVarDesc=lambda index:Var(index,items[index][1]), GetDocumentation=lambda index:(items[index][0],))
            return SimpleNamespace(TKIND_ENUM=0,LoadTypeLib=lambda path:SimpleNamespace(GetTypeInfoCount=lambda:1,GetTypeInfo=lambda index:info))
        good=[("swSpecifyConfiguration",3),("swSetValue_InSpecificConfigurations",3),("swDimensionParamTypeDoubleLinear",0),
              ("swObjectNotSame",0),("swObjectSame",1),("swObjectUnsupported",2)]
        self.assertEqual(getter.read_constants(library(good),"mock"),dict(good))
        for values in (good[:-1],good+[good[0]],[(good[0][0],1)]+good[1:],[(good[0][0],True)]+good[1:],
                       good[:-1]+[("swObjectUnsupported",3)], good[:-2]+[("swObjectSame",True)]+good[-1:]):
            with self.assertRaises(RuntimeError): getter.read_constants(library(values),"mock")

    def test_successful_worker_without_geometry_trace_cannot_pass_supervisor(self):
        with tempfile.TemporaryDirectory() as temporary:
            args=SimpleNamespace(output_dir=Path(temporary)/"evidence",swconst=Path(temporary)/"swconst")
            worker=mock.Mock(returncode=0,pid=123);worker.poll.return_value=0
            def launch(*values,**options):
                report=dict(success=True,cleanup_errors=[],cases=[dict(observations=[],geometry_proofs=[])])
                (args.output_dir/"report.json").write_text(json.dumps(report))
                return worker
            with mock.patch.object(getter.subprocess,"Popen",side_effect=launch),                  mock.patch.object(getter,"audit_read_trace",return_value=[dict(request_id="read-proof")]),                  mock.patch.object(getter,"audit_geometry_trace",side_effect=RuntimeError("geometry proof absent")):
                self.assertEqual(getter.supervise(args),1)
            receipt=json.loads((args.output_dir/"supervisor.json").read_text())
            self.assertFalse(receipt["success"] or receipt["cleanup_proven"])
            self.assertEqual(receipt["failure"],"geometry proof absent")
            worker.terminate.assert_not_called()

    def test_budgets_and_failed_worker_cannot_claim_cleanup(self):
        self.assertIn("600",getter.deadline_reason([],600,600,0))
        self.assertIsNone(getter.deadline_reason([{"time":1}],600,600,0))
        self.assertIn("1800",getter.deadline_reason([],1800,1,0))
        with tempfile.TemporaryDirectory() as temporary:
            args=SimpleNamespace(output_dir=Path(temporary)/"evidence",swconst=Path(temporary)/"swconst")
            worker=mock.Mock(returncode=1,pid=999); worker.poll.return_value=1
            with mock.patch.object(getter.subprocess,"Popen",return_value=worker) as launch:
                self.assertEqual(getter.supervise(args),1)
            launch.assert_called_once(); worker.terminate.assert_not_called()
            receipt=json.loads((args.output_dir/"supervisor.json").read_text())
            self.assertFalse(receipt["success"] or receipt["cleanup_proven"])


class StlModernTraceTests(unittest.TestCase):
    def rows(self,calls):
        return [dict(request_id="req",operation="document.export",worker_pid=123,event="swcli.native-call",
                     sequence=i,call=call,phase=phase) for i,call in enumerate(calls) for phase in ("begin","end")]
    def proof(self,rows):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/"trace.log"
            path.write_text("".join(json.dumps(row)+"\n" for row in rows))
            return stl.configuration_trace_proof(path,"req")
    def test_modern_before_and_after_are_correlated_complete_triples(self):
        self.assertEqual(self.proof(self.rows(["ConfigurationManager","ActiveConfiguration","Name"]*2))["modern_configuration_triples"],2)
    def test_obsolete_partial_failed_wrong_worker_and_interleaved_reads_refuse(self):
        valid=self.rows(["ConfigurationManager","ActiveConfiguration","Name"]*2)
        variants=[valid[:-1],self.rows(["GetActiveConfiguration"]),self.rows(["ConfigurationManager","ActiveConfiguration","Name"]),
                  self.rows(["ConfigurationManager","SomeOtherCall","ActiveConfiguration","Name"]*2)]
        for key,value in (("phase","error"),("request_id","another"),("worker_pid",456)):
            copied=[dict(r) for r in valid];copied[-1][key]=value;variants.append(copied)
        for rows in variants:
            with self.subTest(rows=rows):
                with self.assertRaises(RuntimeError):self.proof(rows)


if __name__ == "__main__": unittest.main()
