"""Internal drawing defaults calibration; never public write acceptance.

One owned host, first failure stops, no retry/rollback/restart. The parent enforces
1800s total and each recorded stage enforces 600s, preserving the original trace.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from uuid import uuid4

from swcli.daemon.documents import DocumentRegistry
from swcli.daemon.operations import execute_operation
from swcli.document_line_font import LINE_FONT_FIELDS, CALIBRATED_LINE_FONT_REVISION
from swcli.hosts import windows_document_line_font as adapter
from swcli.hosts.windows import _com_value
from swcli.hosts.windows_drawings import create_drawing_windows_with_handle
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.hosts.windows_documents import open_windows_document_with_handle
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.result_schemas import validate_operation_result
from swcli.hosts.native_trace import trace_native_request

spec = importlib.util.spec_from_file_location("_line_font_harness", Path(__file__).with_name("verify-through-all-calibration.py"))
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
checked = harness.checked
_STARTUP_WATCHDOG = None


def timeout_watchdog(output, stage):
    def expired():
        (output / "native-timeout.json").write_text(json.dumps({"first_timeout_stage": stage, "seconds": 600}))
        os._exit(124)
    timer = threading.Timer(600, expired)
    timer.daemon = True
    timer.start()
    return timer


def calibrate(app, output, constants, plane, reverse, original_call, case, report, live, *, profile_kind, template):
    if _STARTUP_WATCHDOG is not None:
        _STARTUP_WATCHDOG.cancel()
    report.update(native_timeout_seconds=600, group_timeout_seconds=1800, public_writes_enabled=False)
    def call(name, function):
        timer = timeout_watchdog(output, name)
        try:
            with trace_native_request("line-font-" + uuid4().hex, name):
                return original_call(name, function)
        finally:
            timer.cancel()
    made, document = call("create-owned-drawing", lambda: create_drawing_windows_with_handle(
        app=app, template=str(template), projection="first-angle"))
    live["document"] = document
    case["creation"] = made
    checked(made["ok"] and document is not None, "drawing creation failed")
    front = None
    try:
        front_result, front = call("create-foreground-part", lambda: create_part_windows_with_handle(app=app))
        checked(front_result["ok"] and front is not None, "foreground creation failed")
        registry = DocumentRegistry(app)
        entry, foreground = registry.register(document), registry.register(front)
        registry.set_current(foreground, session_id="line-font")
        lease = registry.acquire_lease(entry, session_id="line-font", ttl_seconds=1800)
        case["official_constants"] = call("read-official-line-font-constants", adapter._constants)
        def read():
            result = execute_operation(app, "document.line-font", {}, documents=registry,
                session_id="line-font", document_id=entry.document_id,
                expected_update_stamp=_com_value(document, "GetUpdateStamp"))
            validate_operation_result("document.line-font", result)
            checked(result["ok"], "line font read failed: " + str(result))
            checked(not result["document"]["active"] and not result["document"]["current"], "background selection changed")
            return result
        case["initial"] = call("public-background-read", read)
        observed = case["initial"]["options"]
        # Historical closed-gate proof lives in the original artifact. Once the
        # exact revision is calibrated, do not make a public mutation here.
        if report["host"]["revision"] != CALIBRATED_LINE_FONT_REVISION:
            rejected = call("prove-public-write-closed", lambda: execute_operation(app, "document.line-font-set",
                dict(field="visible_edges.style", value=1, expected_options=observed), documents=registry,
                session_id="line-font", document_id=entry.document_id, lease_id=lease["lease_id"],
                expected_update_stamp=_com_value(document, "GetUpdateStamp")))
            case["public_write_rejection"] = rejected
            checked(not rejected["ok"] and rejected["error"]["type"] == "DocumentLineFontUncalibrated"
                    and not rejected["mutation"]["attempted"], "public write gate was bypassed")
        else:
            case["public_gate"] = "calibrated revision; public acceptance is a separate gate"
        for field in LINE_FONT_FIELDS:
            expected_stamp = _com_value(document, "GetUpdateStamp")
            registry.require_lease(entry, session_id="line-font", lease_id=lease["lease_id"])
            checked(_com_value(document, "GetUpdateStamp") == expected_stamp, "stamp changed before internal write")
            target = 1 if observed[field] != 1 else 0
            result = call("internal-single-write-" + field, lambda: adapter.set_document_line_font_windows(
                app=app, document=document, field=field, value=target, expected_options=observed,
                _internal_calibration=True))
            case.setdefault("internal_writes", []).append(result)
            checked(result["ok"] and result["changed"] and result["mutation"]["attempted"],
                    "internal line font write failed: " + str(result))
            checked(result["options"] == {**observed, field: target}, "unrequested default changed")
            observed = result["options"]
            checked(call("public-readback-" + field, read)["options"] == observed, "public/internal readback differs")
        case["final_options"] = observed
        checked(_com_value(app, "GetProcessID") == report["host"]["process_id"], "host changed")
    finally:
        if front is not None:
            call("close-foreground", lambda: app.CloseDoc(_com_value(front, "GetTitle")))
    path = output / "line-font.SLDDRW"
    saved = case["save"] = call("save-owned-drawing", lambda: save_as_native_windows(str(path), document=document))
    checked(saved["ok"] and path.is_file(), "drawing save failed")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    call("close-owned-drawing", lambda: app.CloseDoc(_com_value(document, "GetTitle")))
    live["document"] = None
    reopened, document = call("reopen-readonly", lambda: open_windows_document_with_handle(str(path), app=app, read_only=True))
    live["document"] = document
    checked(reopened["ok"] and document is not None, "reopen failed")
    result = case["reopened"] = call("read-reopened", lambda: adapter.read_document_line_font_windows(app=app, document=document))
    checked(result["ok"] and result["options"] == case["final_options"], "line font defaults did not persist")
    rejected = call("readonly-write-rejected", lambda: adapter.set_document_line_font_windows(
        app=app, document=document, field="visible_edges.style", value=0,
        expected_options=result["options"], _internal_calibration=True))
    checked(not rejected["ok"] and not rejected["mutation"]["attempted"], "readonly write was attempted")
    checked(not _com_value(document, "GetSaveFlag") and hashlib.sha256(path.read_bytes()).hexdigest() == digest,
            "readonly observation modified drawing")
    case.update(file_sha256=digest, success=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--drawing-template", type=Path, required=True)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.child:
        args.output_dir.mkdir(parents=True)
        with (args.output_dir / "process.log").open("w") as log:
            try:
                return subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()),
                    "--output-dir", str(args.output_dir.resolve()), "--drawing-template", str(args.drawing_template),
                    "--child"], stdout=log, stderr=log, timeout=1800).returncode
            except subprocess.TimeoutExpired:
                (args.output_dir / "group-timeout.json").write_text('{"seconds":1800}')
                return 124
    global _STARTUP_WATCHDOG
    os.environ["SWCLI_TRACE_NATIVE_CALLS"] = "1"
    _STARTUP_WATCHDOG = timeout_watchdog(args.output_dir, "owned-host-startup")
    def run_case(*a, **k):
        try:
            return calibrate(*a, **k, template=args.drawing_template)
        finally:
            timeout_watchdog(args.output_dir, "owned-host-cleanup")
    return harness.run(args.output_dir.resolve(), Path(r"C:\Program Files\SOLIDWORKS\swconst.tlb"), False,
        case_runner=run_case,
        case_plan=[("drawing", "front", False)], diagnostic_case="internal-document-line-font")


if __name__ == "__main__":
    raise SystemExit(main())
