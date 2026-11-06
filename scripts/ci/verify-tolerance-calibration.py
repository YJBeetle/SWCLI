"""Opt-in internal calibration only; never public acceptance or a release gate.

Owned disposable host, generated part/assembly/drawing. First failure stops all
cases. Supervisor bounds each native span at 600s and the entire group at 1800s.
"""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
from swcli.hosts.native_trace import trace_native_request
from unittest import mock

from swcli.daemon.documents import DocumentRegistry
from swcli.daemon.operations import execute_operation
from swcli.document_tolerances import TOLERANCE_FIELDS, native_constants
from swcli.hosts import windows_document_tolerances as adapter
from swcli.hosts.windows import _com_value
from swcli.hosts.windows_parts import create_part_windows_with_handle
from swcli.hosts.windows_assemblies import create_assembly_windows_with_handle
from swcli.hosts.windows_drawings import create_drawing_windows_with_handle
from swcli.hosts.windows_sketches import create_rectangle_sketch_windows_with_handle
from swcli.hosts.windows_features import extrude_sketch_windows_with_handle
from swcli.hosts.windows_measurements import measure_part_windows
from swcli.hosts.windows_native_files import save_as_native_windows
from swcli.hosts.windows_documents import open_windows_document_with_handle
from swcli.result_schemas import validate_operation_result

spec = importlib.util.spec_from_file_location("_tolerance_owned_harness", Path(__file__).with_name("verify-through-all-calibration.py"))
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
checked = harness.checked


def calibrate_case(app, output, constants, plane, reverse, call, case, report, live, *, profile_kind, drawing_template):
    case.update(kind=profile_kind, success=False, internal_calibration=True)
    if profile_kind == "drawing":
        made, document = call("create-drawing", lambda:create_drawing_windows_with_handle(
            app=app,template=str(drawing_template),projection="first-angle"))
    else:
        creator = create_part_windows_with_handle if profile_kind == "part" else create_assembly_windows_with_handle
        made, document = call("create-"+profile_kind,lambda:creator(app=app))
    live["document"] = document
    case["creation"] = made
    checked(made["ok"] and document is not None,"owned fixture creation failed")
    if profile_kind == "part":
        rectangle, sketch = call("create-profile",lambda:create_rectangle_sketch_windows_with_handle(
            app=app,document=document,plane="front",width_mm=40,height_mm=30))
        checked(rectangle["ok"] and not rectangle.get("warnings") and sketch is not None,"profile creation failed")
        boss, feature = call("create-boss",lambda:extrude_sketch_windows_with_handle(
            app=app,document=document,sketch_feature=sketch,depth_mm=10))
        checked(boss["ok"] and not boss.get("warnings") and feature is not None,"boss creation failed")
        measured=call("measure-before",lambda:measure_part_windows(document=document))
        case["geometry_before"]=measured
        checked(measured["ok"],"initial measurement failed")
        harness.verify_geometry(measured["metrics"],10,cut=False)
    # Keep an independently owned foreground throughout every tolerance operation.
    front_made, foreground=call("create-foreground",lambda:create_part_windows_with_handle(app=app))
    checked(front_made["ok"] and foreground is not None,"foreground creation failed")
    registry=DocumentRegistry(app)
    entry=registry.register(document)
    registry.set_current(registry.register(foreground),session_id="calibration")
    lease=registry.acquire_lease(entry,session_id="calibration",ttl_seconds=1800)["lease_id"]
    def operation(name,values=None):
        with trace_native_request("tolerance-calibration-"+uuid.uuid4().hex,name):
            result=execute_operation(app,name,values or {},documents=registry,session_id="calibration",
                document_id=entry.document_id,expected_update_stamp=_com_value(document,"GetUpdateStamp"),
                lease_id=lease if name.endswith("-set") else None)
        case.setdefault("operations",[]).append(result)
        validate_operation_result(name,result)
        checked(not result["document"]["active"] and not result["document"]["current"],"background identity changed")
        return result
    initial=call("read-defaults",lambda:operation("document.tolerances"))
    checked(initial["ok"] and initial["write_enabled"] is False,"public defaults read failed")
    report["tolerance_constants"]=native_constants()
    denied=call("public-writer-must-refuse",lambda:operation("document.tolerance-set",dict(
        field="linear.type",value="basic",expected_options=initial["options"])))
    checked(not denied["ok"] and denied["mutation"]==dict(attempted=False,may_have_changed=False),"unaccepted public write was enabled")
    expected=deepcopy(initial["options"])
    # This process-local patch is a test instrument. The distributed package's
    # PUBLIC_WRITE_FIELDS remains empty. No request/env parameter can enable it.
    with mock.patch.object(adapter,"PUBLIC_WRITE_FIELDS",frozenset(TOLERANCE_FIELDS)):
        for field,value in (("linear.type","basic"),("linear.type","none"),
                            ("linear.precision","0"),("linear.precision","8"),("linear.precision","3")):
            changed=call("candidate-"+field+"-"+value,lambda:operation("document.tolerance-set",dict(
                field=field,value=value,expected_options=expected)))
            checked(changed["ok"],"candidate failed: "+str(changed.get("error")))
            expected=deepcopy(changed["options"])
            same=call("candidate-noop",lambda:operation("document.tolerance-set",dict(
                field=field,value=value,expected_options=expected)))
            checked(same["ok"] and same["changed"] is False and same["mutation"]==dict(attempted=False,may_have_changed=False),"noop changed native state")
        stale=deepcopy(expected); stale["linear.precision"]=dict(value="2",native_value=2)
        refused=call("full-cas-conflict",lambda:operation("document.tolerance-set",dict(
            field="linear.type",value="basic",expected_options=stale)))
        checked(not refused["ok"] and refused["mutation"]==dict(attempted=False,may_have_changed=False),"stale full CAS did not refuse")
    if profile_kind == "part":
        measured=call("measure-after",lambda:measure_part_windows(document=document))
        case["geometry_after"]=measured
        checked(measured["ok"],"final measurement failed")
        harness.verify_geometry(measured["metrics"],10,cut=False)
        checked(measured["metrics"]==case["geometry_before"]["metrics"],"document defaults changed model geometry")
    path=output/("tolerances."+{"part":"SLDPRT","assembly":"SLDASM","drawing":"SLDDRW"}[profile_kind])
    saved=call("save-owned-fixture",lambda:save_as_native_windows(str(path),document=document))
    case["save"]=saved
    checked(saved["ok"] and saved["api_saved"] and saved["save_errors"]==0 and saved["save_warnings"] is None,"fixture save failed")
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    call("close-target",lambda:app.CloseDoc(_com_value(document,"GetTitle")))
    live["document"]=None
    call("close-first-foreground",lambda:app.CloseDoc(_com_value(foreground,"GetTitle")))
    opened,document=call("reopen-readonly",lambda:open_windows_document_with_handle(str(path),app=app,read_only=True))
    live["document"]=document
    checked(opened["ok"] and opened["api_errors"]==opened["api_warnings"]==0 and opened["read_only"] is True,"readonly reopen failed")
    front_made,foreground=call("create-reopen-foreground",lambda:create_part_windows_with_handle(app=app))
    checked(front_made["ok"] and foreground is not None,"readonly foreground creation failed")
    registry=DocumentRegistry(app); entry=registry.register(document)
    registry.set_current(registry.register(foreground),session_id="calibration")
    lease=registry.acquire_lease(entry,session_id="calibration",ttl_seconds=1800)["lease_id"]
    reopened=call("read-reopened",lambda:operation("document.tolerances"))
    checked(reopened["ok"] and reopened["options"]==expected and reopened["document"]["modified"] is False,"saved defaults did not persist")
    with mock.patch.object(adapter,"PUBLIC_WRITE_FIELDS",frozenset(TOLERANCE_FIELDS)):
        refused=call("readonly-write-refusal",lambda:operation("document.tolerance-set",dict(
            field="linear.type",value="basic",expected_options=expected)))
    checked(not refused["ok"] and refused["mutation"]==dict(attempted=False,may_have_changed=False),"readonly mutation was attempted")
    checked(hashlib.sha256(path.read_bytes()).hexdigest()==digest,"readonly operations changed fixture bytes")
    case["file_sha256"]=digest
    call("close-readonly",lambda:app.CloseDoc(_com_value(document,"GetTitle")))
    live["document"]=None
    call("close-foreground",lambda:app.CloseDoc(_com_value(foreground,"GetTitle")))
    checked(_com_value(app,"GetDocumentCount")==0,"fixture leaked native document")
    case["success"]=True


def supervise(args):
    args.output_dir.mkdir(parents=True,exist_ok=False)
    command=[sys.executable,"-I",str(Path(__file__).resolve()),"--worker","--output-dir",str(args.output_dir),
             "--swconst",str(args.swconst),"--drawing-template",str(args.drawing_template)]
    started=time.time()
    with (args.output_dir/"worker.stdout.log").open("w") as out, (args.output_dir/"worker.stderr.log").open("w") as err:
        process=subprocess.Popen(command,stdout=out,stderr=err)
        while process.poll() is None:
            time.sleep(0.5)
            now=time.time(); span_started=started
            trace=args.output_dir/"trace.jsonl"
            if trace.exists():
                lines=trace.read_text(encoding="utf-8").splitlines()
                if lines:
                    try:
                        last=json.loads(lines[-1])
                        if last.get("phase")=="begin": span_started=last["time"]
                        else: span_started=now
                    except (json.JSONDecodeError,KeyError): pass
            if now-started>=1800 or now-span_started>=600:
                (args.output_dir/"timeout.json").write_text(json.dumps(dict(
                    reason="group" if now-started>=1800 else "native_span",native_timeout_seconds=600,
                    group_timeout_seconds=1800,full_acceptance_eligible=False))+"\n")
                process.kill(); process.wait()
                return 124
        return process.returncode


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--swconst",type=Path,required=True)
    parser.add_argument("--drawing-template",type=Path,required=True)
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not args.worker: return supervise(args)
    def case_runner(*positional,**keywords):
        return calibrate_case(*positional,**keywords,drawing_template=args.drawing_template)
    return harness.run(args.output_dir,args.swconst,False,case_runner=case_runner,
        case_plan=[(kind,"front",False) for kind in ("part","assembly","drawing")],
        diagnostic_case="document-tolerances-internal-calibration")


if __name__=="__main__": raise SystemExit(main())
