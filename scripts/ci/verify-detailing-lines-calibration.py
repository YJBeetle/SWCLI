"""INTERNAL ONLY: owned Windows SW2025 calibration for the two NEW line toggles.

Execution requires separate coordinator authorization. No public allowlisting,
CLI acceptance, VM connection, workflow dispatch or release action is provided.
"""

import argparse
from contextlib import redirect_stderr
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from uuid import uuid4

# Loaded by file, including under -I; never depend on scripts being on sys.path.
def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load("_detailing_lines_gate", "detailing_line_gate.py")
require = gate.require


class NativeBackend:
    def __init__(self, app, output, template, swconst, report):
        from swcli.daemon.documents import DocumentRegistry
        from swcli.hosts import windows_document_detailing_lines as adapter
        from swcli.hosts import windows_document_detailing as legacy
        self.app, self.output, self.report = app, output, report
        self.registry, self.session = DocumentRegistry(app), "detailing-lines-internal"
        self.adapter, self.legacy = adapter, legacy
        self.original_allowlist = adapter.CALIBRATED_LINE_REVISIONS
        self.legacy_allowlist = legacy.CALIBRATED_REVISIONS
        self.document = self.foreground = self.entry = None
        self.swconst, self.template = swconst, template
        self.closed_ids = set()

    def prepare(self):
        from swcli.hosts.windows import _com_value
        from swcli.hosts.windows_drawings import create_drawing_windows_with_handle
        from swcli.hosts.windows_parts import create_part_windows_with_handle
        require(self.legacy._native_windows(), "Wine or unknown Windows runtime is not eligible")
        require(not self.original_allowlist, "new production write allowlist must be empty")
        revision = _com_value(self.app, "RevisionNumber")
        require(type(revision) is str and revision.startswith("33."), "requires SOLIDWORKS 2025")
        self.revision = revision
        self.report["native_runtime"] = dict(windows=True, wine=False, major=33)
        fields = gate.DETAILING_LINE_SNAPSHOT_FIELDS
        official = self.legacy._load_constants(str(self.swconst), tuple(fields.values()))
        hosted = self.legacy._constants(self.app, fields=fields)
        require(hosted == official and set(hosted) == set(fields.values()) | {"swDetailingNoOptionSpecified"}
                and all(type(v) is int for v in hosted.values()), "new-profile official constants incomplete/mismatched")
        self.report["official_constants"] = hosted
        self.report["swconst"] = dict(path=str(self.swconst), sha256=hashlib.sha256(self.swconst.read_bytes()).hexdigest())
        self.report["drawing_template"] = dict(path=str(self.template), sha256=hashlib.sha256(self.template.read_bytes()).hexdigest())
        made, self.document = create_drawing_windows_with_handle(app=self.app, template=str(self.template), projection="first-angle")
        self.report["creation"] = made
        require(made["ok"] and self.document is not None and made["views"] == [], "empty drawing creation failed")
        made_front, self.foreground = create_part_windows_with_handle(app=self.app)
        self.report["foreground_creation"] = made_front
        require(made_front["ok"] and self.foreground is not None, "foreground part creation failed")
        self.front = self.registry.register(self.foreground)
        self.registry.set_current(self.front, session_id=self.session)
        self.register()

    def register(self):
        self.entry = self.registry.register(self.document)
        require(self.entry.document_id not in self.closed_ids, "registry reused a retired drawing ID")
        self.lease = self.registry.acquire_lease(self.entry, session_id=self.session, ttl_seconds=1800)
        self.activate_foreground()

    def activate_foreground(self):
        import pythoncom
        from win32com.client import VARIANT
        from swcli.hosts.windows import _com_value
        error = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        activated = self.app.ActivateDoc3(_com_value(self.foreground, "GetTitle"), False, 1, error)
        require(activated is not None and error.value == 0 and self.registry.is_active(self.front),
                "cannot restore retained foreground fixture")

    def observe(self):
        from swcli.hosts.windows import _com_value
        from swcli.hosts.windows_custom_properties import _state
        from swcli.hosts.windows_drawings import _dispatch
        require(_com_value(self.app, "RevisionNumber") == self.revision
                and _com_value(self.app, "GetProcessID") == self.report["host"]["process_id"], "owned host identity changed")
        require(self.registry.is_active(self.front), "retained foreground identity changed")
        desc = self.registry.describe(self.entry, session_id=self.session)
        sheets, views = _com_value(self.document, "GetSheetNames"), _com_value(self.document, "GetViews")
        require(isinstance(sheets, (tuple, list)) and len(sheets) == 1
                and isinstance(views, (tuple, list)) and len(views) == 1
                and isinstance(views[0], (tuple, list)) and len(views[0]) == 1, "drawing acquired sheets/model views")
        sheet = _com_value(self.document, "GetCurrentSheet")
        properties = _com_value(sheet, "GetProperties2")
        require(isinstance(properties, (tuple, list)) and len(properties) == 8, "sheet properties unavailable")
        layout = dict(sheets=list(sheets), sheet_properties=list(properties),
            view_names=[_com_value(_dispatch(v), "GetName2") for v in views[0]],
            view_models=[_com_value(_dispatch(v), "GetReferencedModelName") for v in views[0]])
        require(_com_value(self.document, "IsOpenedViewOnly") is False, "view-only drawing is not eligible")
        state = _state(self.document)
        require(desc["update_stamp"] == state[1] and desc["modified"] is state[2], "descriptor/state disagree")
        return dict(document_id=desc["document_id"], update_stamp=state[1], modified=state[2],
            path=desc["path"], title=desc["title"], active=desc["active"], current=desc["current"],
            read_only=_com_value(self.document, "IsOpenedReadOnly"), layout=layout,
            normal_sheet=self.legacy._writable_context(self.app, self.legacy._edit_context(self.document)),
            foreground=dict(document_id=self.front.document_id, state=list(_state(self.foreground))))

    def enable_internal(self):
        require(not self.adapter.CALIBRATED_LINE_REVISIONS and self.legacy.CALIBRATED_REVISIONS == self.legacy_allowlist,
                "profile allowlist drift")
        self.adapter.CALIBRATED_LINE_REVISIONS = frozenset({self.revision})
        return dict(revision=self.revision, scope="owned-process-only", public_allowlist_changed=False)

    def invoke(self, operation, field, value, expected, mode):
        from swcli.daemon.operations import execute_operation
        from swcli.hosts.native_trace import trace_native_request
        from swcli.hosts.windows import _com_value
        request = "detailing-lines-" + uuid4().hex
        trace_path = self.output / "native-trace.jsonl"
        offset = trace_path.stat().st_size if trace_path.exists() else 0
        result, raised = None, None
        parameters = {} if operation == gate.READ else dict(field=field, value=value, expected_options=expected)
        context = dict(document_id=self.entry.document_id, session_id=self.session,
            expected_update_stamp=_com_value(self.document, "GetUpdateStamp") + (1 if mode == "stale-stamp" else 0),
            lease_id=("l-000000000000" if mode == "invalid-lease" else self.lease["lease_id"]) if operation == gate.SET else None)
        with trace_path.open("a", encoding="utf-8", buffering=1) as stream, redirect_stderr(stream):
            with trace_native_request(request, operation):
                try:
                    result = execute_operation(self.app, operation, parameters, documents=self.registry, **context)
                except Exception as exc:
                    raised = dict(type=type(exc).__name__, message=str(exc))
        with trace_path.open("rb") as stream:
            stream.seek(offset)
            rows = [json.loads(line) for line in stream.read().decode("utf-8").splitlines()]
        return dict(request_id=request, request=dict(operation=operation, parameters=parameters, **context),
                    mode=mode, result=result, raised=raised, trace=rows)

    @staticmethod
    def validate(operation, result):
        from swcli.result_schemas import validate_operation_result
        validate_operation_result(operation, result)

    def save(self, path):
        from swcli.hosts.windows_native_files import save_as_native_windows
        result = save_as_native_windows(str(path), document=self.document)
        # SaveAs changes the native key; do not let sync retire the retained ID.
        if result.get("ok"):
            self.registry.refresh_key(self.entry)
        return result

    def close(self):
        from swcli.daemon.documents import DocumentNotFound
        from swcli.hosts.windows import _com_value
        from swcli.hosts.windows_feature_inspection import _same
        old_id = self.entry.document_id
        self.registry.release_lease(self.lease["lease_id"], session_id=self.session)
        self.app.CloseDoc(_com_value(self.document, "GetTitle"))
        self.document = None
        # Prove actual native close before retiring the registry ID. Forgetting
        # alone is not evidence of a closed document.
        docs = tuple(_com_value(self.app, "GetDocuments") or ())
        require(_com_value(self.app, "GetDocumentCount") == len(docs) == 1
                and _same(self.app, docs[0], self.foreground), "close left a drawing or changed retained catalog")
        self.registry.forget(old_id)
        self.closed_ids.add(old_id)
        self.entry = None
        try:
            self.registry.resolve(old_id, session_id=self.session)
        except DocumentNotFound:
            return dict(retired_id=old_id, native_catalog_count=1, stale_id_refused=True)
        raise RuntimeError("closed document handle still resolves")

    def reopen(self, path, readonly):
        from swcli.hosts.windows_documents import open_windows_document_with_handle
        result, self.document = open_windows_document_with_handle(str(path), app=self.app, read_only=readonly)
        if result.get("ok") and self.document is not None:
            self.register()
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swconst", type=Path, required=True)
    parser.add_argument("--drawing-template", type=Path, required=True)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--execute-owned-native", action="store_true")
    parser.add_argument("--watchdog-pid", type=int, required=True)
    args = parser.parse_args(argv)
    if not args.execute_owned_native:
        parser.error("execution requires separately authorized --execute-owned-native")
    if args.watchdog_pid != os.getppid():
        parser.error("must run through the bounded run-detailing-lines-calibration.py parent")
    if sys.platform != "win32":
        parser.error("requires native Windows; offline tests never invoke main")
    for path in (args.swconst, args.drawing_template):
        if not path.is_file():
            parser.error("requires existing official swconst and explicit drawing template")
    import swcli
    root = Path(__file__).resolve().parents[2]
    require(Path(swcli.__file__).resolve() == root / "src/swcli/__init__.py", "internal gate requires this checkout's runtime")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    require(args.source_head == head and len(head) == 40, "source head mismatch")
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal", "--", "src", "scripts/ci"],
                                        cwd=root, text=True).strip(), "gate/runtime sources must be committed and clean")
    args.output_dir.mkdir()
    output = args.output_dir.resolve()
    manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((root / "src/swcli").rglob("*.py"))}
    for filename in ("detailing_line_gate.py", "verify-detailing-lines-calibration.py", "run-detailing-lines-calibration.py"):
        path = Path(__file__).with_name(filename)
        manifest[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = dict(success=False, profile=gate.PROFILE, source_commit=head, source_files=manifest, native_accepted=False,
                  public_acceptance=False, full_acceptance_eligible=False, cleanup_errors=[])
    engine = gate.Gate(None, output, report)
    engine.persist()
    app = handle = backend = pythoncom = None
    initialized = owned = False
    old_trace = os.environ.get("SWCLI_TRACE_NATIVE_CALLS")
    os.environ["SWCLI_TRACE_NATIVE_CALLS"] = "1"
    helpers = load("_detailing_lines_lifecycle", "verify-through-all-calibration.py")
    try:
        import pythoncom
        import win32com.client as client
        from swcli.daemon.server import acquire_resident_app
        from swcli.hosts.windows import _com_value, wait_windows_host_ready
        pythoncom.CoInitialize()
        initialized = True
        app, owned = engine.step("acquire_owned_hidden_host", lambda: acquire_resident_app(client, visible=False), {}, "acquire")
        require(owned, "must never attach to an existing host")
        engine.step("wait_owned_ready", lambda: wait_windows_host_ready(app, timeout_seconds=120), {}, "ready")
        report["host"] = dict(process_id=_com_value(app, "GetProcessID"), revision=_com_value(app, "RevisionNumber"), owned=True, visible=False)
        handle = helpers.capture_process(report["host"]["process_id"])
        require(_com_value(app, "GetDocumentCount") == 0, "owned host is not empty")
        backend = NativeBackend(app, output, args.drawing_template.resolve(), args.swconst.resolve(), report)
        engine.backend = backend
        engine.step("prepare_new_profile", backend.prepare, report, "prepare")
        engine.run_plan()
    except BaseException as exc:
        report.setdefault("failure", dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc()))
    finally:
        def require_empty_catalog():
            count = _com_value(app, "GetDocumentCount")
            require(count == 0, "owned cleanup left native documents open")
            report["cleanup_catalog_count"] = count
        if backend is not None:
            backend.adapter.CALIBRATED_LINE_REVISIONS = backend.original_allowlist
            report["allowlist_restored"] = (not backend.adapter.CALIBRATED_LINE_REVISIONS
                and backend.legacy.CALIBRATED_REVISIONS == backend.legacy_allowlist)
        for label, function, needed in (
            ("close-drawing", lambda: app.CloseDoc(_com_value(backend.document, "GetTitle")), owned and backend is not None and backend.document is not None),
            ("close-foreground", lambda: app.CloseDoc(_com_value(backend.foreground, "GetTitle")), owned and backend is not None and backend.foreground is not None),
            ("empty-owned-catalog", require_empty_catalog, owned),
            ("exit-owned-host", lambda: _com_value(app, "ExitApp"), owned),
            ("wait-owned-exit", lambda: helpers.wait_process(handle), handle is not None),
            ("close-process-handle", lambda: handle.Close(), handle is not None),
            ("com-uninitialize", lambda: pythoncom.CoUninitialize(), initialized),
        ):
            if needed:
                try:
                    # Cleanup failures remain separate from the first business error.
                    function()
                    report.setdefault("cleanup_completed", []).append(label)
                except BaseException as exc:
                    report["cleanup_errors"].append(dict(stage=label, type=type(exc).__name__, message=str(exc)))
        if old_trace is None:
            os.environ.pop("SWCLI_TRACE_NATIVE_CALLS", None)
        else:
            os.environ["SWCLI_TRACE_NATIVE_CALLS"] = old_trace
        report["success"] = (report.get("plan_complete") is True and "failure" not in report
            and not report["cleanup_errors"] and report.get("allowlist_restored") is True
            and "wait-owned-exit" in report.get("cleanup_completed", []))
        engine.persist()
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
