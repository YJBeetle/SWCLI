"""Portable control tests only. These fake objects are NOT native SW evidence."""
import copy
import importlib.util
import json
import io
import os
import sys
from contextlib import contextmanager, nullcontext, redirect_stderr
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(os.environ.get("SWCLI_CALIBRATION_PROJECT", str(PROJECT_ROOT)))
if str(PACKAGE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT / "src"))
SOURCE = Path(os.environ.get("SWCLI_CALIBRATION_SCRIPT", str(PROJECT_ROOT / "scripts/dev/calibrate-document-properties.py")))
spec = importlib.util.spec_from_file_location("docprops_calibration_portable", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Calibration = module.Calibration

FONT = dict(zip(module.FONT_MEMBERS, [
    "Original Face", .0035, 12, False, False, False, False, False, False, False,
    1.0, 1.0, 0.0, .0015, 0.0, 0.0, False]))
DISPLAY = {key: False if family == "Toggle" else .01 if family == "Double" else 7
           for key, (family, preference, scope) in module.DISPLAY.items()}


class Doc:
    def __init__(self, title="swcli-test-doc", path=""):
        self.title, self.path, self.dirty, self.fail_title = title, path, False, False
        self.kind, self.readonly, self.viewonly = 1, False, False
        self.stamp, self.configuration, self.edit_token = 7, "Default", "normal"
        self.property_changes_state = False
        self.font, self.display = copy.deepcopy(FONT), copy.deepcopy(DISPLAY)
        self.annotations = {key: True if family == "Toggle" else .00635 if family == "Double" else 1
                            for key, (family, preference, option) in module.ANNOTATIONS.items()}
        self.standard = 7
        self.events = []
        self.live_property = False
        self.final_return = True
        self.scalar_return = True
        self.extension = Extension(self)

    def GetTitle(self):
        if self.fail_title:
            raise RuntimeError("title observation failed")
        return self.title

    def GetPathName(self):
        return self.path

    def GetType(self):
        return self.kind

    def IsOpenedReadOnly(self):
        return self.readonly

    def IsOpenedViewOnly(self):
        return self.viewonly

    def GetSaveFlag(self):
        return self.dirty

    def SetSaveFlag(self):
        self.events.append("save-flag")
        self.dirty = True

    @property
    def Extension(self):
        return self.extension


class Format:
    def __init__(self, document):
        object.__setattr__(self, "document", document)
        object.__setattr__(self, "values", copy.deepcopy(document.font))

    def __getattr__(self, member):
        if member in self.values:
            return self.values[member]
        raise AttributeError(member)

    def __setattr__(self, member, value):
        self.document.events.append("property:" + member)
        self.values[member] = value
        if member == "CharHeight":
            self.values["IsHeightSpecifiedInPts"] = False
        if member == "CharHeightInPts":
            self.values["IsHeightSpecifiedInPts"] = True
        if self.document.live_property:
            self.document.font = copy.deepcopy(self.values)
        if self.document.property_changes_state:
            self.document.stamp += 1
            self.document.dirty = True


class Extension:
    def __init__(self, document):
        self.document = document
        self.pref_keys = {}

    def GetUserPreferenceTextFormat(self, *args):
        self.document.events.append("independent-get")
        return Format(self.document)

    def SetUserPreferenceTextFormat(self, pref, option, format_object):
        self.document.events.append("final-set")
        self.document.font = copy.deepcopy(format_object.values)
        return self.document.final_return

    def _set(self, pref, option, target):
        self.document.events.append("scalar-set")
        self.document.display[self.pref_keys[pref]] = target
        return self.document.scalar_return

    SetUserPreferenceToggle = _set
    SetUserPreferenceInteger = _set
    SetUserPreferenceDouble = _set


class App:
    def __init__(self, documents):
        self.docs = list(documents)
        self.pid, self.UserControl, self.Visible = 2940, True, True
        self.ActiveDoc = None
        self.closed, self.noop_close = [], False

    def GetProcessID(self):
        return self.pid

    def GetDocuments(self):
        return list(self.docs) or None

    def GetDocumentCount(self):
        return len(self.docs)

    def CloseDoc(self, title):
        self.closed.append(title)
        if not self.noop_close:
            self.docs = [document for document in self.docs if document.title != title]


def fixture(documents=()):
    c = Calibration.__new__(Calibration)
    c.args = SimpleNamespace(attach_pid=2940, stage="fonts", font_typeface="Arial", isolated_host=False)
    c.app = App(documents)
    c.originals, c.live, c.original_foreground = [], [], None
    c.constants = {"swDetailingAnnotationTextFormat": 19, "swDetailingNoOptionSpecified": 0}
    for index, (key, (family, preference, scope)) in enumerate(module.DISPLAY.items()):
        c.constants[preference] = 1000 + index
        for document in documents:
            document.extension.pref_keys[1000 + index] = key
    c.virtual_values = [0, 1, 2, 3, 4]
    c.report = {"success": False, "cleanup_errors": [], "file_hashes": {}, "source_files": {},
                "existing_process_ids": [2940, 6668], "reads": {}, "visibility_before": True}
    c.persist = lambda: None
    c.call = lambda label, function: function()
    c.com_value = lambda obj, name: getattr(obj, name)() if callable(getattr(obj, name)) else getattr(obj, name)
    c.native_same = lambda app, first, second: first is second
    c.native_state = lambda doc: (doc.kind, doc.stamp, doc.dirty, doc.configuration)
    c.edit_context = lambda doc: {"mode": doc.edit_token}
    def verify_context(app, doc, context):
        module.require(context == {"mode": doc.edit_token}, "original edit context drifted")
    c.verify_context = verify_context
    c.writable_context = lambda app, context: context == {"mode": "normal"}
    c.original_invariants = lambda label, foreground=False: None
    c.templates = lambda label: {}
    c.restore = lambda label: None
    c.trusted, c.cleanup_mode, c.restore_failed = True, False, False
    c.started = module.time.monotonic()
    c.writable = Calibration.writable.__get__(c, Calibration)
    c.changed_context = Calibration.changed_context.__get__(c, Calibration)

    def observe(doc, kind, foreground, label):
        if c.app.ActiveDoc is None and foreground is not None:
            c.app.ActiveDoc = foreground
        doc.events.append("observe:" + label)
        return {"font": copy.deepcopy(doc.font), "display": copy.deepcopy(doc.display),
                "annotations": copy.deepcopy(doc.annotations), "standard": doc.standard,
                "state": list(c.native_state(doc))}
    c.observe = observe
    c.read_font = lambda doc, label: (doc.extension.GetUserPreferenceTextFormat(), copy.deepcopy(doc.font))
    return c


class ExactRotBinding(unittest.TestCase):
    """Fake ROT only: no native enumeration or COM activation."""

    def rot_fixture(self, names, actual_pid=2940):
        c = fixture()
        events = []
        app = App([])
        app.pid = actual_pid
        class Moniker:
            def __init__(self, name):
                self.name = name
            def GetDisplayName(self, context, reserved):
                events.append(("name", self.name))
                return self.name
        monikers = [Moniker(name) for name in names]
        pending = iter(monikers)
        def next_one(count):
            self.assertEqual(count, 1)
            item = next(pending, None)
            events.append(("next", None if item is None else item.name))
            return () if item is None else (item,)
        def query(iid):
            events.append(("query", iid))
            self.assertEqual(iid, "IDispatch")
            return app
        def get_object(moniker):
            events.append(("bind", moniker.name))
            return SimpleNamespace(QueryInterface=query)
        def dispatch(value):
            events.append(("dispatch", value))
            self.assertIs(value, app)
            return value
        rot = SimpleNamespace(EnumRunning=lambda: SimpleNamespace(Next=next_one), GetObject=get_object)
        c.pythoncom = SimpleNamespace(GetRunningObjectTable=lambda: rot, CreateBindCtx=lambda reserved: object(), IID_IDispatch="IDispatch")
        # No GetActiveObject or ProgID fallback is available in this fake client.
        c.client = SimpleNamespace(Dispatch=dispatch)
        c.app = None
        return c, app, events

    def test_unique_exact_moniker_binds_only_after_complete_enumeration(self):
        c, app, events = self.rot_fixture(["SolidWorks_PID_6668", "unrelated", "SolidWorks_PID_2940"])
        self.assertIs(c.attach_rot(), app)
        self.assertLess(events.index(("next", None)), events.index(("bind", "SolidWorks_PID_2940")))
        self.assertEqual([e for e in events if e[0] == "bind"], [("bind", "SolidWorks_PID_2940")])
        self.assertEqual(sum(e[0] == "query" for e in events), 1)
        self.assertEqual(sum(e[0] == "dispatch" for e in events), 1)
        self.assertTrue(c.report["rot_binding"]["identity_verified"])
        self.assertEqual(c.report["actual_attach_pid"], 2940)

    def test_missing_and_out_of_scope_monikers_never_bind(self):
        names = ["SolidWorks_PID_6668", "SolidWorks_PID_29400", "!SolidWorks_PID_2940", "solidworks_PID_2940", "SolidWorks_PID_2940/suffix", "SldWorks.Application"]
        for candidates in ([], names):
            with self.subTest(candidates=candidates):
                c, app, events = self.rot_fixture(candidates)
                with self.assertRaisesRegex(RuntimeError, "exactly once"):
                    c.attach_rot()
                self.assertFalse(any(e[0] in ("bind", "query", "dispatch") for e in events))
                self.assertEqual(c.report["rot_binding"]["observed_monikers"], candidates)
                self.assertFalse(c.report["rot_binding"]["binding_attempted"])

    def test_duplicate_exact_monikers_never_bind(self):
        c, app, events = self.rot_fixture(["SolidWorks_PID_2940", "SolidWorks_PID_2940"])
        with self.assertRaisesRegex(RuntimeError, "exactly once"):
            c.attach_rot()
        self.assertEqual(c.report["rot_binding"]["matching_moniker_count"], 2)
        self.assertFalse(any(e[0] in ("bind", "query", "dispatch") for e in events))

    def test_exact_name_with_wrong_actual_pid_fails_without_fallback(self):
        for pid in (6668, True, "2940"):
            with self.subTest(pid=pid):
                c, app, events = self.rot_fixture(["SolidWorks_PID_2940"], pid)
                with self.assertRaisesRegex(RuntimeError, "PID mismatch"):
                    c.attach_rot()
                self.assertEqual(sum(e[0] == "bind" for e in events), 1)
                self.assertEqual(sum(e[0] == "dispatch" for e in events), 1)
                self.assertIsNone(c.app)
                self.assertFalse(c.report["rot_binding"]["identity_verified"])
                self.assertEqual(c.report["actual_attach_pid"], pid)

    def test_display_name_failure_stops_before_binding_even_after_match(self):
        c, app, events = self.rot_fixture(["SolidWorks_PID_2940", None])
        with self.assertRaisesRegex(RuntimeError, "display name"):
            c.attach_rot()
        self.assertFalse(any(e[0] == "bind" for e in events))

    def test_query_interface_failure_has_no_dispatch_or_fallback(self):
        c, app, events = self.rot_fixture(["SolidWorks_PID_2940"])
        def fail(moniker):
            events.append(("bind-failed-interface", moniker.name))
            return SimpleNamespace(QueryInterface=lambda iid: (_ for _ in ()).throw(RuntimeError("no dispatch interface")))
        c.pythoncom.GetRunningObjectTable().GetObject = fail
        with self.assertRaisesRegex(RuntimeError, "no dispatch interface"):
            c.attach_rot()
        self.assertEqual(sum(e[0] == "bind-failed-interface" for e in events), 1)
        self.assertFalse(any(e[0] == "dispatch" for e in events))

    def test_missing_process_fails_before_rot_enumeration(self):
        c, app, events = self.rot_fixture(["SolidWorks_PID_2940"])
        with patch.object(module, "process_ids", return_value=[6668]):
            with self.assertRaisesRegex(RuntimeError, "not running"):
                c.attach()
        self.assertEqual(events, [])


class IsolatedHostProcessPolicy(unittest.TestCase):
    def cleanup_fixture(self, isolated, remaining):
        c = fixture()
        c.args.isolated_host = isolated
        c.trusted = False
        c.report["success"] = True
        c.trace = SimpleNamespace(close=lambda: None)
        with patch.object(module, "process_ids", return_value=remaining):
            c.cleanup()
        return c

    def test_isolated_other_exit_and_start_are_actual_observations(self):
        c = self.cleanup_fixture(True, [2940, 7777])
        self.assertTrue(c.report["success"])
        self.assertFalse(c.report["existing_process_ids_preserved"])
        self.assertTrue(c.report["manual_host_still_running"])
        self.assertEqual(c.report["cleanup_errors"], [])
        self.assertEqual(c.report["process_changes"], {
            "exited_process_ids": [6668], "started_process_ids": [7777],
            "other_exited_process_ids": [6668], "other_started_process_ids": [7777]})

    def test_target_exit_fails_in_both_modes(self):
        for isolated in (False, True):
            with self.subTest(isolated=isolated):
                c = self.cleanup_fixture(isolated, [6668, 7777])
                self.assertFalse(c.report["success"])
                self.assertFalse(c.report["manual_host_still_running"])
                self.assertEqual(c.report["process_changes"]["exited_process_ids"], [2940])
                self.assertEqual(c.report["process_changes"]["other_exited_process_ids"], [])
                self.assertIn("target host process missing", c.report["cleanup_errors"][0]["error"])

    def test_default_shared_mode_still_requires_other_preexisting_process(self):
        c = self.cleanup_fixture(False, [2940])
        self.assertFalse(c.report["success"])
        self.assertIn("preexisting host process missing", c.report["cleanup_errors"][0]["error"])

    def test_shared_mode_keeps_previous_permission_for_new_process(self):
        c = self.cleanup_fixture(False, [2940, 6668, 7777])
        self.assertTrue(c.report["success"])
        self.assertEqual(c.report["process_changes"]["other_started_process_ids"], [7777])

    def test_isolation_flag_default_and_explicit_parse(self):
        base = ["calibrate", "--attach-pid", "2940", "--stage", "read"]
        with patch.object(sys, "argv", base):
            self.assertFalse(module.arguments().isolated_host)
        with patch.object(sys, "argv", base + ["--isolated-host"]):
            self.assertTrue(module.arguments().isolated_host)

    def test_isolated_hidden_target_keeps_false_visibility_without_setting_it(self):
        c = fixture()
        c.args.isolated_host = True
        c.app.Visible = False
        c.report["visibility_before"] = False
        c.report["global_templates_before"] = {}
        Calibration.original_invariants(c, "isolated-hidden", foreground=True)
        self.assertIs(c.app.Visible, False)
        self.assertIs(c.app.UserControl, True)
        self.assertEqual(c.app.closed, [])

    def test_isolated_does_not_relax_target_visibility_or_user_control(self):
        for member, value, error in (("Visible", False, "visibility changed"), ("UserControl", False, "UserControl changed")):
            with self.subTest(member=member):
                c = fixture()
                c.args.isolated_host = True
                setattr(c.app, member, value)
                with self.assertRaisesRegex(RuntimeError, error):
                    Calibration.original_invariants(c, "isolated-test")


class Lifecycle(unittest.TestCase):
    def test_registration_keeps_native_before_metadata_failure(self):
        doc = Doc()
        doc.fail_title = True
        c = fixture([doc])
        with self.assertRaisesRegex(RuntimeError, "title observation"):
            c.register(doc, "new-target")
        self.assertEqual(len(c.live), 1)
        self.assertIs(c.live[0]["document"], doc)
        self.assertIsNone(c.live[0]["title"])

    def test_close_empty_title_never_calls_CloseDoc(self):
        doc = Doc("")
        c = fixture([doc])
        c.live = [{"identity": "test", "document": doc, "title": "", "close_attempted": False}]
        with self.assertRaisesRegex(RuntimeError, "empty"):
            c.close(doc, "test")
        self.assertEqual(c.app.closed, [])

    def test_close_pid_mismatch_never_calls_CloseDoc(self):
        doc = Doc()
        c = fixture([doc])
        c.register(doc, "test")
        c.app.pid = 6668
        with self.assertRaisesRegex(RuntimeError, "PID mismatch"):
            c.close(doc, "test")
        self.assertEqual(c.app.closed, [])
        self.assertEqual(len(c.live), 1)

    def test_close_requires_user_control(self):
        doc = Doc()
        c = fixture([doc])
        c.register(doc, "test")
        c.app.UserControl = False
        with self.assertRaisesRegex(RuntimeError, "user-controlled"):
            c.close(doc, "test")
        self.assertEqual(c.app.closed, [])

    def test_close_noop_retains_registry_and_cleanup_does_not_retry(self):
        doc = Doc()
        c = fixture([doc])
        c.register(doc, "test")
        c.app.noop_close = True
        with self.assertRaisesRegex(RuntimeError, "count"):
            c.close(doc, "test")
        self.assertEqual(len(c.live), 1)
        self.assertTrue(c.live[0]["close_attempted"])
        old = module.process_ids
        module.process_ids = lambda: [2940, 6668]
        c.trace = SimpleNamespace(close=lambda: None)
        try:
            c.cleanup()
        finally:
            module.process_ids = old
        self.assertEqual(c.app.closed, [doc.title])
        self.assertEqual(len(c.live), 1)
        self.assertIn("no retry", c.report["cleanup_errors"][0]["error"])

    def test_close_success_verifies_then_removes_registry(self):
        doc = Doc()
        c = fixture([doc])
        c.register(doc, "test")
        c.close(doc, "test")
        self.assertEqual(c.app.closed, [doc.title])
        self.assertEqual(c.live, [])

    def test_preexisting_identity_and_title_collision_are_never_closed(self):
        original, test = Doc("same-title"), Doc("same-title")
        c = fixture([original, test])
        c.originals = [{"identity": "original", "document": original}]
        c.register(test, "test")
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            c.close(test, "test")
        self.assertEqual(c.app.closed, [])
        self.assertIn(original, c.app.docs)

    def test_budget_produces_one_terminal_and_preserves_first_failure(self):
        c = fixture()
        c.call = Calibration.call.__get__(c, Calibration)
        c.started = 0
        now = [0]
        events = []
        c.event = events.append
        old = module.time.monotonic
        module.time.monotonic = lambda: now[0]
        try:
            def overrun():
                now[0] = 601
            with self.assertRaisesRegex(RuntimeError, "600-second"):
                c.call("native-once", overrun)
            first = copy.deepcopy(c.report["first_call_failure"])
            c.cleanup_mode = True
            with self.assertRaisesRegex(RuntimeError, "cleanup failure"):
                c.call("cleanup-once", lambda: (_ for _ in ()).throw(RuntimeError("cleanup failure")))
            self.assertEqual(c.report["first_call_failure"], first)
        finally:
            module.time.monotonic = old
        self.assertEqual([row["phase"] for row in events[:2]], ["begin", "error"])
        self.assertEqual(len([row for row in events if row["call"] == "native-once"]), 2)


class WriteControl(unittest.TestCase):
    def test_font_live_and_detached_each_have_seven_individual_roundtrips(self):
        for live_property in (False, True):
            with self.subTest(live_property=live_property):
                doc = Doc()
                doc.live_property = live_property
                c = fixture([doc])
                snapshots = []
                def roundtrip(document, kind, front, expected, row, label, continue_writable, **kwargs):
                    snapshots.append(copy.deepcopy(document.font))
                    document.events.append("roundtrip")
                    document.dirty = False
                    return document
                c.roundtrip = roundtrip
                case = {"writes": [], "initial": {"standard": doc.standard}}
                c.font_stage(doc, "part", object(), case)
                self.assertEqual(len(snapshots), 7)
                self.assertEqual(len(case["writes"]), 7)
                self.assertTrue(case["all_seven_changed_values_persisted_individually"])
                self.assertEqual(doc.events.count("final-set"), 7)
                self.assertEqual(doc.events.count("roundtrip"), 7)
                for row in case["writes"]:
                    mode = row["live_property_result"]
                    self.assertEqual(mode, "requested-value-visible-before-final-set" if live_property else "not-visible-in-independent-get")
                self.assertIs(snapshots[1]["IsHeightSpecifiedInPts"], False)
                self.assertIs(snapshots[2]["IsHeightSpecifiedInPts"], True)

    def test_font_false_final_set_stops_without_retry_or_rollback(self):
        doc = Doc()
        doc.final_return = False
        c = fixture([doc])
        c.roundtrip = lambda *args: self.fail("must not persist failed setter")
        case = {"writes": [], "initial": {"standard": doc.standard}}
        with self.assertRaisesRegex(RuntimeError, "strict True"):
            c.font_stage(doc, "part", object(), case)
        self.assertEqual(doc.events.count("final-set"), 1)
        self.assertEqual(len([event for event in doc.events if event.startswith("property:")]), 1)
        self.assertEqual(len(case["writes"]), 1)
        self.assertTrue(case["writes"][0]["mutation"]["may_have_changed"])
        self.assertIs(case["writes"][0]["native_return"], False)
        self.assertEqual(doc.font["TypeFaceName"], "Arial")

    def test_display_false_records_after_mutation_and_stops(self):
        doc = Doc()
        doc.scalar_return = False
        c = fixture([doc])
        c.roundtrip = lambda *args: self.fail("must not persist failed setter")
        initial = c.observe(doc, "part", None, "initial")
        case = {"writes": [], "initial": initial}
        with self.assertRaisesRegex(RuntimeError, "False"):
            c.display_stage(doc, "part", object(), case)
        self.assertEqual(doc.events.count("scalar-set"), 1)
        self.assertEqual(len(case["writes"]), 1)
        self.assertIs(case["writes"][0]["native_return"], False)
        self.assertIs(case["writes"][0]["after"]["display"]["grid.display"], True)
        self.assertIs(doc.display["grid.display"], True)

    def test_font_unrequested_drift_stops_before_final_set(self):
        doc = Doc()
        c = fixture([doc])
        original_observe = c.observe
        def observe(document, kind, foreground, label):
            if "independent-get-before-final-set" in label:
                document.standard = 8
            return original_observe(document, kind, foreground, label)
        c.observe = observe
        case = {"writes": [], "initial": {"standard": doc.standard}}
        with self.assertRaisesRegex(RuntimeError, "scalar controls"):
            c.font_stage(doc, "part", object(), case)
        self.assertEqual(doc.events.count("final-set"), 0)
        self.assertEqual(len(case["writes"]), 1)
        self.assertTrue(case["writes"][0]["mutation"]["may_have_changed"])



class EvidenceAndReopen(unittest.TestCase):
    def test_nonfinite_or_unexpected_native_value_does_not_destroy_failure_report(self):
        with tempfile.TemporaryDirectory() as folder:
            c = Calibration.__new__(Calibration)
            c.output = Path(folder)
            invalid = float("nan")
            c.report = {"success": False, "failure": {"message": "native value invalid"},
                        "native_observation": invalid, "unexpected": object()}
            c.persist()
            recorded = json.loads((c.output / "report.json").read_text())
            self.assertEqual(recorded["failure"]["message"], "native value invalid")
            self.assertEqual(recorded["native_observation"]["invalid_native_value"]["repr"], "nan")
            self.assertIs(c.report["native_observation"], invalid)

    def reopen_fixture(self, folder, bad=None):
        front = Doc("swcli-front")
        c = fixture([front])
        c.register(front, "front")
        path = Path(folder).resolve() / "swcli-saved.SLDPRT"
        path.write_bytes(b"x" * 1024)
        saved = {"path": str(path), "sha256": module.digest(path)}
        reopened = Doc("swcli-saved.SLDPRT", str(path))
        reopened.readonly = True
        if bad == "path":
            reopened.path = str(Path(folder) / "foreign.SLDPRT")
        elif bad == "kind":
            reopened.kind = 2
        elif bad == "access":
            reopened.readonly = False
        elif bad == "dirty":
            reopened.dirty = True
        def open_native(path, app, read_only):
            self.assertTrue(read_only)
            app.docs.append(reopened)
            return {"ok": True, "api_errors": 0, "api_warnings": 0}, reopened
        c.open_native = open_native
        c.activated = []
        c.activate = lambda document, label: c.activated.append(document)
        return c, front, saved, reopened

    def test_reopen_checks_actual_path_type_access_and_clean_state(self):
        for bad, message in (("path", "path differs"), ("kind", "type differs"),
                             ("access", "access mode differs"), ("dirty", "already modified")):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as folder:
                c, front, saved, reopened = self.reopen_fixture(folder, bad)
                with self.assertRaisesRegex(RuntimeError, message):
                    c.reopen_test(saved, "part", front, "readback", True)
                self.assertEqual(c.activated, [])
                self.assertIn("native_path", c.report["reopens"][0])
                self.assertEqual(len(c.live), 2)
                self.assertEqual(c.app.closed, [])

    def test_reopen_success_registers_new_native_handle_and_restores_only_test_front(self):
        with tempfile.TemporaryDirectory() as folder:
            c, front, saved, reopened = self.reopen_fixture(folder)
            result = c.reopen_test(saved, "part", front, "readback", True)
            self.assertIs(result, reopened)
            self.assertIsNot(result, front)
            self.assertEqual(c.activated, [front])
            self.assertTrue(c.report["reopens"][0]["native_read_only"])
            self.assertFalse(c.report["reopens"][0]["native_modified"])

    def save_fixture(self, folder, bad=None):
        doc = Doc("swcli-test-original")
        c = fixture([doc])
        c.register(doc, "target")
        c.output, c.prefix = Path(folder).resolve(), "swcli-test"
        def save_native(name, document):
            path = Path(name)
            path.write_bytes(b"n" * 1024)
            document.path, document.title, document.dirty = str(path), path.name, False
            return {"ok": True, "api_saved": bad != "api", "save_errors": 0,
                    "save_warnings": None, "artifact": {"size_bytes": 2048 if bad == "size" else 1024}}
        c.save_native = save_native
        return c, doc

    def test_save_requires_native_api_saved_and_actual_artifact_size(self):
        for bad, message in (("api", "native save failed"), ("size", "byte count")):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as folder:
                c, doc = self.save_fixture(folder, bad)
                with self.assertRaisesRegex(RuntimeError, message):
                    c.save_new(doc, "changed", "part")
                self.assertEqual(len(c.report["save_attempts"]), 1)
                self.assertEqual(c.report["file_hashes"], {})

    def test_save_retains_null_warning_and_verifies_hash_after_close(self):
        with tempfile.TemporaryDirectory() as folder:
            c, doc = self.save_fixture(folder)
            saved = c.save_new(doc, "changed", "part")
            self.assertIsNone(saved["save"]["save_warnings"])
            c.close(doc, "close-saved")
            self.assertEqual(c.report["closed_file_hash_checks"][0]["sha256"], saved["sha256"])
            self.assertEqual(c.live, [])



class RoundtripControl(unittest.TestCase):
    def make_roundtrip(self, folder):
        target, front = Doc("swcli-target"), Doc("swcli-front")
        target.kind = 2
        target.font["TypeFaceName"], target.dirty = "Changed Face", True
        c = fixture([target])
        c.register(target, "target")
        c.app.docs.append(front)
        c.register(front, "front")
        c.output, c.prefix = Path(folder).resolve(), "swcli-test"
        c.open_events = []
        def save_native(name, document):
            path = Path(name)
            path.write_bytes(b"s" * 1024)
            document.path, document.title, document.dirty = str(path), path.name, False
            return {"ok": True, "api_saved": True, "save_errors": 0,
                    "save_warnings": None, "artifact": {"size_bytes": 1024}}
        snapshot = c.observe(target, "assembly", front, "before")
        def open_native(path, app, read_only):
            document = Doc(Path(path).name, path)
            document.kind, document.readonly = 2, read_only
            document.font, document.display = copy.deepcopy(snapshot["font"]), copy.deepcopy(snapshot["display"])
            app.docs.append(document)
            c.open_events.append((document, read_only))
            return {"ok": True, "api_errors": 0, "api_warnings": 0}, document
        c.save_native, c.open_native = save_native, open_native
        c.activate = lambda document, label: self.assertIs(document, front)
        return c, target, front, snapshot

    def test_real_roundtrip_control_uses_readonly_then_new_writable_handle(self):
        with tempfile.TemporaryDirectory() as folder:
            c, target, front, snapshot = self.make_roundtrip(folder)
            row = {}
            returned = c.roundtrip(target, "assembly", front, snapshot, row, "field-one", True)
            self.assertEqual([read_only for document, read_only in c.open_events], [True, False])
            self.assertIs(returned, c.open_events[-1][0])
            self.assertIsNot(returned, target)
            self.assertFalse(returned.readonly)
            self.assertEqual(c.app.closed, ["swcli-test-field-one-changed.SLDASM"] * 2)
            self.assertIn(front, c.app.docs)
            self.assertFalse(row["readonly_observation"]["state"][2])
            self.assertEqual(len(c.report["closed_file_hash_checks"]), 2)

    def test_close_induced_file_change_is_retained_as_failure_without_close_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            c, target, front, snapshot = self.make_roundtrip(folder)
            original_close = c.app.CloseDoc
            def mutate_on_close(title):
                readonly = [doc for doc in c.app.docs if doc.title == title and doc.readonly]
                for doc in readonly:
                    Path(doc.path).write_bytes(b"changed" * 200)
                original_close(title)
            c.app.CloseDoc = mutate_on_close
            with self.assertRaisesRegex(RuntimeError, "file changed"):
                c.roundtrip(target, "assembly", front, snapshot, {}, "field-one", True)
            self.assertEqual(len(c.app.closed), 2)
            self.assertEqual([read_only for document, read_only in c.open_events], [True])
            failed = next(row for row in c.live if row["identity"] != "front")
            self.assertTrue(failed["close_attempted"])



class MutationGuardRegressions(unittest.TestCase):
    FAULTS = ("readonly", "viewonly", "context", "foreground", "stamp", "dirty", "pid", "usercontrol")

    def inject(self, fault, c, doc):
        if fault == "readonly":
            doc.readonly = True
        elif fault == "viewonly":
            doc.viewonly = True
        elif fault == "context":
            doc.edit_token = "changed"
        elif fault == "foreground":
            c.app.ActiveDoc = Doc("foreign")
        elif fault == "stamp":
            doc.stamp += 1
        elif fault == "dirty":
            doc.dirty = not doc.dirty
        elif fault == "pid":
            c.app.pid = 6668
        elif fault == "usercontrol":
            c.app.UserControl = False

    def assert_events(self, document, property_count, final_count, scalar_count, dirty_count):
        self.assertEqual(len([e for e in document.events if e.startswith("property:")]), property_count)
        self.assertEqual(document.events.count("final-set"), final_count)
        self.assertEqual(document.events.count("scalar-set"), scalar_count)
        self.assertEqual(document.events.count("save-flag"), dirty_count)

    def stage_fixture(self, fault, phase):
        doc = Doc()
        c = fixture([doc])
        front = Doc("front")
        c.app.ActiveDoc = front
        original_observe = c.observe
        def observe(document, kind, foreground, label):
            result = original_observe(document, kind, foreground, label)
            matches = (phase == "before" and label.endswith(".before")
                       or phase == "probe" and "independent-get-before-final-set" in label
                       or phase == "after" and label.endswith(".after"))
            if matches:
                self.inject(fault, c, document)
            return result
        c.observe = observe
        c.roundtrip = lambda *args, **kwargs: self.fail("fault path must not save/reopen")
        return c, doc, front

    def test_font_pre_read_faults_have_zero_native_mutations(self):
        for fault in self.FAULTS:
            with self.subTest(fault=fault):
                c, doc, front = self.stage_fixture(fault, "before")
                case = {"writes": [], "initial": {"standard": doc.standard}}
                with self.assertRaises(RuntimeError):
                    c.font_stage(doc, "part", front, case)
                self.assert_events(doc, 0, 0, 0, 0)
                self.assertFalse(case["writes"][0]["mutation"]["attempted"])

    def test_font_property_probe_faults_have_one_property_no_final_or_dirty(self):
        for fault in self.FAULTS:
            with self.subTest(fault=fault):
                c, doc, front = self.stage_fixture(fault, "probe")
                case = {"writes": [], "initial": {"standard": doc.standard}}
                with self.assertRaises(RuntimeError):
                    c.font_stage(doc, "part", front, case)
                self.assert_events(doc, 1, 0, 0, 0)
                self.assertTrue(case["writes"][0]["mutation"]["may_have_changed"])

    def test_font_post_final_read_faults_never_mark_dirty(self):
        for fault in self.FAULTS:
            with self.subTest(fault=fault):
                c, doc, front = self.stage_fixture(fault, "after")
                case = {"writes": [], "initial": {"standard": doc.standard}}
                with self.assertRaises(RuntimeError):
                    c.font_stage(doc, "part", front, case)
                self.assert_events(doc, 1, 1, 0, 0)

    def test_display_pre_read_faults_have_zero_native_mutations(self):
        for fault in self.FAULTS:
            with self.subTest(fault=fault):
                c, doc, front = self.stage_fixture(fault, "before")
                case = {"writes": [], "initial": copy.deepcopy(c.observe(doc, "part", front, "initial"))}
                with self.assertRaises(RuntimeError):
                    c.display_stage(doc, "part", front, case)
                self.assert_events(doc, 0, 0, 0, 0)
                self.assertFalse(case["writes"][0]["mutation"]["attempted"])
                self.assertEqual(case["writes"][0]["native_setter_calls"], 0)

    def test_display_post_setter_faults_never_mark_dirty(self):
        for fault in self.FAULTS:
            with self.subTest(fault=fault):
                c, doc, front = self.stage_fixture(fault, "after")
                case = {"writes": [], "initial": copy.deepcopy(c.observe(doc, "part", front, "initial"))}
                with self.assertRaises(RuntimeError):
                    c.display_stage(doc, "part", front, case)
                self.assert_events(doc, 0, 0, 1, 0)

    def test_legitimate_property_stamp_dirty_change_remains_allowed(self):
        doc = Doc()
        doc.live_property = True
        doc.property_changes_state = True
        c = fixture([doc])
        front = Doc("front")
        c.app.ActiveDoc = front
        persisted = []
        def roundtrip(document, kind, foreground, expected, row, label, continue_writable, **kwargs):
            persisted.append(copy.deepcopy(document.font))
            document.dirty = False
            return document
        c.roundtrip = roundtrip
        case = {"writes": [], "initial": {"standard": doc.standard}}
        c.font_stage(doc, "part", front, case)
        self.assertEqual(len(persisted), 7)
        self.assert_events(doc, 7, 7, 0, 0)

    def test_geometry_area_and_each_initial_centroid_axis_are_checked(self):
        baseline = {"solid_body_count": 1, "volume_mm3": 12000.0,
                    "surface_area_mm2": 3800.0, "centroid_mm": {"x": 0.0, "y": 0.0, "z": 5.0}}
        for field in ("surface_area_mm2", "x", "y", "z"):
            with self.subTest(field=field):
                c = fixture()
                metrics = copy.deepcopy(baseline)
                if field == "surface_area_mm2":
                    metrics[field] += 1.0
                else:
                    metrics["centroid_mm"][field] += .1
                c.measure = lambda document: {"ok": True, "metrics": metrics}
                with self.assertRaisesRegex(RuntimeError, "V/S/centroid"):
                    c.geometry(Doc(), "failed-geometry", reference=baseline)
                self.assertEqual(c.report["geometry"]["failed-geometry"]["metrics"], metrics)



# Standard tests compose the actual fixed reader with portable fake native
# objects. They test control/data flow only; there is no COM or native proof.
def standard_dependencies():
    root = Path(os.environ.get("SWCLI_CALIBRATION_PROJECT", str(PROJECT_ROOT)))
    if str(root / "src") not in sys.path:
        sys.path.insert(0, str(root / "src"))
    from swcli.hosts.windows_document_drafting_standard import _read_snapshot
    from swcli.document_display_options import DISPLAY_FIELDS
    from swcli.document_annotations import ANNOTATION_FIELDS
    from swcli.document_drafting_standard import BASE_STANDARD_OPTIONS
    return _read_snapshot, DISPLAY_FIELDS, ANNOTATION_FIELDS, BASE_STANDARD_OPTIONS


class StandardExtension(Extension):
    def __init__(self, document, display_fields, annotations):
        super().__init__(document)
        self.pref_keys = {spec["preference"]: key for key, spec in display_fields.items()}
        self.annotation_keys = {(spec["kind"], spec["preference"], spec["option"]): key
                                for key, spec in annotations.items()}
        self.standard_return = True
        self.standard_exception = None
        self.ignore_standard_write = False

    def _get(self, family, preference, option):
        if family == "Integer" and preference == 13:
            return self.document.standard if option == 0 else self.document.base[option]
        annotation = self.annotation_keys.get((family, preference, option))
        if annotation is not None:
            return self.document.annotations[annotation]
        if option == 0 and preference in self.pref_keys:
            return self.document.display[self.pref_keys[preference]]
        raise RuntimeError("unsupported fake native preference; no fallback/default")

    def GetUserPreferenceInteger(self, preference, option):
        return self._get("Integer", preference, option)

    def GetUserPreferenceDouble(self, preference, option):
        return self._get("Double", preference, option)

    def GetUserPreferenceToggle(self, preference, option):
        return self._get("Toggle", preference, option)

    def SetUserPreferenceInteger(self, preference, option, target):
        if (preference, option) != (13, 0):
            return self._set(preference, option, target)
        doc = self.document
        doc.events.append(("standard-set", target))
        if not self.ignore_standard_write:
            doc.standard = target
            doc.base = {key: target for key in doc.base}
            # Deliberate linked changes exercise the finite observed profile.
            doc.font["Bold"] = target % 2 == 0
            doc.display["grid.minor_lines_per_major"] = target + 4
            doc.annotations["zero.leading"] = target % 3 + 1
            doc.units[3] = target + 1
        if self.standard_exception is not None:
            raise self.standard_exception
        return self.standard_return


def standard_fixture(kind=2):
    reader, display_fields, annotations, base_options = standard_dependencies()
    doc = Doc("swcli-standard-target")
    doc.kind = kind
    doc.units = [99, 1, 8, 2, 0]  # unknown readable length code must be preserved
    doc.GetUnits = lambda: doc.units
    doc.base = {spec["option"]: 77 for spec in base_options.values()}
    doc.extension = StandardExtension(doc, display_fields, annotations)
    c = fixture([doc])
    front = Doc("swcli-standard-front")
    c.register(doc, "target")
    c.app.docs.append(front)
    c.register(front, "front")
    c.app.ActiveDoc = front
    c.report["cases"] = []
    c.prefix = "swcli-standard-test"
    c.standard_reader = reader
    c.standard_trace = lambda *args: nullcontext()
    c.standard_native_call = lambda stage, method, function: function()
    c.constants.update({spec["symbol"]: spec["preference"] for spec in display_fields.values()})
    c.constants.update({spec["symbol"]: spec["option"] for spec in base_options.values()})
    c.constants["swDetailingDimensionStandard"] = 13
    c.constants.update(dict(zip(module.STANDARD_SYMBOLS, range(1, 9))))
    c.source_file = lambda path, role: None
    c.standard_catalog()
    return c, doc, front


class StandardsControl(unittest.TestCase):
    def test_actual_fixed_reader_preserves_unknown_base_and_all_five_units(self):
        c, doc, front = standard_fixture()
        snapshot = c.standard_reader(doc, 2)
        observed = snapshot["observed_defaults"]
        self.assertEqual(observed["profile"], "drafting-defaults-v1")
        self.assertEqual(len(observed["annotations"]), 7)
        self.assertEqual(len(observed["annotation_font"]["native_font"]), 17)
        self.assertEqual(len(observed["display"]), 10)
        self.assertEqual(len(observed["base_standards"]), 4)
        self.assertTrue(all(row == {"value": "other", "native_value": 77}
                            for row in observed["base_standards"].values()))
        self.assertEqual(observed["length_units"]["length_unit"], "other")
        self.assertEqual(list(observed["length_units"]["native_units"].values()), [99, 1, 8, 2, 0])
        drawing = c.standard_reader(doc, 3)
        self.assertEqual(len(drawing["observed_defaults"]["display"]), 5)

    def test_fixed_plan_has_36_single_setters_and_individual_roundtrips_across_types(self):
        total = 0
        for kind, name in ((1, "part"), (2, "assembly"), (3, "drawing")):
            with self.subTest(kind=kind):
                c, doc, front = standard_fixture(kind)
                persisted = []
                def roundtrip(document, kind_name, foreground, expected, state, context, row, label, continue_writable):
                    persisted.append(copy.deepcopy(expected))
                    document.dirty = False
                    return document
                c.standard_roundtrip = roundtrip
                case = {"kind": name, "writes": [], "initial": {"standard": doc.standard}}
                c.report["cases"].append(case)
                c.standards_stage(doc, name, front, case)
                requests = [event[1] for event in doc.events
                            if isinstance(event, tuple) and event[0] == "standard-set"]
                self.assertEqual(requests, [1, 7, 2, 7, 3, 7, 4, 7, 5, 7, 6, 7])
                self.assertEqual(len(persisted), 12)
                self.assertEqual(case["successful_planned_transitions"], 12)
                self.assertTrue(all(row["native_setter_calls"] == 1 for row in case["writes"]))
                self.assertTrue(all(row["before_after_diff"] and row["observed_defaults_diff"]
                                    and not row["after_final_diff"] for row in case["writes"]))
                total += len(requests)
        self.assertEqual(total, 36)

    def test_non_gb_baseline_stops_without_any_setter(self):
        for initial in (1, 8, 999):
            with self.subTest(initial=initial):
                c, doc, front = standard_fixture()
                doc.standard = initial
                case = {"writes": [], "initial": {"standard": doc.standard}}
                with self.assertRaisesRegex(RuntimeError, "GB7"):
                    c.standards_stage(doc, "assembly", front, case)
                self.assertEqual(case["writes"], [])
                self.assertFalse(any(isinstance(event, tuple) for event in doc.events))

    def test_native_false_nonbool_or_exception_stops_without_return_to_gb_or_saveflag(self):
        for returned in (False, 1, "true", RuntimeError("native standard failed")):
            with self.subTest(returned=returned):
                c, doc, front = standard_fixture()
                if isinstance(returned, Exception):
                    doc.extension.standard_exception = returned
                else:
                    doc.extension.standard_return = returned
                c.standard_roundtrip = lambda *args: self.fail("failed setter must not persist")
                case = {"writes": [], "initial": {"standard": doc.standard}}
                with self.assertRaises(RuntimeError):
                    c.standards_stage(doc, "assembly", front, case)
                self.assertEqual([event for event in doc.events if isinstance(event, tuple)], [("standard-set", 1)])
                self.assertEqual(doc.events.count("save-flag"), 0)
                self.assertEqual(doc.standard, 1)  # possible partial mutation is not rolled back
                self.assertTrue(case["writes"][0]["mutation"]["may_have_changed"])

    def test_unknown_base_bool_or_invalid_units_fail_first_without_defaults(self):
        for bad in ("base", "units"):
            with self.subTest(bad=bad):
                c, doc, front = standard_fixture()
                if bad == "base":
                    doc.base[103] = True
                else:
                    doc.units[0] = True
                case = {"writes": [], "initial": {"standard": doc.standard}}
                with self.assertRaises((RuntimeError, ValueError)):
                    c.standards_stage(doc, "assembly", front, case)
                self.assertFalse(any(isinstance(event, tuple) for event in doc.events))
                self.assertEqual(doc.events.count("save-flag"), 0)

    def test_standard_read_drift_rejected_before_set_or_dirty(self):
        faults = ("readonly", "context", "foreground", "stamp", "dirty", "pid", "usercontrol")
        for phase, expected_sets in ((2, 0), (3, 1)):
            for fault in faults:
                with self.subTest(phase=phase, fault=fault):
                    c, doc, front = standard_fixture()
                    actual = c.standard_reader
                    count = [0]
                    def reader(document, kind):
                        snapshot = actual(document, kind)
                        count[0] += 1
                        if count[0] == phase:
                            MutationGuardRegressions().inject(fault, c, document)
                        return snapshot
                    c.standard_reader = reader
                    c.standard_roundtrip = lambda *args: self.fail("drift must not persist")
                    case = {"writes": [], "initial": {"standard": doc.standard}}
                    with self.assertRaises(RuntimeError):
                        c.standards_stage(doc, "assembly", front, case)
                    self.assertEqual(len([event for event in doc.events if isinstance(event, tuple)]), expected_sets)
                    self.assertEqual(doc.events.count("save-flag"), 0)
                    self.assertEqual(case["writes"][0]["mutation"]["attempted"], bool(expected_sets))

    def test_typed_diff_distinguishes_bool_int_and_allows_declared_coupling(self):
        diff = Calibration.standard_diff({"same": True, "nested": {"value": 1}}, {"same": 1, "nested": {"value": 2}})
        self.assertEqual({row["path"] for row in diff}, {"/same", "/nested/value"})
        typed = next(row for row in diff if row["path"] == "/same")
        self.assertEqual((typed["before_type"], typed["after_type"]), ("bool", "int"))

    def test_observed_coverage_change_is_not_accepted_as_standard_coupling(self):
        c, doc, front = standard_fixture()
        actual = c.standard_reader
        reads = [0]
        def reader(document, kind):
            value = actual(document, kind)
            reads[0] += 1
            if reads[0] == 3:
                value["observed_defaults"]["coverage"]["unexpected"] = True
            return value
        c.standard_reader = reader
        case = {"writes": [], "initial": {"standard": doc.standard}}
        with self.assertRaisesRegex(RuntimeError, "coverage manifest"):
            c.standards_stage(doc, "assembly", front, case)
        self.assertEqual(len([event for event in doc.events if isinstance(event, tuple)]), 1)
        self.assertEqual(doc.events.count("save-flag"), 0)


class StandardRoundtripControl(unittest.TestCase):
    def fixture(self, folder):
        c, target, front = standard_fixture()
        c.output = Path(folder).resolve()
        c.prefix = "swcli-standard-test"
        target.extension.SetUserPreferenceInteger(13, 0, 1)
        target.dirty = True
        snapshot = c.standard_reader(target, 2)
        state, context = list(c.native_state(target)), c.edit_context(target)
        stored = {}
        c.open_modes = []
        def save_native(name, document):
            path = Path(name)
            path.write_bytes(b"d" * 1024)
            document.path, document.title, document.dirty = str(path), path.name, False
            stored[str(path)] = {key: copy.deepcopy(getattr(document, key))
                                 for key in ("font", "display", "annotations", "base", "units", "standard")}
            return {"ok": True, "api_saved": True, "save_errors": 0, "save_warnings": None,
                    "artifact": {"size_bytes": 1024}}
        def open_native(path, app, read_only):
            reopened = Doc(Path(path).name, path)
            reopened.kind, reopened.readonly = 2, read_only
            for key, value in stored[path].items():
                setattr(reopened, key, copy.deepcopy(value))
            reopened.GetUnits = lambda: reopened.units
            _, display_fields, annotations, _ = standard_dependencies()
            reopened.extension = StandardExtension(reopened, display_fields, annotations)
            app.docs.append(reopened)
            c.open_modes.append(read_only)
            return {"ok": True, "api_errors": 0, "api_warnings": 0}, reopened
        c.save_native, c.open_native = save_native, open_native
        c.activate = lambda document, label: self.assertIs(document, front)
        return c, target, front, snapshot, state, context

    def test_full_standard_profile_survives_actual_roundtrip_control_and_writable_continuation(self):
        for continuation in (False, True):
            with self.subTest(continuation=continuation), tempfile.TemporaryDirectory() as folder:
                c, target, front, snapshot, state, context = self.fixture(folder)
                row = {}
                returned = c.standard_roundtrip(target, "assembly", front, snapshot, state, context,
                                                row, "gb-to-ansi", continuation)
                self.assertIsNot(returned, target)
                self.assertEqual(c.open_modes, [True, False] if continuation else [True])
                self.assertEqual(returned.readonly, not continuation)
                self.assertEqual(Calibration.standard_key(row["readonly_profile"]), Calibration.standard_key(snapshot))
                self.assertIsNone(row["saved"]["save"]["save_warnings"])
                self.assertEqual(len(c.report["closed_file_hash_checks"]), 2 if continuation else 1)



class FontInactiveCacheControl(unittest.TestCase):
    def test_final_set_records_only_inactive_normalization_for_both_modes(self):
        for points_mode in (False, True):
            with self.subTest(points_mode=points_mode):
                doc = Doc()
                doc.font["IsHeightSpecifiedInPts"] = points_mode
                c = fixture([doc])
                front = Doc("front")
                c.app.ActiveDoc = front
                original_set = doc.extension.SetUserPreferenceTextFormat
                def final_set(pref, option, format_object):
                    value = original_set(pref, option, format_object)
                    if doc.font["IsHeightSpecifiedInPts"]:
                        doc.font["CharHeight"] += .0001
                    else:
                        doc.font["CharHeightInPts"] += 2
                    return value
                doc.extension.SetUserPreferenceTextFormat = final_set
                persisted = []
                def roundtrip(document, kind, foreground, expected, row, label, continue_writable, **kwargs):
                    persisted.append(copy.deepcopy(document.font))
                    document.dirty = False
                    return document
                c.roundtrip = roundtrip
                case = {"writes": []}
                c.font_stage(doc, "part", front, case)
                row = case["writes"][0]
                inactive = "CharHeight" if points_mode else "CharHeightInPts"
                self.assertEqual(row["native_normalizations"], [{
                    "member": inactive, "before": FONT[inactive],
                    "after": persisted[0][inactive], "reason": "inactive-height-representation"}])
                active = "CharHeightInPts" if points_mode else "CharHeight"
                self.assertEqual(persisted[0][active], FONT[active])
                self.assertIs(persisted[0]["IsHeightSpecifiedInPts"], points_mode)
                self.assertEqual(len(persisted), 7)

    def test_detached_probe_inactive_cache_drift_is_not_misclassified_as_live(self):
        doc = Doc()
        c = fixture([doc])
        front = Doc("front")
        c.app.ActiveDoc = front
        original_observe = c.observe
        def observe(document, kind, foreground, label):
            if "independent-get-before-final-set" in label and "TypeFaceName" in label:
                document.font["CharHeightInPts"] = 14
            return original_observe(document, kind, foreground, label)
        c.observe = observe
        def roundtrip(document, kind, foreground, expected, row, label, continue_writable, **kwargs):
            document.dirty = False
            return document
        c.roundtrip = roundtrip
        case = {"writes": []}
        c.font_stage(doc, "part", front, case)
        row = case["writes"][0]
        self.assertEqual(row["live_property_result"], "not-visible-in-independent-get")
        self.assertEqual(row["property_probe_native_normalizations"], [{
            "member": "CharHeightInPts", "before": 12, "after": 14,
            "reason": "inactive-height-representation"}])

    def test_active_height_mode_or_unrelated_member_drift_still_stops_before_dirty(self):
        for fault in ("active", "mode", "italic"):
            with self.subTest(fault=fault):
                doc = Doc()
                c = fixture([doc])
                front = Doc("front")
                c.app.ActiveDoc = front
                original_set = doc.extension.SetUserPreferenceTextFormat
                def final_set(pref, option, format_object):
                    value = original_set(pref, option, format_object)
                    if fault == "active":
                        doc.font["CharHeight"] = .004
                    elif fault == "mode":
                        doc.font["IsHeightSpecifiedInPts"] = True
                    else:
                        doc.font["Italic"] = True
                    return value
                doc.extension.SetUserPreferenceTextFormat = final_set
                c.roundtrip = lambda *args, **kwargs: self.fail("invalid active/unrelated drift must not persist")
                case = {"writes": []}
                with self.assertRaises(ValueError):
                    c.font_stage(doc, "part", front, case)
                self.assertEqual(doc.events.count("final-set"), 1)
                self.assertEqual(doc.events.count("save-flag"), 0)

    def test_saved_reopen_raw_equality_is_not_relaxed_for_inactive_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            c, target, front, snapshot = RoundtripControl().make_roundtrip(folder)
            original_observe = c.observe
            def observe(document, kind, foreground, label):
                if "readonly-readback" in label:
                    document.font["CharHeightInPts"] += 2
                return original_observe(document, kind, foreground, label)
            c.observe = observe
            with self.assertRaisesRegex(RuntimeError, "persist cleanly"):
                c.roundtrip(target, "assembly", front, snapshot, {}, "strict-copy", False)


class StandardNativeTraceControl(unittest.TestCase):
    def test_fixed_reader_and_raw_set_emit_flat_leaf_boundaries(self):
        from swcli.hosts.native_trace import trace_native_request, native_call
        c, doc, front = standard_fixture()
        c.standard_trace, c.standard_native_call = trace_native_request, native_call
        c.standard_plan = c.standard_plan[:2]
        def roundtrip(document, kind, foreground, expected, state, context, row, label, continue_writable):
            document.dirty = False
            return document
        c.standard_roundtrip = roundtrip
        output = io.StringIO()
        with patch.dict(os.environ, {"SWCLI_TRACE_NATIVE_CALLS": "1"}), redirect_stderr(output):
            c.standards_stage(doc, "assembly", front, {"writes": [], "initial": {"standard": 7}})
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        active = {}
        setters = 0
        for row in records:
            if row["sequence"] == 0:
                continue
            request = row["request_id"]
            if row["phase"] == "begin":
                self.assertNotIn(request, active)
                active[request] = row["sequence"]
                if row["call"] == "IModelDocExtension.SetUserPreferenceInteger" and row["stage"] == "document-drafting-standard-calibration":
                    setters += 1
            else:
                self.assertEqual(active.pop(request), row["sequence"])
                self.assertEqual(row["phase"], "end")
        self.assertEqual(active, {})
        self.assertEqual(setters, 2)
        self.assertTrue(any(row["call"] == "IModelDoc2.GetUnits" for row in records))

class ReportPersistenceControl(unittest.TestCase):
    """Disk faults and portable traces; no SOLIDWORKS/COM is invoked."""

    @contextmanager
    def disk_fixture(self):
        # Close the writer before TemporaryDirectory removes its files. Test
        # cleanups run after the method and are too late for Windows file locks.
        with tempfile.TemporaryDirectory() as folder:
            c = fixture()
            c.output = Path(folder)
            with (c.output / "trace.jsonl").open("x", encoding="utf-8", buffering=1) as trace:
                c.trace = trace
                c.persist = Calibration.persist.__get__(c, Calibration)
                c.call = Calibration.call.__get__(c, Calibration)
                c.event = Calibration.event.__get__(c, Calibration)
                c.trusted = False
                yield c

    def test_precall_permission_failure_has_terminal_native_zero_and_cleanup_continues(self):
        with self.disk_fixture() as c:
            native = []
            cause = PermissionError(5, "report replacement denied")
            with patch.object(Path, "replace", side_effect=cause) as replace:
                with self.assertRaises(PermissionError) as caught:
                    c.call("must-not-enter-native", lambda: native.append("entered"))
                self.assertIs(caught.exception, cause)
                self.assertEqual(replace.call_count, 1)
            self.assertEqual(native, [])
            self.assertEqual(c.report["first_call_failure"]["type"], "PermissionError")
            first = copy.deepcopy(c.report["first_call_failure"])
            with patch.object(module, "process_ids", return_value=[2940, 6668]):
                c.cleanup()
            self.assertEqual(c.report["first_call_failure"], first)
            self.assertTrue(c.report["manual_host_still_running"])
            rows = [json.loads(line) for line in (c.output / "trace.jsonl").read_text().splitlines()]
            self.assertEqual([(r["call"], r["phase"]) for r in rows], [
                ("must-not-enter-native", "begin"), ("must-not-enter-native", "error"),
                ("snapshot-processes-after", "begin"), ("snapshot-processes-after", "end")])
            self.assertEqual(rows[1]["type"], "PermissionError")
            self.assertIn("report replacement denied", rows[1]["message"])
            saved = json.loads((c.output / "report.json").read_text())
            self.assertEqual(saved["first_call_failure"], first)

    def test_identical_report_skips_disk_but_getter_observation_and_mutation_intent_persist(self):
        with self.disk_fixture() as c:
            original_replace = Path.replace
            replaced = []
            def replace(path, target):
                replaced.append(path.read_bytes())
                return original_replace(path, target)
            with patch.object(Path, "replace", replace):
                c.persist()
                baseline = (c.output / "report.json").read_bytes()
                c.persist()
                self.assertEqual(replaced, [baseline])
                c.report["reads"]["getter-1"] = {"value": 3}
                c.persist()
                self.assertEqual(len(replaced), 2)
                self.assertEqual(json.loads(replaced[-1])["reads"]["getter-1"]["value"], 3)
                c.report["mutation_intent"] = {"field": "grid.display", "target": True}
                c.report_changed()
                def native():
                    saved = json.loads((c.output / "report.json").read_text())
                    self.assertEqual(saved["mutation_intent"], c.report["mutation_intent"])
                    return True
                self.assertTrue(c.call("single-setter", native))
                self.assertEqual(len(replaced), 3)
                c.call("pure-getter", lambda: 3)
                self.assertEqual(len(replaced), 3)
            c.trace.flush()
            rows = [json.loads(line) for line in (c.output / "trace.jsonl").read_text().splitlines()]
            self.assertEqual([r["phase"] for r in rows], ["begin", "end", "begin", "end"])

    def test_cache_advances_only_after_successful_replace(self):
        with self.disk_fixture() as c:
            c.persist()
            previous = c._persisted_report_bytes
            c.report["reads"]["new-native-value"] = 42
            with patch.object(Path, "replace", side_effect=PermissionError("locked")) as replace:
                with self.assertRaisesRegex(PermissionError, "locked"):
                    c.persist()
                self.assertEqual(replace.call_count, 1)
            self.assertEqual(c._persisted_report_bytes, previous)
            self.assertEqual((c.output / "report.json").read_bytes(), previous)
            self.assertNotEqual((c.output / "report.tmp").read_bytes(), previous)

    def test_trace_begin_and_terminal_each_fsync_even_when_snapshot_is_identical(self):
        with self.disk_fixture() as c:
            c.persist()
            with patch.object(module.os, "fsync", wraps=module.os.fsync) as fsync:
                c.call("getter-with-unchanged-report", lambda: 7)
            self.assertEqual([args.args[0] for args in fsync.call_args_list],
                             [c.trace.fileno(), c.trace.fileno()])

    def test_native_cause_survives_secondary_failure_report_io_fault(self):
        c = fixture()
        c.call = Calibration.call.__get__(c, Calibration)
        events = []
        c.event = events.append
        snapshots = []
        def persist():
            snapshots.append(True)
            if len(snapshots) == 2:
                raise PermissionError("failure-report locked")
        c.persist = persist
        cause = RuntimeError("native first cause")
        def native():
            raise cause
        with self.assertRaises(RuntimeError) as caught:
            c.call("native-failed-once", native)
        self.assertIs(caught.exception, cause)
        self.assertEqual(len(snapshots), 2)
        self.assertEqual([r["phase"] for r in events], ["begin", "error"])
        self.assertEqual(events[1]["message"], "native first cause")
        self.assertEqual(events[1]["report_persist_failure"], {
            "type": "PermissionError", "message": "failure-report locked"})
        self.assertEqual(c.report["first_call_failure"]["message"], "native first cause")


if __name__ == "__main__":
    unittest.main(verbosity=2)
