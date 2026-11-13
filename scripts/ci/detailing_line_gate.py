"""Independent internal line-default plan and fail-closed evidence checks.

This module imports no COM runtime. A fake backend proves only the gate logic.
It never changes the production allowlist or promotes an internal result.
"""

import hashlib
import json
import math
from pathlib import Path
import time

from swcli.document_detailing import DETAILING_FIELDS
from swcli.document_detailing_lines import DETAILING_LINE_FIELDS, DETAILING_LINE_SNAPSHOT_FIELDS

PROFILE = "drawing-detailing-lines-v1"
READ = "document.detailing-line-options"
SET = "document.detailing-line-option-set"
GETTER = "IModelDocExtension.GetUserPreferenceToggle"
SETTER = "IModelDocExtension.SetUserPreferenceToggle"
DIRTY = "IModelDoc2.SetSaveFlag"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def options(value):
    require(type(value) is dict and set(value) == set(DETAILING_LINE_SNAPSHOT_FIELDS)
            and all(type(v) is bool for v in value.values()), "missing or non-boolean four-field snapshot")
    return dict(value)


def transitions(initial):
    """Euler circuit: each field flips both ways with either neighbor value."""
    current = options(initial)
    a, b = DETAILING_LINE_FIELDS
    edges = []
    for field in (a, b, a, b, b, a, b, a):
        before = dict(current)
        current[field] = not current[field]
        edges.append(dict(field=field, value=current[field], before=before, after=dict(current)))
    return edges


def file_proof(path):
    path = Path(path)
    require(path.is_file() and path.stat().st_size >= 512, "native drawing missing or truncated")
    return dict(path=str(path.resolve()), size=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def check_trace(envelope, operation, getters, setters):
    rows = envelope["trace"]
    request = envelope["request_id"]
    require(rows and all(row.get("request_id") == request and row.get("operation") == operation
                        for row in rows), "trace missing or borrowed from another request/profile")
    pending, calls, seen = {}, [], set()
    for row in rows:
        key = row["sequence"]
        if row["phase"] == "begin":
            require(type(key) is int and key >= 0 and key not in seen, "duplicate or invalid trace sequence")
            seen.add(key)
            pending[key] = row["call"]
            if key != 0:
                calls.append(row["call"])
        else:
            require(row["phase"] == "end" and pending.pop(key, None) == row["call"],
                    "incomplete or failed native trace")
            require(type(row.get("duration_ms")) in (int, float) and math.isfinite(row["duration_ms"]) and 0 <= row["duration_ms"] <= 600000,
                    "native call exceeded budget or duration is missing")
    require(not pending and rows[0]["sequence"] == rows[-1]["sequence"] == 0,
            "unclosed operation trace")
    require(all("UserPreference" not in call or call in (GETTER, SETTER) for call in calls),
            "unrelated preference API appeared in trace")
    require(calls.count(GETTER) == getters and calls.count(SETTER) == setters
            and calls.count(DIRTY) <= setters, "unexpected preference getter/setter/dirty counts")


def check_background(observed, *, readonly):
    require(type(observed["document_id"]) is str and observed["document_id"].startswith("d-"),
            "document identity missing")
    require(observed["read_only"] is readonly and observed["active"] is False
            and observed["current"] is False, "drawing is not the required background/read-only target")
    require(type(observed["update_stamp"]) is int and type(observed["modified"]) is bool,
            "drawing state unreadable")
    require(observed["normal_sheet"] is True, "unknown drawing edit context")


def check_result(envelope, operation, expected, *, changed=None, refused=False, getters=4):
    result = envelope["result"]
    check_trace(envelope, operation, getters, 1 if changed else 0)
    if result is None:
        raised = envelope.get("raised", {})
        allowed = {"stale-stamp": "DocumentUpdateConflict", "invalid-lease": "DocumentLeaseConflict"}
        require(refused and getters == 0 and raised.get("type") == allowed.get(envelope.get("mode")),
                "unexpected raised exception instead of guarded refusal")
        return
    require(result.get("action") == operation, "wrong operation evidence")
    if refused:
        require(result.get("ok") is False and result.get("mutation") ==
                {"attempted": False, "may_have_changed": False}, "expected refusal attempted mutation")
        return
    require(result.get("ok") is True and options(result.get("options")) == expected,
            "operation failed or full snapshot differs")
    if operation == SET:
        require(result.get("changed") is changed and result.get("mutation") ==
                {"attempted": changed, "may_have_changed": changed}, "unexpected mutation receipt")
        if changed:
            require(result.get("native_return") is True, "setter did not return strict true")


class Gate:
    def __init__(self, backend, output, report):
        self.backend, self.output, self.report = backend, Path(output), report
        self.requests = set()
        self.report.update(schema_version=1, profile=PROFILE, public_acceptance=False, full_acceptance_eligible=False,
                           native_timeout_seconds=600, group_timeout_seconds=1800, writes=[])

    def persist(self):
        (self.output / "report.json").write_text(json.dumps(self.report, indent=2) + "\n", encoding="utf-8")

    def step(self, name, function, record, key):
        # Persist the slot before invoking: a failure keeps earlier receipts and
        # the exact first failed boundary rather than returning a success stub.
        record[key] = {"pending": True}
        self.persist()
        def event(phase, **extra):
            with (self.output / "progress.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(dict(call=name, phase=phase, time=time.monotonic(), wall_time=time.time(), **extra)) + "\n")
        event("begin")
        try:
            value = function()
            record[key] = value
            self.persist()
            event("end")
            return value
        except BaseException as exc:
            record.setdefault("first_failure", dict(stage=name, type=type(exc).__name__, message=str(exc)))
            self.persist()
            event("error", error=str(exc))
            raise

    def fresh_request(self, envelope):
        request = envelope.get("request_id")
        require(type(request) is str and request and request not in self.requests, "borrowed/repeated request evidence")
        self.requests.add(request)

    def unchanged_files(self):
        for record in self.report["writes"]:
            if "file" in record:
                require(file_proof(record["file"]["path"]) == record["file"], "retained drawing bytes changed")

    def observe(self, record, key, *, readonly=False):
        value = self.step(key, self.backend.observe, record, key)
        check_background(value, readonly=readonly)
        return value

    def invoke(self, record, key, operation, expected, *, field=None, value=None,
               mode="normal", changed=None, refused=False, getters=4, cas=None):
        envelope = self.step(key, lambda: self.backend.invoke(operation, field, value, expected if cas is None else cas, mode), record, key)
        self.fresh_request(envelope)
        # Preserve the first API error separately if validation or trace
        # checks also fail; never replace a partial setter receipt.
        if not refused and envelope.get("result") is not None and envelope["result"].get("ok") is False:
            self.report.setdefault("first_business_error", envelope["result"].get("error"))
            self.persist()
        # Native result schema validation follows persistence of the raw result.
        if envelope["result"] is not None:
            self.backend.validate(operation, envelope["result"])
        check_result(envelope, operation, expected, changed=changed, refused=refused, getters=getters)
        return envelope

    def run_plan(self):
        initial_state = self.observe(self.report, "initial_state")
        initial = self.step("initial_read", lambda: self.backend.invoke(READ, None, None, None, "normal"),
                            self.report, "initial_read")
        self.fresh_request(initial)
        self.backend.validate(READ, initial["result"])
        current = options(initial["result"].get("options"))
        check_result(initial, READ, current)
        require(initial["result"].get("write_enabled") is False, "production new-write gate must remain closed")
        require(self.observe(self.report, "after_initial_read") == initial_state, "initial read changed state")
        self.step("enable_owned_internal_profile", self.backend.enable_internal, self.report, "internal_scope")
        used_ids = {initial_state["document_id"]}
        for index, edge in enumerate(transitions(current), 1):
            record = dict(index=index, **edge)
            self.report["writes"].append(record)
            before = self.observe(record, "state_before")
            require(before["layout"] == initial_state["layout"] and before["foreground"] == initial_state["foreground"],
                    "fixture layout/foreground drift before write")
            self.invoke(record, "write", SET, edge["after"], field=edge["field"], value=edge["value"],
                        changed=True, getters=12, cas=edge["before"])
            require(record["write"]["result"].get("before") == edge["before"], "write CAS was not full current snapshot")
            after = self.observe(record, "state_after")
            require(after["document_id"] == before["document_id"] and after["layout"] == before["layout"]
                    and after["foreground"] == before["foreground"] and after["modified"] is True,
                    "write changed identity/layout/foreground or failed to mark dirty")
            self.unchanged_files()
            # A conflict deliberately includes an OLD guard: a new-only CAS is insufficient.
            wrong = dict(edge["after"])
            old_field = next(iter(DETAILING_FIELDS))
            wrong[old_field] = not wrong[old_field]
            for key, expected, mode, refused, getters in (
                ("noop", edge["after"], "normal", False, 4),
                ("old_guard_cas_refusal", wrong, "normal", True, 4),
                ("stale_stamp_refusal", edge["after"], "stale-stamp", True, 0),
                ("lease_refusal", edge["after"], "invalid-lease", True, 0),
            ):
                self.invoke(record, key, SET, expected, field=edge["field"], value=edge["value"],
                            mode=mode, changed=False, refused=refused, getters=getters)
                require(self.observe(record, key + "_state") == after, "no-op/refusal changed drawing state")
                self.unchanged_files()
            path = self.output / ("line-defaults-%02d.SLDDRW" % index)
            saved = self.step("save", lambda: self.backend.save(path), record, "save")
            require(saved.get("ok") is True and saved.get("api_saved") is True and saved.get("save_errors") == 0
                    and saved.get("save_warnings") is None and saved["document"]["modified"] is False,
                    "native save failed or produced warning/dirty state")
            proof = record["file"] = file_proof(path)
            self.unchanged_files()
            for readonly in (True, False):
                label = "readonly" if readonly else "writable"
                retired = record["state_after"]["document_id"] if readonly else record["readonly_state"]["document_id"]
                closed = self.step("close_before_" + label, self.backend.close, record, "close_before_" + label)
                require(closed.get("retired_id") == retired and closed.get("native_catalog_count") == 1
                        and closed.get("stale_id_refused") is True, "close/retirement proof missing")
                opened = self.step("reopen_" + label, lambda: self.backend.reopen(path, readonly), record, "reopen_" + label)
                require(opened.get("ok") is True and opened.get("api_errors") == opened.get("api_warnings") == 0
                        and opened.get("read_only") is readonly, "drawing reopen failed or warned")
                state = self.observe(record, label + "_state", readonly=readonly)
                require(state["document_id"] not in used_ids, "reopened drawing reused retired document identity")
                used_ids.add(state["document_id"])
                require(state["modified"] is False and state["layout"] == initial_state["layout"]
                        and state["foreground"] == initial_state["foreground"], "reopen changed layout/foreground or dirty state")
                self.invoke(record, label + "_read", READ, edge["after"])
                if readonly:
                    self.invoke(record, "readonly_refusal", SET, edge["after"], field=edge["field"],
                                value=not edge["value"], changed=False, refused=True, getters=0)
                require(self.observe(record, label + "_after", readonly=readonly) == state,
                        "reopened read/refusal changed state")
                require(file_proof(path) == proof, "reopen/read/refusal changed saved drawing bytes")
            self.unchanged_files()
            record["file_after"] = file_proof(path)
            record["success"] = True
            self.persist()
        require(len(self.report["writes"]) == 8, "incomplete eight-edge plan")
        self.report["plan_complete"] = True
        self.persist()
