"""Contracts for the separately scheduled public STEP periodic-face gate."""

from hashlib import sha256
import json
from pathlib import Path

from swcli.hosts.windows_step_export import verify_step_output

from .step_periodic_evidence import PLAN, audit_cylinder_topology, require, verify_cylinder_mass


ENGLISH_HOST = "english"
CHINESE_HOST = "chinese-simplified"
LANGUAGE_REFUSAL = "StepSplitLanguageUnsupported"
WRITER_SCOPE = "step-public-periodic-cli-daemon"
LEGACY_SCOPE = "step-public-periodic-legacy-control"
TOGGLE = "swStepExportSplitPeriodic"
SAVE_CALL = "IModelDocExtension.SaveAs3"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def label(protocol, split):
    return f"{protocol}-split-{str(split).lower()}"


def export_arguments(path, protocol, split=None):
    arguments = ["document", "export", str(path), "--strict",
                 "--step-protocol", protocol, "--step-geometry", "solid-surface"]
    if split is not None:
        arguments.append("--step-split-periodic-faces" if split else "--no-step-split-periodic-faces")
    return arguments


def check_host(host, language):
    require(host.get("revision") == "33.5.0" and host.get("language") == language
            and host.get("owned_by_daemon") is True and host.get("visible") is False
            and host.get("shared_interactive") is False and type(host.get("process_id")) is int
            and host["process_id"] > 0, "periodic public gate requires the selected native language and an owned hidden 33.5.0 host")


def check_refusal(result, target, original):
    require(result.get("ok") is False and result.get("error", {}).get("type") == LANGUAGE_REFUSAL,
            "Chinese periodic export did not return the dedicated language refusal")
    require(result.get("mutation") == {"attempted": False, "may_have_changed": False}
            and "step_preferences" not in result and "save_attempted" not in result,
            "Chinese refusal reports STEP preference or save activity")
    require(target.read_bytes() == original, "Chinese refusal changed existing output")


def verify_export(path, protocol, split):
    if split is None:
        return verify_step_output(path, protocol, "solid-surface")
    from swcli.hosts.windows_step_export import verify_periodic_step_output

    return verify_periodic_step_output(path, protocol, "solid-surface")


def check_export(result, target, protocol, split):
    require(result.get("ok") is True and result.get("api_saved") is True
            and type(result.get("save_errors")) is int and result["save_errors"] == 0
            and type(result.get("save_warnings")) is int and result["save_warnings"] == 0,
            "public periodic case requires an actual clean native SaveAs3")
    document = result["document"]
    require(document["type"] == 1 and document["active"] is False and document["current"] is False
            and document["modified"] is False, "public background part was changed or activated")
    prefs = result["step_preferences"]
    keys = {"swStepAP", "swStepExportPreference"}
    if split is not None:
        keys.add(TOGGLE)
        require(prefs["requested"].get(TOGGLE) is split and type(prefs["before"].get(TOGGLE)) is bool,
                "periodic preference value or original differs")
    require(prefs["restored"] is True and prefs["before"] == prefs["after"]
            and all(set(prefs[key]) == keys for key in ("before", "requested", "after"))
            and prefs["requested"]["swStepAP"] == int(protocol[2:]),
            "public STEP preference scope or restoration differs")
    content = verify_export(target, protocol, split)
    require(content == result["step_output"] and Path(result["output"]) == target
            and Path(result["artifact"]["path"]) == target
            and result["artifact"]["size_bytes"] == target.stat().st_size,
            "public STEP output does not match its receipt")
    if split is not None:
        audit_cylinder_topology(target.read_bytes(), split)


def trace_members(pairs):
    members = {}
    for key, value in pairs:
        require(key not in members, "duplicate trace JSON member: " + key)
        members[key] = value
    return members


def reject_trace_constant(value):
    raise ValueError("nonfinite trace JSON value: " + value)


def request_trace(raw, request_id):
    require(type(request_id) is str and bool(request_id), "public CLI trace request ID is absent")
    rows = []
    for raw_line in raw.removeprefix(b"\xef\xbb\xbf").splitlines():
        line = raw_line.lstrip(b" \t")
        # Native stderr may also contain localized, non-JSON subprocess diagnostics.
        if not line.startswith(b"{"):
            continue
        row = json.loads(line.decode("utf-8"), object_pairs_hook=trace_members,
                         parse_constant=reject_trace_constant)
        if row.get("event") == "swcli.native-call" and row.get("request_id") == request_id:
            rows.append(row)
    require(rows and all(row["operation"] == "document.export" for row in rows)
            and len({row["worker_pid"] for row in rows}) == 1, "missing or mixed public worker trace")
    beginning, ending = rows[0], rows[-1]
    require((beginning["sequence"], beginning["stage"], beginning["phase"]) == (0, "operation", "begin")
            and (ending["sequence"], ending["stage"], ending["phase"]) == (0, "operation", "end"),
            "public export operation trace is incomplete")
    starts, finishes = {}, {}
    for row in rows[1:-1]:
        sequence = row["sequence"]
        require(type(sequence) is int and sequence > 0 and row["phase"] in ("begin", "end", "error"),
                "invalid native call trace row")
        table = starts if row["phase"] == "begin" else finishes
        require(sequence not in table and (row["phase"] == "begin" or sequence in starts),
                "out-of-order or duplicate native trace boundary")
        table[sequence] = (row["stage"], row["call"])
    require(starts == finishes and set(starts) == set(range(1, len(starts) + 1)),
            "unpaired or missing native call trace")
    return list(starts.values())


def check_export_trace(raw, case):
    calls = request_trace(raw, case["request_id"])
    preferences = [call for stage, call in calls
                   if stage == "step-export" or "GetUserPreference" in call or "SetUserPreference" in call]
    save = [call for _, call in calls if "SaveAs" in call]
    language = [i for i, (_, call) in enumerate(calls) if call == "GetCurrentLanguage"]
    if case["mode"] == "refusal":
        require(len(language) == 1, "Chinese refusal lacks one actual language read")
        require(not preferences and not save, "language refusal reached preference or native save calls")
    else:
        require(save == [SAVE_CALL] and preferences, "successful public export lacks one native SaveAs3 or STEP preference proof")
        has_periodic = any(TOGGLE in call or call.startswith("periodic-") for call in preferences)
        require(has_periodic == (case["mode"] == "periodic"), "legacy or periodic preference trace differs")
        if case["mode"] == "legacy":
            require(not language, "omitted periodic option reached the language gate")
        else:
            first_preference_or_save = next(i for i, (_, call) in enumerate(calls)
                                            if call in preferences or call == SAVE_CALL)
            require(len(language) == 1 and language[0] < first_preference_or_save,
                    "periodic export did not read language before preferences and SaveAs3")
    return dict(request_id=case["request_id"], mode=case["mode"], native_call_count=len(calls),
                step_preference_call_count=len(preferences), native_save_calls=save)


def run_writer(output, report, cli, stamp, context, documents, persist, *, legacy_only=False):
    language = report["host"]["language"]
    source = output / "public-cylinder.SLDPRT"
    doc = cli("create-cylinder", "document", "create", "--type", "part",
              operation="document.create")["document"]["document_id"]
    documents[doc] = None
    lease = cli("cylinder-lease", "document", "lease", "acquire", "--document", doc,
                "--ttl-seconds", "1800")["lease"]["lease_id"]
    documents[doc] = lease
    document_args = ["--document", doc, "--lease", lease]
    circle = cli("circle-r10", "sketch", "circle", "--plane", "front", "--radius-mm", "10",
                 *document_args, operation="sketch.circle")
    cli("extrude-h30", "feature", "extrude", circle["sketch"]["sketch_id"], "--depth-mm", "30",
        *document_args, operation="feature.extrude")
    cli("save-cylinder", "document", "save-as", str(source), *document_args, operation="document.save-as")
    verify_cylinder_mass(cli("measure-cylinder", "document", "measure", "--document", doc,
                             operation="document.measure"))
    report["source_sha256"] = digest(source)
    peer = cli("create-background-peer", "document", "create", "--type", "part",
               operation="document.create")["document"]["document_id"]
    documents[peer] = None
    source_before = cli("source-before-periodic", "document", "inspect", "--document", doc,
                        operation="document.inspect")["document"]
    peer_before = cli("peer-before-periodic", "document", "inspect", "--document", peer,
                      operation="document.inspect")["document"]

    report["trace_cases"] = []
    if legacy_only:
        target = output / "ap214-legacy.step"
        result = cli("ap214-legacy", *export_arguments(target, "ap214"), *context(doc, lease, stamp(doc)),
                     operation="document.export")
        check_export(result, target, "ap214", None)
        report["trace_cases"].append(dict(mode="legacy", request_id=result["request_id"]))
    elif language == CHINESE_HOST:
        sentinel = b"preserve-existing-output"
        for split in (False, True):
            target = output / (label("ap214", split) + ".step")
            target.write_bytes(sentinel)
            result = cli(label("ap214", split) + "-refusal", *export_arguments(target, "ap214", split),
                         "--overwrite", *context(doc, lease, stamp(doc)), error=LANGUAGE_REFUSAL)
            check_refusal(result, target, sentinel)
            report["trace_cases"].append(dict(mode="refusal", request_id=result["request_id"]))
            persist()
    else:
        for protocol, split in PLAN:
            case = label(protocol, split)
            target = output / (case + ".step")
            result = cli(case, *export_arguments(target, protocol, split), *context(doc, lease, stamp(doc)),
                         operation="document.export")
            check_export(result, target, protocol, split)
            report["outputs"].append(dict(protocol=protocol, split_periodic_faces=split,
                                          name=target.name, sha256=digest(target), request_id=result["request_id"]))
            report["trace_cases"].append(dict(mode="periodic", request_id=result["request_id"]))
            persist()

    require(cli("source-after-periodic", "document", "inspect", "--document", doc,
                operation="document.inspect")["document"] == source_before and digest(source) == report["source_sha256"],
            "public source changed")
    require(cli("peer-after-periodic", "document", "inspect", "--document", peer,
                operation="document.inspect")["document"] == peer_before,
            "foreground peer changed")


def writer_inputs(binding, expected_head):
    path = Path(binding["path"])
    raw = path.read_bytes()
    require(sha256(raw).hexdigest() == binding["sha256"], "public writer report digest differs")
    report = json.loads(raw)
    require(report["success"] is True and report["source_commit"] == expected_head
            and report["evidence_scope"] == WRITER_SCOPE and report["owned_exit_confirmed"] is True
            and type(report["daemon_returncode"]) is int and report["daemon_returncode"] == 0
            and not report["cleanup_errors"], "public writer terminal result did not pass")
    check_host(report["host"], ENGLISH_HOST)
    check_host(report["host_after"], ENGLISH_HOST)
    require(report["host_after"]["process_id"] == report["host"]["process_id"], "public writer host changed")
    require([row["mode"] for row in report["trace_cases"]] == ["periodic"] * len(PLAN)
            and len({row["request_id"] for row in report["trace_cases"]}) == len(PLAN),
            "public writer request plan differs")
    trace_path = path.with_name("daemon.stderr.log")
    trace = trace_path.read_bytes()
    require(sha256(trace).hexdigest() == report["daemon_trace_sha256"], "public writer trace changed")
    require([check_export_trace(trace, row) for row in report["trace_cases"]] == report["trace_observations"],
            "public writer recorded trace comparison differs")
    require(digest(path.parent / "public-cylinder.SLDPRT") == report["source_sha256"], "public writer source changed")
    rows = report["outputs"]
    require(len(rows) == len(PLAN), "public writer output count differs")
    inputs = []
    for row, (protocol, split), trace_case in zip(rows, PLAN, report["trace_cases"]):
        name = label(protocol, split) + ".step"
        require(row["protocol"] == protocol and row["split_periodic_faces"] is split and row["name"] == name
                and row["request_id"] == trace_case["request_id"],
                "public writer output plan differs")
        target = path.parent / name
        raw = target.read_bytes()
        require(sha256(raw).hexdigest() == row["sha256"], "public STEP output hash changed: " + name)
        verify_export(target, protocol, split)
        audit_cylinder_topology(raw, split)
        inputs.append((target, row["sha256"]))
    return report["host"]["process_id"], inputs
