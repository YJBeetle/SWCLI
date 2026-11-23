"""Installed CLI/daemon acceptance for the two calibrated drawing line defaults."""

from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import time

from swcli import __version__
from swcli.document_detailing_lines import DETAILING_LINE_FIELDS, DETAILING_LINE_SNAPSHOT_FIELDS
from swcli.hosts.windows_document_detailing import _native_windows
from swcli.mcp import DaemonBridge
from swcli.result_schemas import validate_operation_result
from swcli.sdk import Client


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy = load("verify-detailing-public")
internal = load("verify-detailing-lines-calibration")
support = legacy.support
require = legacy.require
READ, SET = internal.gate.READ, internal.gate.SET
WIDTH = len(DETAILING_LINE_SNAPSHOT_FIELDS)
GUARDS = {"auto_center_marks.part_holes": True, "auto_center_marks.part_fillets": False}
REVISION = "33.5.0"


class PublicGate(support.AnnotationSmoke):
    @contextmanager
    def boundary(self, name):
        def event(phase):
            with (self.directory / "progress.jsonl").open("a", encoding="utf-8") as progress:
                progress.write(json.dumps(dict(call=name, phase=phase, time=time.monotonic())) + "\n")
        event("begin")
        try:
            yield
        except BaseException:
            try:
                event("error")
            except OSError as exc:
                self.record.setdefault("progress_errors", []).append(str(exc))
            raise
        else:
            event("end")

    def command(self, *arguments, **kwargs):
        with self.boundary(".".join(map(str, arguments[:2]))):
            return super().command(*arguments, **kwargs)


def read(gate, trace, document):
    result = gate.command("document", "detailing-line-options", document=document)
    validate_operation_result(READ, result)
    gate.background(result, document)
    trace.cli(gate, getters=WIDTH, setters=0)
    require(result["write_enabled"] is True
            and all(result["options"][field] is value for field, value in GUARDS.items()),
            "drawing does not match the calibrated legacy guards")
    return result


def edit(gate, trace, document, before, field, value, *,
         expected=None, error=None, session=None, stamp=None, read_only=False):
    snapshot = before["options"] if expected is None else expected
    stamp = before["document"]["update_stamp"] if stamp is None else stamp
    result = gate.command("document", "detailing-line-option-set", field, str(value).lower(),
                          "--if-options", json.dumps(snapshot), "--if-update-stamp", stamp,
                          document=document, lease=gate.leases[document], session=session,
                          expected_error=error)
    transport_refusal = error in ("DocumentLeaseConflict", "DocumentUpdateConflict")
    if not transport_refusal:
        validate_operation_result(SET, result)
        gate.background(result, document)
    changed = error is None and before["options"][field] is not value
    trace.cli(gate, getters=0 if read_only or transport_refusal else WIDTH * (3 if changed else 1),
              setters=int(changed))
    if transport_refusal:
        return result
    require(result["mutation"] == {"attempted": changed, "may_have_changed": changed},
            "write did not report the expected mutation boundary")
    if error is None:
        require(result["before"] == snapshot and result["options"] == {**snapshot, field: value}
                and result["changed"] is changed, "public write violated its exact four-value snapshot")
        if changed:
            require(result["native_return"] is True and result["document"]["modified"] is True,
                    "native setter return or dirty state was not confirmed")
        else:
            require(result["document"] == before["document"], "no-op changed the document")
    return result


def contracts(gate, trace, document, before):
    field = next(iter(DETAILING_LINE_FIELDS))
    context = dict(document_id=document, expected_update_stamp=before["document"]["update_stamp"])
    params = dict(field=field, value=before["options"][field], expected_options=before["options"])
    client = Client(endpoint=gate.endpoint, session_id=gate.session, timeout_seconds=600)
    bridge = DaemonBridge(endpoint=gate.endpoint, session_id=gate.session, timeout_seconds=600)
    evidence = gate.record["sdk_mcp_contracts"] = {}
    with gate.boundary("SDK.read"):
        reply = client.document.detailing_line_options(**context)
        evidence["sdk_read"] = dict(reply.raw)
        require(reply.require_result() == before, "SDK read differs from installed CLI")
        trace.verify(reply.request_id, READ, getters=WIDTH, setters=0)
    with gate.boundary("MCP.capabilities"):
        capability = bridge.call("capabilities", {"operation": SET})
        evidence["mcp_capabilities"] = capability
        require(capability["success"], "MCP capabilities failed")
        schema = capability["result"]["operation_schemas"][SET]
        require(schema["x-swcli-context"] == {**dict.fromkeys(context, "required"), "lease_id": "required"}
                and set(schema["properties"]["field"]["enum"]) == set(DETAILING_LINE_FIELDS)
                and set(schema["properties"]["expected_options"]["required"]) == set(DETAILING_LINE_SNAPSHOT_FIELDS),
                "MCP misstated the two writable fields or four-value CAS")
    context["lease_id"] = gate.leases[document]
    with gate.boundary("SDK.noop"):
        reply = client.document.detailing_line_option_set(**context, **params)
        evidence["sdk_noop"] = dict(reply.raw)
        sdk = reply.require_result()
        trace.verify(reply.request_id, SET, getters=WIDTH, setters=0)
        require(sdk["options"] == before["options"] and sdk["document"] == before["document"]
                and sdk["changed"] is False and sdk["mutation"] == {"attempted": False, "may_have_changed": False},
                "SDK no-op changed state")
    with gate.boundary("MCP.noop"):
        reply = bridge.call("execute", {"operation": SET, "parameters": params, **context})
        evidence["mcp_noop"] = reply
        require(reply["success"] and reply["result"] == sdk, "MCP no-op differs from typed SDK")
        validate_operation_result(SET, reply["result"])
        trace.verify(reply["request_id"], SET, getters=WIDTH, setters=0)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def retained_foreground(gate, document, foreground):
    result = gate.command("document", "list")
    documents = {doc["document_id"]: doc for doc in result["documents"]}
    require(result["count"] == 2 and set(documents) == {document, foreground},
            "daemon document catalog differs from the two owned fixtures")
    front = documents[foreground]
    require(front["active"] is True and front["current"] is True and front["type"] == 1
            and documents[document]["active"] is False and documents[document]["current"] is False,
            "foreground or current drawing state changed")
    return front


def run(gate, trace, template):
    health = gate.health()
    host = health["host"]
    gate.record["host"] = host
    require(health["server_version"] == __version__ and host["owned_by_daemon"] is True
            and host["shared_interactive"] is False and host["visible"] is False
            and host["platform"] == "windows", "public validation requires its own hidden Windows daemon")
    gate.host_handle = gate.capture_process(host["process_id"])
    require(host["revision"] == REVISION, "public validation requires the calibrated exact revision")
    gate.require_empty()
    made = gate.command("document", "create", "--type", "drawing", "--template", template, "--projection", "first-angle")
    require(made["created"] is True and made["document"]["type"] == 3 and made["views"] == [],
            "fixture must be an empty drawing")
    document, foreground = made["document"]["document_id"], gate.create()
    used_drawings = {document}
    gate.command("document", "lease", "acquire", "--ttl-seconds", 1800, document=document)
    current = gate.record["initial"] = read(gate, trace, document)
    plan = internal.gate.transitions(current["options"])
    first = plan[0]
    gate.record["lease_refusal"] = edit(gate, trace, document, current, first["field"], first["value"],
                                         session=gate.session + "-contender", error="DocumentLeaseConflict")
    gate.record["stamp_refusal"] = edit(gate, trace, document, current, first["field"], first["value"],
                                        stamp=current["document"]["update_stamp"] + 1, error="DocumentUpdateConflict")
    require(read(gate, trace, document) == current, "lease or stamp refusal changed drawing state")
    for index, edge in enumerate(plan, 1):
        field, value = edge["field"], edge["value"]
        row = dict(index=index, **edge)
        gate.record["writes"].append(row)
        require(current["options"] == edge["before"], "current drawing differs from the ordered transition")
        front_before = row["foreground_before"] = retained_foreground(gate, document, foreground)
        stale = dict(edge["before"])
        old_field = next(iter(GUARDS))
        stale[old_field] = not stale[old_field]
        row["cas_refusal"] = edit(gate, trace, document, current, field, value, expected=stale, error="ValueError")
        require(read(gate, trace, document) == current, "legacy-value CAS refusal changed state")
        changed = row["write"] = edit(gate, trace, document, current, field, value)
        row["noop"] = edit(gate, trace, document, changed, field, value)
        require(read(gate, trace, document)["options"] == edge["after"], "post-write read differs")
        row["foreground_after"] = retained_foreground(gate, document, foreground)
        require(row["foreground_after"] == front_before, "write or refusal changed the retained foreground part")
        saved = row["save"] = support.save_copy(gate, document, f"public-line-defaults-{index:02d}.SLDDRW", "SLDDRW")
        for read_only, access in ((True, "readonly"), (False, "writable")):
            retired = document
            gate.close(document)
            row[access + "_retired"] = gate.command("document", "inspect", document=retired, expected_error="DocumentNotFound")
            gate.close(foreground)
            gate.require_empty()
            opened, document, foreground = support.open_background(gate, saved["host_path"], 3, read_only=read_only)
            row[access + "_open"] = opened
            require(document not in used_drawings, "reopened drawing reused a retired document ID")
            used_drawings.add(document)
            current = row[access + "_read"] = read(gate, trace, document)
            require(current["options"] == edge["after"], "public save/reopen lost the four-value snapshot")
            gate.command("document", "lease", "acquire", "--ttl-seconds", 1800, document=document)
            if read_only:
                row["readonly_refusal"] = edit(gate, trace, document, current, field, not value,
                                               error="ValueError", read_only=True)
                require(read(gate, trace, document) == current, "read-only refusal changed drawing state")
            require(digest(saved["path"]) == saved["sha256"], "reopen or observation changed saved bytes")
    contracts(gate, trace, document, current)
    gate.close(document)
    gate.close(foreground)
    gate.require_empty(after_case="document-detailing-lines-public")
    require(all(digest(row["save"]["path"]) == row["save"]["sha256"] for row in gate.record["writes"]),
            "a later transition modified an earlier native original")
    gate.record["host_after"] = gate.health()["host"]
    require(gate.record["host_after"] == host, "public validation replaced the owned host")
    gate.record.update(state="completed", success=True, elapsed_seconds=time.monotonic() - gate.group_started)


def main(argv=None):
    args, output, supervision = internal.supervised_worker(__doc__, argv)
    if args.supervision_probe:
        return 0
    require(_native_windows(), "public gate requires native Windows")
    require(args.wheel is not None and args.swconst.is_file() and args.drawing_template.is_file(),
            "public gate requires the installed wheel, official swconst and GB drawing template")
    _, head, runtime = internal.candidate_runtime(args)
    lifecycle = load("verify-through-all-calibration")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        endpoint = f"127.0.0.1:{sock.getsockname()[1]}"
    gate = PublicGate(directory=output, host_directory=str(output), endpoint=endpoint)
    gate.record_path = output / "public-detailing-lines.json"
    gate.record.update(profile="document-detailing-lines-public", source_commit=head, runtime=runtime,
                       supervision=supervision, writes=[], swconst_sha256=digest(args.swconst),
                       drawing_template_sha256=digest(args.drawing_template),
                       evidence_kind="installed-public-cli-daemon-gate", full_acceptance_eligible=False)
    gate.capture_process, gate.host_handle = lifecycle.capture_process, None

    def confirm_exit(gate, daemon):
        require(gate.host_handle is not None, "owned SOLIDWORKS process exit is unconfirmed")
        try:
            lifecycle.wait_process(gate.host_handle)
            gate.record["owned_host_exit_confirmed"] = True
            require(daemon is not None and daemon.returncode == 0, "owned daemon exit is unconfirmed")
        finally:
            gate.host_handle.Close()

    return legacy.run_owned_public(gate, str(args.drawing_template.resolve()), run_gate=run,
                                   snapshot_width=WIDTH, confirm_exit=confirm_exit)


if __name__ == "__main__":
    raise SystemExit(main())
