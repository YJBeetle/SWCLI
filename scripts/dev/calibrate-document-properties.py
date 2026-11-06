"""LOCAL explicit-PID diagnosis; never starts, hides, exits or kills SOLIDWORKS.

Not public CLI/lease acceptance. Soft native/group budgets are 600/1800 seconds.
An external watchdog must enforce hard limits. Only this run's new documents
may be changed/closed. Preexisting native objects and visibility are preserved.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from uuid import uuid4

FONT_MEMBERS = (
    "TypeFaceName", "CharHeight", "CharHeightInPts", "Bold", "Italic", "Underline",
    "Strikeout", "BackWards", "UpsideDown", "Vertical", "WidthFactor",
    "CharSpacingFactor", "Escapement", "LineSpacing", "LineLength",
    "ObliqueAngle", "IsHeightSpecifiedInPts",
)
FONT_BOOL = {"Bold", "Italic", "Underline", "Strikeout", "BackWards", "UpsideDown", "Vertical", "IsHeightSpecifiedInPts"}
HEIGHT_MEMBERS = {"CharHeight", "CharHeightInPts", "IsHeightSpecifiedInPts"}
DISPLAY = {
    "grid.display": ("Toggle", "swGridDisplay", "all"),
    "grid.major_spacing_mm": ("Double", "swGridMajorSpacing", "all"),
    "grid.minor_lines_per_major": ("Integer", "swGridMinorLinesPerMajor", "all"),
    "grid.snap_points_per_minor": ("Integer", "swSnapPointsPerMinor", "all"),
    "virtual_sharp.style": ("Integer", "swDetailingVirtualSharpStyle", "all"),
    "plane.front_face_color": ("Integer", "swPlaneDisplayFrontFaceColor", "model"),
    "plane.back_face_color": ("Integer", "swPlaneDisplayBackFaceColor", "model"),
    "plane.intersection_line_color": ("Integer", "swPlaneDisplayIntersectionLineColor", "model"),
    "plane.transparency": ("Integer", "swPlaneDisplayTransparency", "model"),
    "plane.show_intersections": ("Toggle", "swPlaneDisplayShowIntersections", "model"),
}
ANNOTATIONS = {
    "arrow.edge_vertex": ("Integer", "swDetailingArrowStyleForEdgeVertexAttachment", "swDetailingNoOptionSpecified"),
    "arrow.face_surface": ("Integer", "swDetailingArrowStyleForFaceAttachment", "swDetailingNoOptionSpecified"),
    "arrow.unattached": ("Integer", "swDetailingArrowStyleForUnattached", "swDetailingNoOptionSpecified"),
    "bent_leader.enabled": ("Toggle", "swDetailingAnnotationUseBentLeaders", "swDetailingNoOptionSpecified"),
    "bent_leader.length_mm": ("Double", "swDetailingAnnotationBentLeaderLength", "swDetailingNoOptionSpecified"),
    "zero.leading": ("Integer", "swDetailingLeadingZero", "swDetailingAnnotation"),
    "zero.trailing": ("Integer", "swDetailingDimTrailingZero", "swDetailingAnnotation"),
}
STANDARD_SYMBOLS = (
    "swDetailingStandardANSI", "swDetailingStandardISO", "swDetailingStandardDIN",
    "swDetailingStandardJIS", "swDetailingStandardBS", "swDetailingStandardGOST",
    "swDetailingStandardGB", "swDetailingStandardUserDefined",
)
TEMPLATE_SYMBOLS = ("swDefaultTemplatePart", "swDefaultTemplateAssembly", "swDefaultTemplateDrawing")
SUFFIX = {"part": "SLDPRT", "assembly": "SLDASM", "drawing": "SLDDRW"}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()



def json_evidence(value):
    """Keep invalid native values representable without weakening validation.

    The in-memory report retains original values for exact type checks. Only
    evidence serialization tags NaN/Infinity or unexpected object types so a
    native observation failure cannot destroy the first-cause report.
    """
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) in (list, tuple):
        return [json_evidence(item) for item in value]
    if type(value) is dict:
        return {str(key): json_evidence(item) for key, item in value.items()}
    try:
        representation = repr(value)
    except Exception:
        representation = "<repr failed>"
    return {"invalid_native_value": {"type": type(value).__name__, "repr": representation}}


def process_ids():
    result = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe", "/FO", "CSV", "/NH"],
        text=True, timeout=15)
    return sorted(int(row[1]) for row in csv.reader(result.splitlines())
                  if len(row) > 1 and row[0].casefold() == "sldworks.exe")


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attach-pid", type=int, required=True)
    parser.add_argument("--owned-interface-stdin", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--isolated-host", action="store_true", help="Observe other SW process changes without requiring their survival; target guards remain strict")
    parser.add_argument("--stage", choices=("read", "fonts", "display", "standards"), required=True)
    parser.add_argument("--output", help="New independent directory below C:\\Workspace")
    parser.add_argument("--swconst", help="Installed official swconst.tlb")
    parser.add_argument("--part-template", help="Explicit installed PRTDOT for this diagnostic; no global preference change")
    parser.add_argument("--assembly-template", help="Explicit installed ASMDOT for this diagnostic; no global preference change")
    parser.add_argument("--drawing-template", default=r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\gb_a4.drwdot")
    parser.add_argument("--font-typeface", default="Arial")
    args = parser.parse_args()
    if args.attach_pid <= 0:
        parser.error("--attach-pid must be positive")
    return args


class Calibration:
    def __init__(self, args, *, owned_interface=None):
        owned_mode = getattr(args, "owned_interface_stdin", False)
        require(type(owned_mode) is bool, "invalid owned-interface mode")
        require((owned_mode and getattr(args, "isolated_host", False)
                 and type(owned_interface) is bytes and 0 < len(owned_interface) <= 65536)
                or (not owned_mode and owned_interface is None),
                "owned interface requires an authorized in-memory packet and isolated host")
        self._owned_interface_data = owned_interface
        self.args, self.started = args, time.monotonic()
        self.prefix = "swcli-docprops-" + args.stage + "-" + uuid4().hex[:12]
        self.output = Path(args.output or (str(Path(r"C:\Workspace\SWCLI-tests") / self.prefix))).resolve()
        workspace = Path(r"C:\Workspace").resolve()
        require(self.output != workspace and workspace in self.output.parents, "output must be a new directory below C:\\Workspace")
        self.output.mkdir(parents=True, exist_ok=False)
        self.trace = (self.output / "trace.jsonl").open("x", encoding="utf-8", buffering=1)
        self.report = {
            "diagnostic_case": "document-properties-local-attach-calibration",
            "full_acceptance_eligible": False, "stage": args.stage, "success": False,
            "prefix": self.prefix, "attach_pid": args.attach_pid,
            "isolated_host": bool(args.isolated_host),
            "other_process_policy": "observe-only" if args.isolated_host else "preserve-preexisting",
            "native_timeout_seconds": 600, "group_timeout_seconds": 1800,
            "timeout_enforcement": "soft checks; external hard watchdog required",
            "global_preference_setter_calls": 0, "host_start_calls": 0,
            "host_exit_calls": 0, "visibility_setter_calls": 0,
            "cases": [], "reads": {}, "cleanup_errors": [], "file_hashes": {}, "source_files": {},
            "script_sha256": digest(Path(__file__)), "python": sys.version, "python_process_id": os.getpid(),
            "font_typeface_installation": "not verified; exact native name readback required; no fallback installed",
            "standards_write_status": "pending; a finite observed_defaults field/option/document-type manifest must be calibrated first",
            "font_subtype_preservation": "not established: only annotation preference 19 is observed",
            "display_visual_effect": "not established: native settings/persistence diagnosis only",
        }
        self.report_changed()
        self.app, self.trusted, self.cleanup_mode = None, False, False
        self.originals, self.live, self.original_foreground = [], [], None
        self.restore_failed = False
        self._persisted_report_bytes = None
        self.persist()

    def report_changed(self):
        """Invalidate the durable snapshot after an evidence mutation, aliases included."""
        self._report_revision = getattr(self, "_report_revision", 0) + 1

    def checkpoint(self):
        # Native read-only calls do not repeatedly walk/serialize the whole report.
        # Explicit persist remains a forced observation for callers and diagnostics.
        if getattr(self, "_persisted_report_revision", -1) != getattr(self, "_report_revision", 0):
            self.persist()

    def persist(self):
        revision = getattr(self, "_report_revision", 0)
        # Compare complete serialized evidence, including every newly observed
        # getter value. A failed replace must never advance this cache.
        serialized = json.dumps(json_evidence(self.report), ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        content = serialized.replace("\n", os.linesep).encode("utf-8")
        if content == getattr(self, "_persisted_report_bytes", None):
            self._persisted_report_revision = revision
            return
        temporary = self.output / "report.tmp"
        with temporary.open("wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.output / "report.json")
        self._persisted_report_bytes = content
        self._persisted_report_revision = revision

    def event(self, row):
        self.trace.write(json.dumps(json_evidence(row), ensure_ascii=False, allow_nan=False) + "\n")
        self.trace.flush()
        os.fsync(self.trace.fileno())

    def call(self, label, function):
        if not self.cleanup_mode:
            require(time.monotonic() - self.started < 1800, "1800-second group budget exceeded")
        start = time.monotonic()
        self.event({"call": label, "phase": "begin", "time": time.time(), "cleanup": self.cleanup_mode})
        snapshot_ready = False
        checkpoint_start = time.monotonic()
        native_start = native_end = None

        def timings():
            now = time.monotonic()
            return {
                # elapsed_seconds retains the conservative wrapper budget used
                # by the watchdog. native_seconds measures function() only; a
                # function can itself be a guarded multi-COM SDK helper.
                "elapsed_seconds": now - start,
                "begin_trace_seconds": checkpoint_start - start,
                "checkpoint_seconds": (native_start if native_start is not None else now) - checkpoint_start,
                "native_seconds": None if native_start is None else (native_end if native_end is not None else now) - native_start,
                "native_started": native_start is not None,
                "native_completed": native_end is not None,
                "timing_scope": "wrapper before terminal trace fsync; native is function body, not necessarily one COM leaf",
            }

        try:
            self.checkpoint()
            snapshot_ready = True
            native_start = time.monotonic()
            value = function()
            native_end = time.monotonic()
            elapsed = native_end - start
            require(elapsed < 600, "600-second native call budget exceeded: " + label)
            if not self.cleanup_mode:
                require(time.monotonic() - self.started < 1800, "1800-second group budget exceeded after " + label)
            self.event({"call": label, "phase": "end", **timings()})
            return value
        except BaseException as error:
            failure = {"call": label, "type": type(error).__name__, "message": str(error), **timings()}
            self.report.setdefault("first_call_failure", failure)
            self.report_changed()
            try:
                # A pre-call snapshot failure is the cause, not permission to
                # retry the same I/O or to enter the native function.
                if snapshot_ready:
                    self.persist()
            except BaseException as report_error:
                failure["report_persist_failure"] = {
                    "type": type(report_error).__name__, "message": str(report_error)}
                self.report_changed()
            finally:
                self.event({**failure, "phase": "error"})
            raise

    def get(self, obj, name, label):
        return self.call(label + "." + name, lambda: self.com_value(obj, name))

    def same(self, first, second):
        return self.call("ISldWorks.IsSame", lambda: self.native_same(self.app, first, second))

    def export_constants(self):
        candidates = [Path(self.args.swconst)] if self.args.swconst else [
            Path(r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\swconst.tlb"),
            Path(r"C:\Program Files\SOLIDWORKS\swconst.tlb")]
        path = next((item for item in candidates if item.is_file()), None)
        require(path is not None, "installed official swconst.tlb missing")
        wanted = {"swDetailingAnnotationTextFormat", "swDetailingDimensionStandard", "swDetailingNoOptionSpecified", "swDontRebuildActiveDoc"}
        wanted.update(STANDARD_SYMBOLS + TEMPLATE_SYMBOLS)
        self.report_changed()
        wanted.update(spec[1] for spec in DISPLAY.values())
        self.report_changed()
        wanted.update(name for spec in ANNOTATIONS.values() for name in spec[1:])
        self.report_changed()
        if self.args.stage == "standards":
            wanted.update(("swDetailingGeometricTolerance", "swDetailingDetailView",
                           "swDetailingAuxiliaryView", "swDetailingSectionView"))
            self.report_changed()
        library = self.call("pythoncom.LoadTypeLib.swconst", lambda: self.pythoncom.LoadTypeLib(str(path)))
        found, rows, all_rows = {}, [], []
        for index in range(library.GetTypeInfoCount()):
            info = library.GetTypeInfo(index)
            attr = info.GetTypeAttr()
            if attr.typekind != self.pythoncom.TKIND_ENUM:
                continue
            enum_name = info.GetDocumentation(-1)[0]
            for position in range(attr.cVars):
                descriptor = info.GetVarDesc(position)
                name = info.GetDocumentation(descriptor[0])[0]
                row = {"enum": enum_name, "name": name, "value": descriptor.value}
                all_rows.append(row)
                self.report_changed()
                if name in wanted:
                    require(name not in found and type(descriptor.value) is int, "duplicate/non-integer required enum: " + name)
                    found[name] = descriptor.value
                    self.report_changed()
                    rows.append(row)
                    self.report_changed()
        self.report["swconst"] = {"path": str(path), "sha256": digest(path), "constants": found,
                                  "required_rows": rows, "missing": sorted(wanted - found.keys())}
        self.report_changed()
        (self.output / "swconst-enums.json").write_text(json.dumps(all_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.persist()
        require(wanted == found.keys(), "required swconst symbols missing: " + repr(wanted - found.keys()))
        require(found["swDetailingAnnotationTextFormat"] == 19 and found["swDetailingDimensionStandard"] == 13
                and found["swDetailingNoOptionSpecified"] == 0, "installed font/standard/option differs from candidate")
        self.constants = found
        self.report["virtual_sharp_members"] = [row for row in all_rows if row["enum"] == "swDetailingVirtualSharp_e"]
        self.report_changed()
        self.virtual_values = sorted({row["value"] for row in self.report["virtual_sharp_members"]})
        require(len(self.virtual_values) >= 2 and all(type(value) is int for value in self.virtual_values),
                "installed virtual-sharp enum cannot provide two typed target values")
        self.source_file(path, "installed-swconst")
        self.persist()

    def source_file(self, path, role):
        path = Path(path).resolve()
        require(path.is_file(), "required source file is missing: " + str(path))
        key = str(path)
        observed = {"sha256": digest(path), "size": path.stat().st_size}
        existing = self.report["source_files"].get(key)
        if existing is None:
            self.report["source_files"][key] = {**observed, "roles": [role]}
            self.report_changed()
        else:
            require(all(existing[name] == observed[name] for name in ("sha256", "size")),
                    "source changed since initial hash: " + key)
            if role not in existing["roles"]:
                existing["roles"].append(role)
                self.report_changed()
        self.persist()

    def documents(self, label):
        raw = self.get(self.app, "GetDocuments", label)
        docs = [] if raw is None else list(raw) if isinstance(raw, (tuple, list)) else None
        require(docs is not None and len(docs) <= 256, "native document catalog is not a bounded object array")
        count = self.get(self.app, "GetDocumentCount", label)
        require(type(count) is int and count == len(docs), "native document count mismatch")
        return docs

    def describe(self, document, label):
        return {"title": self.get(document, "GetTitle", label), "path": self.get(document, "GetPathName", label),
                "state": list(self.call(label + ".state", lambda: self.native_state(document)))}

    def identity_catalog(self, expected, label):
        actual = self.documents(label)
        require(len(actual) == len(expected), "unexpected document count: " + label)
        # Prove expected native identities are distinct at this checkpoint. A
        # diagonal-only shortcut would incorrectly accept duplicated objects.
        for index, document in enumerate(expected):
            require(not any(self.same(document, previous) for previous in expected[:index]),
                    "duplicate expected native document identity: " + label)
        # Match a complete fresh catalog bijectively. Distinct expected identities
        # and consuming each actual entry once reject duplicated/missing/foreign
        # actual objects, including same-title objects. No cross-checkpoint cache.
        unmatched = list(actual)
        for document in expected:
            match = next((index for index, other in enumerate(unmatched) if self.same(document, other)), None)
            require(match is not None, "native document identity changed: " + label)
            unmatched.pop(match)
        require(not unmatched, "unmatched native document identity: " + label)
        return actual

    def templates(self, label):
        result = {}
        for symbol in TEMPLATE_SYMBOLS:
            value = self.call(label + "." + symbol, lambda symbol=symbol: self.app.GetUserPreferenceStringValue(self.constants[symbol]))
            require(type(value) is str, "global template path is not a string")
            result[symbol] = value
            self.report_changed()
        return result

    def original_invariants(self, label, foreground=False):
        require(self.get(self.app, "GetProcessID", label) == self.args.attach_pid, "manual host PID changed")
        require(self.get(self.app, "Visible", label) == self.report["visibility_before"], "manual host visibility changed")
        require(self.get(self.app, "UserControl", label) is True, "manual host UserControl changed; no visibility/lifetime correction is permitted")
        self.identity_catalog([row["document"] for row in self.originals + self.live], label)
        for row in self.originals:
            require(self.describe(row["document"], label + "." + row["identity"]) == row["snapshot"], "preexisting document title/path/state changed")
            self.call(label + ".original-edit-context", lambda row=row: self.verify_context(self.app, row["document"], row["context"]))
        require(self.templates(label + ".global-templates") == self.report["global_templates_before"], "global template paths changed")
        if foreground:
            require(self.same(self.get(self.app, "ActiveDoc", label), self.original_foreground), "original foreground not restored")

    def attach_rot(self):
        """Bind exactly one PID moniker, without activating or probing other objects.

        SolidPractices recommends ROT/PID lookup for separate SW instances:
        https://3dswym.3dexperience.3ds.com/wiki/solidworks-news-info/getting-started-with-the-solidworks-api-solidpractices_eLpSxUm2THqG6jwQdSrMGQ
        The exact moniker spelling is independently checked by the native preflight.
        """
        expected = "SolidWorks_PID_" + str(self.args.attach_pid)
        evidence = self.report["rot_binding"] = {
            "expected_moniker": expected, "observed_monikers": [],
            "matching_moniker_count": 0, "binding_attempted": False,
            "identity_verified": False,
        }
        self.report_changed()
        self.persist()
        rot = self.call("ROT.GetRunningObjectTable", self.pythoncom.GetRunningObjectTable)
        context = self.call("ROT.CreateBindCtx", lambda: self.pythoncom.CreateBindCtx(0))
        enumerator = self.call("ROT.EnumRunning", rot.EnumRunning)
        matches = []
        # A finite enumeration must complete before any object may be bound.
        for index in range(4096):
            batch = self.call("ROT.Next." + str(index), lambda: enumerator.Next(1))
            require(type(batch) in (tuple, list) and len(batch) <= 1, "invalid ROT enumeration result")
            if not batch:
                break
            moniker = batch[0]
            name = self.call("ROT.GetDisplayName." + str(index), lambda: moniker.GetDisplayName(context, None))
            require(type(name) is str, "ROT moniker display name is not a string")
            evidence["observed_monikers"].append(name)
            self.report_changed()
            if name == expected:
                matches.append(moniker)
                self.report_changed()
                evidence["matching_moniker_count"] = len(matches)
                self.report_changed()
            self.persist()
        else:
            raise RuntimeError("ROT enumeration exceeded finite limit; no object bound")
        require(len(matches) == 1, "ROT exact PID moniker must match exactly once; no object bound")
        evidence["binding_attempted"] = True
        self.report_changed()
        self.persist()
        unknown = self.call("ROT.GetObject.once", lambda: rot.GetObject(matches[0]))
        dispatch = self.call("ROT.QueryInterface.IDispatch", lambda: unknown.QueryInterface(self.pythoncom.IID_IDispatch))
        app = self.call("ROT.Dispatch.existing", lambda: self.client.Dispatch(dispatch))
        pid = self.get(app, "GetProcessID", "attach-readonly")
        self.report["actual_attach_pid"] = pid
        self.report_changed()
        self.persist()
        require(type(pid) is int and pid == self.args.attach_pid, "ROT host PID mismatch; stop without mutation")
        evidence["identity_verified"] = True
        self.report_changed()
        self.persist()
        return app

    def attach_owned_interface(self):
        # This packet is injected only after the hardened worker grant and is
        # received over its private stdin. Never persist/log the COM capability.
        packet, self._owned_interface_data = self._owned_interface_data, None
        require(type(packet) is bytes and 0 < len(packet) <= 65536, "owned interface packet missing")
        self.report["owned_interface_binding"] = {"source": "parent-owned-COM-marshal",
            "unmarshal_attempted": False, "identity_verified": False}
        self.report_changed()
        self.persist()
        stream = self.pythoncom.CreateStreamOnHGlobal()
        stream.Write(packet)
        packet = None
        stream.Seek(0, 0)
        evidence = self.report["owned_interface_binding"]
        evidence["unmarshal_attempted"] = True
        self.report_changed()
        self.persist()
        dispatch = self.call("owned-interface.CoUnmarshalInterface.once",
                             lambda: self.pythoncom.CoUnmarshalInterface(stream, self.pythoncom.IID_IDispatch))
        app = self.call("owned-interface.Dispatch.existing", lambda: self.client.Dispatch(dispatch))
        pid = self.get(app, "GetProcessID", "owned-interface-readonly")
        self.report["actual_attach_pid"] = pid
        self.report_changed()
        self.persist()
        require(type(pid) is int and pid == self.args.attach_pid, "owned interface host PID mismatch; stop without mutation")
        evidence["identity_verified"] = True
        self.report_changed()
        self.persist()
        return app

    def attach(self):
        self.report["existing_process_ids"] = self.call("snapshot-processes-before", process_ids)
        self.report_changed()
        require(self.args.attach_pid in self.report["existing_process_ids"], "specified manual SW PID is not running")
        self.app = (self.attach_owned_interface() if getattr(self.args, "owned_interface_stdin", False)
                    else self.attach_rot())
        self.export_constants()
        self.report["revision"] = self.get(self.app, "RevisionNumber", "attach-readonly")
        self.report_changed()
        visible = self.get(self.app, "Visible", "attach-readonly")
        require(type(visible) is bool, "manual host visibility is not boolean")
        self.report["visibility_before"] = visible
        self.report_changed()
        self.report["user_control_before"] = self.get(self.app, "UserControl", "attach-readonly")
        self.report_changed()
        require(self.report["user_control_before"] is True, "manual host must already have UserControl=True; do not mutate it")
        self.original_foreground = self.get(self.app, "ActiveDoc", "attach-readonly")
        for index, document in enumerate(self.documents("original-catalog")):
            self.originals.append({"identity": "original-" + str(index + 1), "document": document,
                "snapshot": self.describe(document, "original-" + str(index + 1)),
                "context": self.call("original-edit-context", lambda document=document: self.edit_context(document))})
            self.report_changed()
        require(self.original_foreground is None or any(self.same(self.original_foreground, row["document"]) for row in self.originals), "foreground absent from original catalog")
        self.report["original_documents"] = [{"identity": row["identity"], **row["snapshot"]} for row in self.originals]
        self.report_changed()
        self.report["original_foreground"] = next((row["identity"] for row in self.originals if self.same(row["document"], self.original_foreground)), None)
        self.report_changed()
        self.report["global_templates_before"] = self.templates("global-templates-before")
        self.report_changed()
        self.report["template_path_availability"] = {}
        self.report_changed()
        for symbol, value in self.report["global_templates_before"].items():
            available = bool(value and Path(value).is_file())
            self.report["template_path_availability"][symbol] = available
            self.report_changed()
            if available:
                self.source_file(value, "global-template-" + symbol)
        for row in self.originals:
            path = row["snapshot"]["path"]
            if path and Path(path).is_file():
                self.source_file(path, "preexisting-" + row["identity"])
        self.original_invariants("attach-baseline", foreground=True)
        self.trusted = True
        self.persist()

    def register(self, document, label):
        require(document is not None and not any(self.same(document, row["document"]) for row in self.originals + self.live), "new/open returned existing/null document")
        row = {"identity": label, "document": document, "title": None, "close_attempted": False}
        # Retain the newly returned native handle even if metadata observation fails.
        self.live.append(row)
        self.report_changed()
        title = self.get(document, "GetTitle", label)
        require(type(title) is str and bool(title.strip()), "new test document title is empty/unreadable")
        row["title"] = title
        self.report_changed()
        self.identity_catalog([item["document"] for item in self.originals + self.live], "register-" + label)
        return document

    def save_new(self, document, label, kind):
        path = self.output / (self.prefix + "-" + label + "." + SUFFIX[kind])
        require(not path.exists(), "refuse reused native filename")
        result = self.call(label + ".save-as-native", lambda: self.save_native(str(path), document=document))
        self.report.setdefault("save_attempts", []).append({"label": label, "path": str(path), "native_result": result})
        self.report_changed()
        self.persist()
        row = next(item for item in self.live if self.same(document, item["document"]))
        title = self.get(document, "GetTitle", label + ".post-save")
        require(type(title) is str and bool(title.strip()) and title.startswith(self.prefix),
                "saved test title is empty or not uniquely prefixed")
        row["title"] = title
        self.report_changed()
        require(result.get("ok") is True and result.get("api_saved") is True
                and type(result.get("save_errors")) is int and result["save_errors"] == 0,
                "native save failed: " + repr(result))
        require(self.get(document, "GetSaveFlag", label) is False and path.is_file() and path.stat().st_size >= 512, "saved test file is missing/dirty/too small")
        require(Path(self.get(document, "GetPathName", label)).resolve() == path, "saved document path mismatch")
        artifact = result.get("artifact", {})
        require(type(artifact.get("size_bytes")) is int and artifact["size_bytes"] == path.stat().st_size,
                "native save artifact byte count differs from actual file size")
        # Retain save_warnings exactly as returned. SaveAs3 has no warning out
        # parameter, so the installed adapter's None must never be replaced by 0.
        row["path"] = str(path)
        self.report_changed()
        evidence = {"sha256": digest(path), "size": path.stat().st_size}
        self.report["file_hashes"][str(path)] = evidence
        self.report_changed()
        self.persist()
        return {"path": str(path), "save": result, **evidence}

    def create(self, kind, label):
        if kind == "drawing":
            require(Path(self.args.drawing_template).is_file(), "explicit drawing template missing")
            template = self.args.drawing_template
            self.source_file(template, label + "-actual-drawing-template")
            creator = lambda: self.create_drawing(app=self.app, template=template, projection="first-angle")
        else:
            method = self.create_part if kind == "part" else self.create_assembly
            explicit = getattr(self.args, kind + "_template", None)
            resolution = self.call(label + ".resolve-actual-template-readonly", lambda: self.resolve_template(self.app, explicit, kind=kind))
            require(resolution.get("ok") is True, "explicit actual template resolution failed")
            template = resolution["path"]
            self.source_file(template, label + "-actual-" + kind + "-template")
            creator = lambda: method(app=self.app, template=template)
        result, document = self.call(label + ".create-" + kind, creator)
        if document is not None:
            self.register(document, label)
        require(result.get("ok") is True and document is not None, "test creation failed: " + repr(result))
        if kind == "part" and label.endswith("-target") and self.args.stage in ("fonts", "display", "standards"):
            profile, sketch = self.call(label + ".rectangle", lambda: self.rectangle(app=self.app, document=document, plane="front", width_mm=40, height_mm=30))
            require(profile.get("ok") is True and sketch is not None, "test rectangle failed")
            boss, feature = self.call(label + ".extrude", lambda: self.extrude(app=self.app, document=document, sketch_feature=sketch, depth_mm=10, reverse=False))
            require(boss.get("ok") is True and feature is not None, "test extrusion failed")
            self.report["cases"][-1]["geometry_initial"] = self.geometry(document, label + ".geometry-before")
            self.report_changed()
            self.persist()
        baseline = self.save_new(document, label + "-baseline", kind)
        self.report.setdefault("created_documents", []).append({"identity": label, "kind": kind, "creation": result, "baseline": baseline})
        self.report_changed()
        self.original_invariants(label + ".after-create")
        return document, baseline

    def close(self, document, label):
        row = next((item for item in self.live if item["document"] is document), None)
        require(row is not None and not row["close_attempted"], "refuse unregistered/repeated document close")
        require(self.get(self.app, "GetProcessID", label + ".close-preflight") == self.args.attach_pid,
                "host PID mismatch before registered close")
        require(self.get(self.app, "UserControl", label + ".close-preflight") is True,
                "refuse CloseDoc without user-controlled host lifetime")
        actual = self.identity_catalog([item["document"] for item in self.originals + self.live], label + ".catalog")
        require(not any(self.same(document, item["document"]) for item in self.originals), "refuse closing preexisting document")
        title = self.get(document, "GetTitle", label)
        require(type(title) is str and bool(title.strip()) and title == row["title"],
                "registered test title is empty/unreadable/changed; never CloseDoc('')")
        require(sum(self.get(item, "GetTitle", label + ".collision-check") == title for item in actual) == 1, "CloseDoc title ambiguous")
        row["close_attempted"] = True
        self.report_changed()
        self.persist()
        require(self.get(self.app, "GetProcessID", label + ".immediate-close-check") == self.args.attach_pid,
                "host PID mismatch immediately before registered close")
        self.call(label + ".CloseDoc.registered-test-only", lambda: self.app.CloseDoc(title))
        remaining = [item["document"] for item in self.originals + self.live if item is not row]
        self.identity_catalog(remaining, label + ".after-close")
        path = row.get("path")
        if path in self.report["file_hashes"]:
            before = self.report["file_hashes"][path]
            actual_size, actual_sha256 = Path(path).stat().st_size, digest(path)
            self.report.setdefault("closed_file_hash_checks", []).append(
                {"identity": row["identity"], "path": path, "sha256": actual_sha256, "size": actual_size})
            self.report_changed()
            self.persist()
            require(actual_sha256 == before["sha256"] and actual_size == before["size"],
                    "test file changed while closing reopened/native document")
        self.live.remove(row)
        self.report_changed()

    def activate(self, document, label):
        name = self.get(document, "GetPathName", label) or self.get(document, "GetTitle", label)
        error = self.client.VARIANT(self.pythoncom.VT_BYREF | self.pythoncom.VT_I4, 0)
        result = self.call(label + ".ActivateDoc3.no-rebuild", lambda: self.app.ActivateDoc3(name, False, self.constants["swDontRebuildActiveDoc"], error))
        require(error.value == 0 and result is not None and self.same(result, document), "explicit foreground activation failed")
        require(self.same(self.get(self.app, "ActiveDoc", label), document), "foreground activation readback differs")

    def restore(self, label):
        try:
            require(not self.live, "test documents remain open")
            self.original_invariants(label + ".before-restore")
            if self.original_foreground is not None:
                self.activate(self.original_foreground, label + ".restore-original-foreground")
            else:
                require(self.get(self.app, "ActiveDoc", label) is None, "empty original host has remaining foreground")
            self.original_invariants(label + ".restored", foreground=True)
        except BaseException:
            self.restore_failed = True
            raise

    def read_font(self, document, label):
        extension = self.get(document, "Extension", label)
        font = self.call(label + ".GetUserPreferenceTextFormat", lambda: extension.GetUserPreferenceTextFormat(self.constants["swDetailingAnnotationTextFormat"], self.constants["swDetailingNoOptionSpecified"]))
        require(font is not None, "annotation font object is null")
        result = self.report["reads"].setdefault(label, {})
        self.report_changed()
        for member in FONT_MEMBERS:
            value = self.get(font, member, label + ".ITextFormat")
            result[member] = value
            self.report_changed()
            valid = type(value) is bool if member in FONT_BOOL else type(value) is str if member == "TypeFaceName" else type(value) is int if member == "CharHeightInPts" else type(value) in (int, float) and math.isfinite(value)
            require(valid, "unreadable native font member: " + member)
        require(result["CharHeight"] > 0 and result["CharHeightInPts"] >= 0, "invalid native font height")
        self.persist()
        return font, dict(result)

    def read_scalars(self, document, kind, label):
        extension = self.get(document, "Extension", label)
        c = self.constants
        result = self.report["reads"].setdefault(label, {"display": {}, "annotations": {}, "support": {}})
        self.report_changed()
        for key, (family, preference, scope) in DISPLAY.items():
            if kind == "drawing" and scope == "model":
                result["support"][key] = {"status": "not-applicable", "reason": "Plane Display is model-only; native getter not called"}
                self.report_changed()
                continue
            raw = self.call(label + ".display." + key, lambda family=family, preference=preference: getattr(extension, "GetUserPreference" + family)(c[preference], c["swDetailingNoOptionSpecified"]))
            result["display"][key] = raw
            self.report_changed()
            result["support"][key] = {"status": "getter-returned", "preference": c[preference], "option": c["swDetailingNoOptionSpecified"], "family": family}
            self.report_changed()
            require(type(raw) is (bool if family == "Toggle" else int if family == "Integer" else float) and (family != "Double" or math.isfinite(raw)), "unreadable display scalar: " + key)
        for key, (family, preference, option) in ANNOTATIONS.items():
            raw = self.call(label + ".annotation." + key, lambda family=family, preference=preference, option=option: getattr(extension, "GetUserPreference" + family)(c[preference], c[option]))
            result["annotations"][key] = raw
            self.report_changed()
            require(type(raw) is (bool if family == "Toggle" else int if family == "Integer" else float) and (family != "Double" or math.isfinite(raw)), "unreadable annotation scalar: " + key)
        result["standard"] = self.call(label + ".overall-standard", lambda: extension.GetUserPreferenceInteger(c["swDetailingDimensionStandard"], c["swDetailingNoOptionSpecified"]))
        self.report_changed()
        require(type(result["standard"]) is int, "native overall standard is not integer")
        self.persist()
        return {key: dict(value) if type(value) is dict else value for key, value in result.items()}

    def observe(self, document, kind, foreground, label):
        before = self.call(label + ".state-before", lambda: self.native_state(document))
        context = self.call(label + ".edit-context", lambda: self.edit_context(document))
        _, font = self.read_font(document, label + ".font")
        scalar = self.read_scalars(document, kind, label + ".scalars")
        self.call(label + ".verify-edit-context", lambda: self.verify_context(self.app, document, context))
        require(self.call(label + ".state-after", lambda: self.native_state(document)) == before, "read changed test state")
        require(self.same(self.get(self.app, "ActiveDoc", label), foreground), "read changed foreground")
        self.original_invariants(label + ".original-preservation")
        return {"font": font, **scalar, "state": list(before)}

    def geometry(self, document, label, reference=None):
        result = self.call(label, lambda: self.measure(document=document))
        self.report.setdefault("geometry", {})[label] = result
        self.report_changed()
        self.persist()
        metrics = result.get("metrics", {})
        center = metrics.get("centroid_mm", {})
        require(result.get("ok") is True and metrics.get("solid_body_count") == 1
                and type(metrics.get("volume_mm3")) in (int, float)
                and type(metrics.get("surface_area_mm2")) in (int, float)
                and math.isclose(metrics["volume_mm3"], 12000, rel_tol=0, abs_tol=1e-6)
                and math.isclose(metrics["surface_area_mm2"], 3800, rel_tol=0, abs_tol=1e-6)
                and type(center) is dict and center.keys() == {"x", "y", "z"}
                and all(type(value) in (int, float) and math.isfinite(value) for value in center.values()),
                "test box V/S/centroid is unavailable/changed")
        if reference is not None:
            require(all(math.isclose(metrics[field], reference[field], rel_tol=0, abs_tol=1e-6)
                        for field in ("volume_mm3", "surface_area_mm2"))
                    and all(math.isclose(center[axis], reference["centroid_mm"][axis], rel_tol=0, abs_tol=1e-8)
                            for axis in ("x", "y", "z")),
                    "test box V/S/centroid differs from the initial native geometry")
        return metrics

    def changed_context(self, document, front, state, context, label):
        now = self.call(label + ".state", lambda: self.native_state(document))
        self.report.setdefault("state_observations", {})[label] = list(now)
        self.report_changed()
        self.persist()
        require((now[0], now[3]) == (state[0], state[3]), "write changed test kind/configuration")
        require(self.same(self.get(self.app, "ActiveDoc", label), front), "write changed foreground")
        self.call(label + ".edit-context", lambda: self.verify_context(self.app, document, context))
        self.original_invariants(label + ".original-preservation")
        require(self.call(label + ".state-after-guards", lambda: self.native_state(document)) == now,
                "read guards changed post-mutation state")
        return list(now)

    @staticmethod
    def same_values(before, after):
        return all(before[key] == after[key] for key in ("font", "display", "annotations", "standard"))

    @staticmethod
    def font_requested(font, member, target):
        if member == "CharHeight":
            return font["IsHeightSpecifiedInPts"] is False and math.isclose(font[member], target, rel_tol=1e-12, abs_tol=1e-12)
        if member == "CharHeightInPts":
            return font["IsHeightSpecifiedInPts"] is True and type(font[member]) is int and font[member] == target
        return type(font[member]) is type(target) and font[member] == target

    @staticmethod
    def font_native_normalizations(before, after, member):
        from swcli.document_annotation_fonts import annotation_font_native_normalizations
        return annotation_font_native_normalizations(before, after, member)

    @staticmethod
    def font_unrequested(before, after, member):
        try:
            Calibration.font_native_normalizations(before, after, member)
        except ValueError:
            return False
        return True

    @staticmethod
    def font_probe_effectively_old(before, probe, member):
        if member in HEIGHT_MEMBERS:
            active = "CharHeightInPts" if before["IsHeightSpecifiedInPts"] else "CharHeight"
            return (probe["IsHeightSpecifiedInPts"] is before["IsHeightSpecifiedInPts"]
                    and type(probe[active]) is type(before[active]) and probe[active] == before[active])
        return type(probe[member]) is type(before[member]) and probe[member] == before[member]

    def writable(self, document, label):
        require(self.get(document, "IsOpenedReadOnly", label) is False and self.get(document, "IsOpenedViewOnly", label) is False,
                "test target is read-only/view-only")
        context = self.call(label + ".edit-context", lambda: self.edit_context(document))
        require(self.call(label + ".writable-context", lambda: self.writable_context(self.app, context)), "test edit context is not writable")
        return context

    def mutation_guard(self, document, front, state, context, label):
        """Validate an existing baseline; never adopt a newly observed edit context."""
        observed = {"expected_state": list(state)}
        self.report.setdefault("mutation_guards", {})[label] = observed
        self.report_changed()
        self.persist()
        self.original_invariants(label + ".host-and-originals")
        self.call(label + ".verify-original-edit-context",
                  lambda: self.verify_context(self.app, document, context))
        require(self.call(label + ".original-context-writable",
                          lambda: self.writable_context(self.app, context)),
                "original test edit context is not writable")
        observed["read_only"] = self.get(document, "IsOpenedReadOnly", label)
        self.report_changed()
        observed["view_only"] = self.get(document, "IsOpenedViewOnly", label)
        self.report_changed()
        observed["foreground_matches"] = self.same(self.get(self.app, "ActiveDoc", label), front)
        self.report_changed()
        observed["state"] = list(self.call(label + ".known-state-check", lambda: self.native_state(document)))
        self.report_changed()
        self.persist()
        require(observed["read_only"] is False and observed["view_only"] is False,
                "test target became read-only/view-only before mutation")
        require(observed["foreground_matches"], "known test foreground changed before mutation")
        require(observed["state"] == list(state), "known test state changed during pre-mutation reads")
        # A guard is itself read-only: compare against the same original context
        # and state again, rather than blessing any context drift as a new baseline.
        self.call(label + ".recheck-original-edit-context",
                  lambda: self.verify_context(self.app, document, context))
        observed["final_read_only"] = self.get(document, "IsOpenedReadOnly", label + ".final")
        self.report_changed()
        observed["final_view_only"] = self.get(document, "IsOpenedViewOnly", label + ".final")
        self.report_changed()
        observed["final_pid"] = self.get(self.app, "GetProcessID", label + ".final")
        self.report_changed()
        observed["final_user_control"] = self.get(self.app, "UserControl", label + ".final")
        self.report_changed()
        observed["final_foreground_matches"] = self.same(self.get(self.app, "ActiveDoc", label + ".final"), front)
        self.report_changed()
        observed["final_state"] = list(self.call(label + ".final-known-state-check", lambda: self.native_state(document)))
        self.report_changed()
        self.persist()
        require(observed["final_read_only"] is False and observed["final_view_only"] is False,
                "test target became read-only/view-only in mutation guard")
        require(observed["final_pid"] == self.args.attach_pid and observed["final_user_control"] is True,
                "manual host PID/UserControl changed in mutation guard")
        require(observed["final_foreground_matches"] and observed["final_state"] == list(state),
                "known foreground/state drifted in mutation guard")

    def mark_dirty(self, document, kind, front, expected, label, *, context, post_setter_state):
        # post_setter_state was captured immediately after the actual setter.
        # Reads before this point must not redefine the baseline for this write.
        require(expected["state"] == list(post_setter_state), "post-setter read adopted a drifted state")
        self.mutation_guard(document, front, post_setter_state, context, label + ".before-saveflag")
        if post_setter_state[2] is False:
            self.call(label + ".SetSaveFlag.once", lambda: document.SetSaveFlag())
            post_flag_state = self.changed_context(document, front, post_setter_state, context, label + ".post-saveflag")
            require(post_flag_state[2] is True, "SetSaveFlag did not mark the test target dirty")
        else:
            post_flag_state = list(post_setter_state)
        final = self.observe(document, kind, front, label + ".after-saveflag")
        require(final["state"] == post_flag_state and final["state"][2] is True
                and self.same_values(expected, final), "marking dirty/readback changed test options or state")
        self.mutation_guard(document, front, post_flag_state, context, label + ".after-saveflag-guards")
        return final

    def reopen_test(self, saved, kind, front, label, read_only):
        path = Path(saved["path"])
        require(digest(path) == saved["sha256"], "saved file changed before reopening")
        opened, document = self.call(label + ".OpenDoc6." + ("readonly" if read_only else "writable"),
                                     lambda: self.open_native(str(path), app=self.app, read_only=read_only))
        if document is not None:
            self.register(document, label)
        evidence = {"identity": label, "read_only": read_only, "open": opened}
        self.report.setdefault("reopens", []).append(evidence)
        self.report_changed()
        self.persist()
        require(document is not None and opened.get("ok") is True and opened.get("api_errors") == 0 and opened.get("api_warnings") == 0,
                "test reopen failed: " + repr(opened))
        evidence["native_path"] = self.get(document, "GetPathName", label)
        self.report_changed()
        evidence["native_type"] = self.get(document, "GetType", label)
        self.report_changed()
        evidence["native_read_only"] = self.get(document, "IsOpenedReadOnly", label)
        self.report_changed()
        evidence["native_view_only"] = self.get(document, "IsOpenedViewOnly", label)
        self.report_changed()
        evidence["native_modified"] = self.get(document, "GetSaveFlag", label)
        self.report_changed()
        self.persist()
        require(type(evidence["native_path"]) is str and Path(evidence["native_path"]).resolve() == path,
                "reopened native path differs from the saved test copy")
        require(type(evidence["native_type"]) is int and evidence["native_type"] == {"part": 1, "assembly": 2, "drawing": 3}[kind],
                "reopened native document type differs")
        next(item for item in self.live if item["document"] is document)["path"] = evidence["native_path"]
        self.report_changed()
        require(evidence["native_read_only"] is read_only, "reopened access mode differs")
        require(evidence["native_view_only"] is False and evidence["native_modified"] is False,
                "test reopened view-only or already modified")
        # OpenDoc6 may change foreground; explicitly select our own front part.
        self.activate(front, label + ".restore-test-foreground")
        return document

    def roundtrip(self, document, kind, front, expected, row, label, continue_writable, *, context=None):
        if context is not None:
            self.mutation_guard(document, front, expected["state"], context, label + ".before-save-as")
        row["saved"] = self.save_new(document, label + "-changed", kind)
        self.report_changed()
        saved_observation = self.observe(document, kind, front, label + ".after-save")
        row["saved_observation"] = saved_observation
        self.report_changed()
        require(self.same_values(expected, saved_observation), "save changed test settings")
        if kind == "part":
            reference = self.report["cases"][-1].get("geometry_initial")
            require(reference is not None, "part geometry initial native baseline is missing")
            row["saved_geometry"] = self.geometry(document, label + ".geometry-before-close", reference=reference)
            self.report_changed()
        self.close(document, label + ".close-written")
        reopened = self.reopen_test(row["saved"], kind, front, label + "-readonly", True)
        observed = self.observe(reopened, kind, front, label + ".readonly-readback")
        row["readonly_observation"] = observed
        self.report_changed()
        require(self.same_values(expected, observed) and observed["state"][2] is False, "changed test values did not persist cleanly")
        if kind == "part":
            row["reopened_geometry"] = self.geometry(reopened, label + ".geometry-reopened", reference=reference)
            self.report_changed()
        require(digest(Path(row["saved"]["path"])) == row["saved"]["sha256"], "readonly observation changed saved file bytes")
        row["fresh_handle_note"] = "closed test and opened new native handle; no public daemon document ID is claimed"
        self.report_changed()
        self.persist()
        if not continue_writable:
            return reopened
        self.close(reopened, label + ".close-readonly")
        writable = self.reopen_test(row["saved"], kind, front, label + "-writable", False)
        reopened_values = self.observe(writable, kind, front, label + ".writable-readback")
        require(self.same_values(expected, reopened_values) and reopened_values["state"][2] is False,
                "continuation reopen changed persisted settings")
        return writable

    def font_stage(self, document, kind, front, case):
        members = ("TypeFaceName", "CharHeight", "CharHeightInPts", "Bold", "Italic", "Underline", "Strikeout")
        for index, member in enumerate(members):
            label = kind + ".font-write-" + str(index + 1) + "-" + member
            initial_state = list(self.call(label + ".state-before-any-reads", lambda: self.native_state(document)))
            context = self.writable(document, label)
            before = self.observe(document, kind, front, label + ".before")
            format_object, native_before = self.read_font(document, label + ".object-before")
            require(native_before == before["font"], "font changed between snapshot and target object read")
            if member == "TypeFaceName":
                target = self.args.font_typeface if native_before[member] != self.args.font_typeface else "Times New Roman"
                require(type(target) is str and target.strip() == target and bool(target), "invalid requested typeface")
            elif member == "CharHeight":
                target = 0.004 if not math.isclose(native_before[member], 0.004, rel_tol=1e-12, abs_tol=1e-12) else 0.005
            elif member == "CharHeightInPts":
                target = 14 if native_before[member] != 14 else 16
            else:
                target = not native_before[member]
            require(not self.font_requested(native_before, member, target), "font target is not an actual change")
            row = {"member": member, "target_native": target, "before": before,
                   "mutation": {"attempted": False, "may_have_changed": False},
                   "property_set_calls": 0, "final_set_calls": 0}
            case["writes"].append(row)
            self.report_changed()
            self.persist()
            require(before["state"] == initial_state, "font pre-read changed initial test state")
            self.mutation_guard(document, front, initial_state, context, label + ".before-property")
            row["mutation"] = {"attempted": True, "may_have_changed": True}
            self.report_changed()
            row["property_set_calls"] = 1
            self.report_changed()
            self.persist()
            self.call(label + ".ITextFormat." + member + ".set.once", lambda: setattr(format_object, member, target))
            row["state_after_property"] = self.changed_context(document, front, before["state"], context, label + ".post-property")
            self.report_changed()
            # This is a second, independent Get, before the document's final Set.
            probe = self.observe(document, kind, front, label + ".independent-get-before-final-set")
            row["property_probe"] = probe
            self.report_changed()
            require(all(probe[key] == before[key] for key in ("display", "annotations", "standard")), "font property assignment changed scalar controls")
            row["property_probe_native_normalizations"] = self.font_native_normalizations(native_before, probe["font"], member)
            self.report_changed()
            if self.font_requested(probe["font"], member, target):
                row["live_property_result"] = "requested-value-visible-before-final-set"
                self.report_changed()
            else:
                require(self.font_probe_effectively_old(native_before, probe["font"], member),
                        "unexpected effective font mutation before final Set")
                row["live_property_result"] = "not-visible-in-independent-get"
                self.report_changed()
            self.persist()
            extension = self.get(document, "Extension", label)
            require(probe["state"] == row["state_after_property"], "independent font Get adopted a drifted state")
            self.mutation_guard(document, front, row["state_after_property"], context, label + ".before-final-set")
            row["final_set_calls"] = 1
            self.report_changed()
            self.persist()
            row["native_return"] = self.call(label + ".SetUserPreferenceTextFormat.once", lambda:
                extension.SetUserPreferenceTextFormat(self.constants["swDetailingAnnotationTextFormat"],
                                                     self.constants["swDetailingNoOptionSpecified"], format_object))
            self.report_changed()
            self.persist()
            require(row["native_return"] is True, "font final Set did not return strict True")
            row["state_after_final_set"] = self.changed_context(document, front, before["state"], context, label + ".post-final-set")
            self.report_changed()
            after = self.observe(document, kind, front, label + ".after")
            row["after"] = after
            self.report_changed()
            require(self.font_requested(after["font"], member, target), "font requested value/mode did not read back")
            row["native_normalizations"] = self.font_native_normalizations(native_before, after["font"], member)
            self.report_changed()
            self.persist()
            require(all(after[key] == before[key] for key in ("display", "annotations", "standard")), "font Set changed scalar controls")
            final = self.mark_dirty(document, kind, front, after, label,
                                    context=context, post_setter_state=row["state_after_final_set"])
            # Persist each height mode before the next field can supersede it.
            document = self.roundtrip(document, kind, front, final, row, label,
                                      index + 1 < len(members), context=context)
            row["success"] = True
            self.report_changed()
            self.persist()
        case["all_seven_changed_values_persisted_individually"] = True
        self.report_changed()
        return document

    def display_stage(self, document, kind, front, case):
        current = case["initial"]
        for index, (key, (family, preference, scope)) in enumerate(DISPLAY.items()):
            if key not in current["display"]:
                continue
            label = kind + ".display-write-" + str(index + 1) + "-" + key
            initial_state = list(self.call(label + ".state-before-any-reads", lambda: self.native_state(document)))
            context = self.writable(document, label)
            before = self.observe(document, kind, front, label + ".before")
            value = before["display"][key]
            if family == "Toggle":
                target = not value
            elif key == "grid.major_spacing_mm":
                target = 0.010 if value != 0.010 else 0.020
            elif key == "grid.minor_lines_per_major":
                target = 10 if value != 10 else 5
            elif key == "grid.snap_points_per_minor":
                target = 5 if value != 5 else 4
            elif key == "virtual_sharp.style":
                target = next(candidate for candidate in self.virtual_values if candidate != value)
            elif key == "plane.transparency":
                target = 25 if value != 25 else 50
            else:
                # Raw native RGB integers; this diagnosis does not assert color rendering.
                target = 0x123456 if value != 0x123456 else 0x654321
            require(type(target) is type(value) and target != value, "display target is not a typed change")
            row = {"field": key, "family": family, "preference_symbol": preference,
                   "preference": self.constants[preference], "option": self.constants["swDetailingNoOptionSpecified"],
                   "target_native": target, "before": before, "native_setter_calls": 0,
                   "mutation": {"attempted": False, "may_have_changed": False}}
            case["writes"].append(row)
            self.report_changed()
            self.persist()
            extension = self.get(document, "Extension", label)
            require(before["state"] == initial_state, "display pre-read changed initial test state")
            self.mutation_guard(document, front, initial_state, context, label + ".before-scalar-set")
            row["mutation"] = {"attempted": True, "may_have_changed": True}
            self.report_changed()
            row["native_setter_calls"] = 1
            self.report_changed()
            self.persist()
            row["native_return"] = self.call(label + ".SetUserPreference" + family + ".once", lambda:
                getattr(extension, "SetUserPreference" + family)(self.constants[preference],
                    self.constants["swDetailingNoOptionSpecified"], target))
            self.report_changed()
            self.persist()
            require(type(row["native_return"]) is bool, "display setter return is not boolean")
            row["state_after_setter"] = self.changed_context(document, front, before["state"], context, label + ".post-setter")
            self.report_changed()
            after = self.observe(document, kind, front, label + ".after")
            row["after"] = after
            self.report_changed()
            require(after["display"] == {**before["display"], key: target}, "display setter changed requested/unrelated scalar")
            require(all(after[group] == before[group] for group in ("font", "annotations", "standard")), "display setter changed font/annotation/standard")
            # Keep native False as failure evidence even if getter shows a mutation.
            require(row["native_return"] is True, "display setter returned False; no retry/rollback")
            current = self.mark_dirty(document, kind, front, after, label,
                                      context=context, post_setter_state=row["state_after_setter"])
            row["success"] = True
            self.report_changed()
            self.persist()
        require(all(current["display"][key] != case["initial"]["display"][key] for key in current["display"]),
                "not every applicable display value is changed at persistence boundary")
        roundtrip = {}
        case["changed_values_roundtrip"] = roundtrip
        self.report_changed()
        return self.roundtrip(document, kind, front, current, roundtrip, kind + ".display-final", False, context=context)

    @staticmethod
    def standard_key(snapshot):
        # _read_snapshot validates the fixed shape/types. This comparison also
        # distinguishes booleans from numeric prevalues instead of Python ==.
        return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))

    @staticmethod
    def standard_diff(before, after):
        changes = []
        def visit(first, second, path):
            if type(first) is dict and type(second) is dict:
                for key in sorted(first.keys() | second.keys()):
                    child = path + "/" + key.replace("~", "~0").replace("/", "~1")
                    if key not in first:
                        changes.append({"path": child, "before_missing": True, "after": second[key]})
                    elif key not in second:
                        changes.append({"path": child, "before": first[key], "after_missing": True})
                    else:
                        visit(first[key], second[key], child)
            elif type(first) is list and type(second) is list and len(first) == len(second):
                for index, (left, right) in enumerate(zip(first, second)):
                    visit(left, right, path + "/" + str(index))
            elif type(first) is not type(second) or first != second:
                changes.append({"path": path or "/", "before": first, "after": second,
                                "before_type": type(first).__name__, "after_type": type(second).__name__})
        visit(before, after, "")
        return changes

    def standard_catalog(self):
        # This asserts the fixed product reader agrees with *this installation's*
        # freshly exported TLB; no SDK catalog/transition whitelist is patched.
        from swcli.document_annotation_fonts import ANNOTATION_FONT_PREFERENCE
        from swcli.document_display_options import DISPLAY_FIELDS, resolve_display_preference_ids
        from swcli.document_drafting_standard import (
            BASE_STANDARD_OPTIONS, DRAFTING_DEFAULTS_PROFILE, DRAFTING_STANDARD_OPTION,
            DRAFTING_STANDARD_PREFERENCE, DRAFTING_STANDARDS, CALIBRATED_DRAFTING_TRANSITIONS,
        )
        c = self.constants
        require(DRAFTING_DEFAULTS_PROFILE == "drafting-defaults-v1", "unexpected fixed standard observation profile")
        require(DRAFTING_STANDARD_PREFERENCE == c["swDetailingDimensionStandard"]
                and DRAFTING_STANDARD_OPTION == c["swDetailingNoOptionSpecified"]
                and ANNOTATION_FONT_PREFERENCE == {"preference": c["swDetailingAnnotationTextFormat"],
                                                  "option": c["swDetailingNoOptionSpecified"]},
                "fixed reader overall/font preference differs from installed TLB")
        ids = resolve_display_preference_ids()
        require(all(ids[spec["symbol"]] == c[spec["symbol"]]
                    and spec["option"] == c["swDetailingNoOptionSpecified"] for spec in DISPLAY_FIELDS.values()),
                "fixed reader display IDs differ from installed TLB")
        require(all(spec["option"] == c[spec["symbol"]] for spec in BASE_STANDARD_OPTIONS.values()),
                "fixed reader base-standard options differ from installed TLB")
        names = ("ansi", "iso", "din", "jis", "bsi", "gost", "gb", "custom")
        require(all(DRAFTING_STANDARDS[name] == c[symbol] for name, symbol in zip(names, STANDARD_SYMBOLS)),
                "fixed reader named standards differ from installed TLB")
        # The plan is finite and deliberate, not a retry/restoration mechanism.
        self.standard_plan = []
        gb = c["swDetailingStandardGB"]
        require(gb == 7, "this private GB-template plan requires the exported GB code 7")
        for name, symbol in zip(names[:6], STANDARD_SYMBOLS[:6]):
            target = c[symbol]
            self.standard_plan.extend([
                {"source": gb, "target": target, "source_name": "gb", "target_name": name},
                {"source": target, "target": gb, "source_name": name, "target_name": "gb"},
            ])
            self.report_changed()
        self.report["standards_write_status"] = "private finite GB-to-named-and-back diagnosis; no public whitelist/capability is modified"
        self.report_changed()
        self.report["standards_profile"] = DRAFTING_DEFAULTS_PROFILE
        self.report_changed()
        self.report["standards_plan_per_document"] = self.standard_plan
        self.report_changed()
        self.report["public_transition_whitelist_observed"] = list(CALIBRATED_DRAFTING_TRANSITIONS)
        self.report_changed()
        self.report["standards_plan_is_not_failure_rollback"] = True
        self.report_changed()
        self.source_file(Path(self.standard_reader.__code__.co_filename), "fixed-standard-reader-source")
        self.persist()

    def standard_observe(self, document, kind, front, state, context, label):
        record = {"known_state": list(state)}
        self.report.setdefault("standard_reads", {})[label] = record
        self.report_changed()
        self.persist()
        require(list(self.call(label + ".state-before-read", lambda: self.native_state(document))) == list(state),
                "known state changed before fixed standard read")
        self.call(label + ".original-context-before-read", lambda: self.verify_context(self.app, document, context))
        require(self.same(self.get(self.app, "ActiveDoc", label), front), "foreground changed before fixed standard read")
        def read():
            # SDK helpers emit individually flushed, flat native-call boundaries
            # to stderr, correlated with this private diagnostic request.
            with self.standard_trace(self.prefix + "-" + label, "diagnostic.document-drafting-standard-snapshot"):
                return self.standard_reader(document, {"part": 1, "assembly": 2, "drawing": 3}[kind])
        snapshot = self.call(label + ".fixed-observed-defaults-reader", read)
        record["snapshot"] = snapshot
        self.report_changed()
        self.persist()
        require(snapshot["observed_defaults"]["profile"] == "drafting-defaults-v1"
                and type(snapshot["observed_defaults"]["document_type"]) is int
                and snapshot["observed_defaults"]["document_type"] == state[0],
                "fixed standard profile/document type changed")
        self.call(label + ".original-context-after-read", lambda: self.verify_context(self.app, document, context))
        record["state_after"] = list(self.call(label + ".state-after-read", lambda: self.native_state(document)))
        self.report_changed()
        record["foreground_matches"] = self.same(self.get(self.app, "ActiveDoc", label), front)
        self.report_changed()
        self.persist()
        require(record["state_after"] == list(state) and record["foreground_matches"],
                "fixed standard read changed state/foreground")
        self.original_invariants(label + ".original-preservation")
        require(list(self.call(label + ".state-after-invariants", lambda: self.native_state(document))) == list(state),
                "standard read guards changed the known state")
        return snapshot

    def standard_mark_dirty(self, document, kind, front, after, state, context, label):
        self.mutation_guard(document, front, state, context, label + ".before-saveflag")
        if state[2] is False:
            self.call(label + ".SetSaveFlag.once", lambda: document.SetSaveFlag())
            final_state = self.changed_context(document, front, state, context, label + ".post-saveflag")
            require(final_state[2] is True, "standard change did not become dirty")
        else:
            final_state = list(state)
        final = self.standard_observe(document, kind, front, final_state, context, label + ".final")
        require(self.standard_key(final) == self.standard_key(after), "marking dirty changed fixed standard defaults")
        self.mutation_guard(document, front, final_state, context, label + ".final-guards")
        return final, final_state

    def standard_roundtrip(self, document, kind, front, expected, state, context, row, label, continue_writable):
        self.mutation_guard(document, front, state, context, label + ".before-save-as")
        row["saved"] = self.save_new(document, label + "-changed", kind)
        self.report_changed()
        saved_state = self.changed_context(document, front, state, context, label + ".post-save")
        require(saved_state[2] is False, "saved standard test copy remains dirty")
        row["saved_profile"] = self.standard_observe(document, kind, front, saved_state, context, label + ".saved-profile")
        self.report_changed()
        require(self.standard_key(row["saved_profile"]) == self.standard_key(expected), "save changed fixed standard defaults")
        reference = None
        if kind == "part":
            reference = self.report["cases"][-1].get("geometry_initial")
            require(reference is not None, "initial part geometry is missing")
            row["saved_geometry"] = self.geometry(document, label + ".geometry-before-close", reference=reference)
            self.report_changed()
        self.close(document, label + ".close-written")
        reopened = self.reopen_test(row["saved"], kind, front, label + "-readonly", True)
        reopened_state = list(self.call(label + ".readonly-state", lambda: self.native_state(reopened)))
        reopened_context = self.call(label + ".readonly-context", lambda: self.edit_context(reopened))
        row["readonly_profile"] = self.standard_observe(reopened, kind, front, reopened_state, reopened_context,
                                                       label + ".readonly-profile")
        self.report_changed()
        require(reopened_state[2] is False and self.standard_key(row["readonly_profile"]) == self.standard_key(expected),
                "fixed standard profile did not persist in clean readonly copy")
        if kind == "part":
            row["reopened_geometry"] = self.geometry(reopened, label + ".geometry-reopened", reference=reference)
            self.report_changed()
        require(digest(Path(row["saved"]["path"])) == row["saved"]["sha256"], "readonly standard observation changed saved bytes")
        row["fresh_handle_note"] = "native close/open diagnosis; no public daemon document ID is claimed"
        self.report_changed()
        self.persist()
        if not continue_writable:
            return reopened
        self.close(reopened, label + ".close-readonly")
        writable = self.reopen_test(row["saved"], kind, front, label + "-writable", False)
        writable_state = list(self.call(label + ".writable-state", lambda: self.native_state(writable)))
        writable_context = self.call(label + ".writable-context", lambda: self.edit_context(writable))
        row["continuation_profile"] = self.standard_observe(writable, kind, front, writable_state, writable_context,
                                                           label + ".continuation-profile")
        self.report_changed()
        require(writable_state[2] is False and self.standard_key(row["continuation_profile"]) == self.standard_key(expected),
                "writable continuation changed fixed standard profile")
        return writable

    def standards_stage(self, document, kind, front, case):
        state = list(self.call(kind + ".standards.initial-state-before-reads", lambda: self.native_state(document)))
        context = self.writable(document, kind + ".standards.initial")
        current = self.standard_observe(document, kind, front, state, context, kind + ".standards.initial")
        case["standard_initial"] = current
        self.report_changed()
        self.persist()
        require(type(case["initial"]["standard"]) is int
                and case["initial"]["standard"] == self.constants["swDetailingStandardGB"]
                and current["standard"]["native_value"] == self.constants["swDetailingStandardGB"]
                and current["standard"]["value"] == "gb", "standard plan requires an unchanged GB7 template baseline")
        for index, transition in enumerate(self.standard_plan):
            label = kind + ".standard-" + str(index + 1) + "-" + transition["source_name"] + "-to-" + transition["target_name"]
            row = {**transition, "plan_index": index + 1, "native_setter_calls": 0,
                   "mutation": {"attempted": False, "may_have_changed": False}}
            case["writes"].append(row)
            self.report_changed()
            self.persist()
            state = list(self.call(label + ".state-before-any-reads", lambda: self.native_state(document)))
            context = self.writable(document, label)
            before = self.standard_observe(document, kind, front, state, context, label + ".before")
            row["before"], row["state_before"] = before, state
            self.report_changed()
            require(self.standard_key(before) == self.standard_key(current), "fixed defaults changed between planned transitions")
            require(before["standard"]["native_value"] == transition["source"]
                    and transition["source"] != transition["target"], "planned standard source/target differs")
            extension = self.get(document, "Extension", label)
            self.mutation_guard(document, front, state, context, label + ".before-standard-set")
            row["mutation"] = {"attempted": True, "may_have_changed": True}
            self.report_changed()
            row["native_setter_calls"] = 1
            self.report_changed()
            self.persist()
            def set_once():
                with self.standard_trace(self.prefix + "-" + label, "diagnostic.document-drafting-standard-set"):
                    return self.standard_native_call("document-drafting-standard-calibration",
                        "IModelDocExtension.SetUserPreferenceInteger",
                        lambda: extension.SetUserPreferenceInteger(self.constants["swDetailingDimensionStandard"],
                            self.constants["swDetailingNoOptionSpecified"], transition["target"]))
            row["native_return"] = self.call(label + ".SetUserPreferenceInteger.once", set_once)
            self.report_changed()
            self.persist()
            require(row["native_return"] is True, "standard setter returned False/non-bool; no retry or rollback")
            post_state = self.changed_context(document, front, state, context, label + ".post-setter")
            row["state_after_setter"] = post_state
            self.report_changed()
            after = self.standard_observe(document, kind, front, post_state, context, label + ".after")
            row["after"] = after
            self.report_changed()
            require(after["standard"]["native_value"] == transition["target"], "requested overall standard did not read back")
            require(self.standard_key(after["observed_defaults"]["coverage"]) == self.standard_key(before["observed_defaults"]["coverage"]),
                    "fixed standard coverage manifest changed during a transition")
            row["before_after_diff"] = self.standard_diff(before, after)
            self.report_changed()
            row["observed_defaults_diff"] = self.standard_diff(before["observed_defaults"], after["observed_defaults"])
            self.report_changed()
            final, final_state = self.standard_mark_dirty(document, kind, front, after, post_state, context, label)
            row["final"], row["state_after_saveflag"] = final, final_state
            self.report_changed()
            row["after_final_diff"] = self.standard_diff(after, final)
            self.report_changed()
            document = self.standard_roundtrip(document, kind, front, final, final_state, context, row, label,
                                               index + 1 < len(self.standard_plan))
            row["success"] = True
            self.report_changed()
            current = final
            self.persist()
        case["successful_planned_transitions"] = len(self.standard_plan)
        self.report_changed()
        case["calibrated_scope_note"] = "only GB-to-each-named-and-back for this document type and fixed drafting-defaults-v1"
        self.report_changed()
        return document

    def run_case(self, kind):
        row = {"kind": kind, "success": False, "writes": []}
        self.report["cases"].append(row)
        self.report_changed()
        self.persist()
        document, row["baseline"] = self.create(kind, kind + "-target")
        self.report_changed()
        front, row["foreground_baseline"] = self.create("part", kind + "-foreground")
        self.report_changed()
        row["initial"] = self.observe(document, kind, front, kind + ".initial")
        self.report_changed()
        if self.args.stage == "fonts":
            document = self.font_stage(document, kind, front, row)
        elif self.args.stage == "display":
            document = self.display_stage(document, kind, front, row)
        elif self.args.stage == "standards":
            document = self.standards_stage(document, kind, front, row)
        else:
            row["read_only_options"], row["no_preference_setters"] = True, True
            self.report_changed()
            row["standard_probe_requirements"] = ["declare finite observed_defaults field/option/document-type manifest", "read declared font/substandard/dimension defaults", "record pre/post transition differences within that manifest", "persist and read back declared defaults", "make no claim about unobserved settings"]
            self.report_changed()
        self.close(document, kind + ".close-target")
        self.close(front, kind + ".close-foreground")
        self.restore(kind + ".case-end")
        row["success"] = True
        self.report_changed()
        self.persist()

    def cleanup(self):
        self.cleanup_mode = True
        if self.trusted:
            for row in reversed(list(self.live)):
                if row["close_attempted"]:
                    self.report["cleanup_errors"].append({"stage": "CloseDoc", "identity": row["identity"], "error": "previous attempt failed; no retry"})
                    self.report_changed()
                    continue
                try:
                    self.close(row["document"], "cleanup." + row["identity"])
                except BaseException as error:
                    self.report["cleanup_errors"].append({"stage": "CloseDoc", "identity": row["identity"], "error": str(error)})
                    self.report_changed()
                    self.persist()
            if not self.live and not self.restore_failed:
                try:
                    self.restore("cleanup")
                except BaseException as error:
                    self.report["cleanup_errors"].append({"stage": "restore-original-foreground", "error": str(error)})
                    self.report_changed()
            try:
                self.original_invariants("final-originals", foreground=True)
                self.report["original_catalog_identity_preserved"] = True
                self.report_changed()
                self.report["global_templates_after"] = self.templates("global-templates-after")
                self.report_changed()
                self.report["visibility_after"] = self.get(self.app, "Visible", "final-host")
                self.report_changed()
            except BaseException as error:
                self.report["cleanup_errors"].append({"stage": "final-originals", "error": str(error)})
                self.report_changed()
        for name, before in {**self.report["source_files"], **self.report["file_hashes"]}.items():
            try:
                path = Path(name)
                require(path.is_file() and digest(path) == before["sha256"] and path.stat().st_size == before["size"], "native evidence file changed: " + name)
            except BaseException as error:
                self.report["cleanup_errors"].append({"stage": "source-file-hash", "error": str(error)})
                self.report_changed()
        try:
            remaining = self.call("snapshot-processes-after", process_ids)
            self.report["remaining_process_ids"] = remaining
            self.report_changed()
            self.report["manual_host_still_running"] = self.args.attach_pid in remaining
            self.report_changed()
            before = set(self.report.get("existing_process_ids", []))
            after = set(remaining)
            self.report["existing_process_ids_preserved"] = before <= after
            self.report_changed()
            self.report["process_changes"] = {
                "exited_process_ids": sorted(before - after),
                "started_process_ids": sorted(after - before),
                "other_exited_process_ids": sorted((before - after) - {self.args.attach_pid}),
                "other_started_process_ids": sorted((after - before) - {self.args.attach_pid}),
            }
            self.report_changed()
            require(self.report["manual_host_still_running"], "manual/target host process missing")
            if not getattr(self.args, "isolated_host", False):
                require(self.report["existing_process_ids_preserved"], "preexisting host process missing")
        except BaseException as error:
            self.report["cleanup_errors"].append({"stage": "remaining-processes", "error": str(error)})
            self.report_changed()
        self.report["remaining_registered_test_documents"] = [{key: value for key, value in row.items() if key != "document"} for row in self.live]
        self.report_changed()
        self.report["success"] = bool(self.report["success"] and not self.report["cleanup_errors"] and not self.live)
        self.report_changed()
        self.report["elapsed_seconds"] = time.monotonic() - self.started
        self.report_changed()
        self.persist()
        self.trace.close()

    def run(self):
        import pythoncom
        import win32com.client
        from swcli.hosts.windows import _com_value
        from swcli.hosts.windows_custom_properties import _state
        from swcli.hosts.windows_document_annotations import _edit_context, _verify_context, _writable_context
        from swcli.hosts.windows_documents import open_windows_document_with_handle
        from swcli.hosts.windows_sketches import create_rectangle_sketch_windows_with_handle
        from swcli.hosts.windows_features import extrude_sketch_windows_with_handle
        from swcli.hosts.windows_measurements import measure_part_windows
        from swcli.hosts.windows_feature_inspection import _same
        from swcli.hosts.windows_parts import create_part_windows_with_handle, _resolve_document_template
        from swcli.hosts.windows_assemblies import create_assembly_windows_with_handle
        from swcli.hosts.windows_drawings import create_drawing_windows_with_handle
        from swcli.hosts.windows_native_files import save_as_native_windows
        self.pythoncom, self.client = pythoncom, win32com.client
        self.com_value, self.native_state, self.native_same = _com_value, _state, _same
        self.edit_context, self.verify_context = _edit_context, _verify_context
        self.create_part, self.create_assembly, self.create_drawing = create_part_windows_with_handle, create_assembly_windows_with_handle, create_drawing_windows_with_handle
        self.resolve_template = _resolve_document_template
        self.save_native, self.open_native = save_as_native_windows, open_windows_document_with_handle
        self.rectangle, self.extrude, self.measure = create_rectangle_sketch_windows_with_handle, extrude_sketch_windows_with_handle, measure_part_windows
        self.writable_context = _writable_context
        if self.args.stage == "standards":
            from swcli.hosts.windows_document_drafting_standard import _read_snapshot
            from swcli.hosts.native_trace import trace_native_request, native_call
            # Only this Python diagnostic process is affected; no SW setting or
            # machine environment is changed. Driver must retain stderr intact.
            os.environ["SWCLI_TRACE_NATIVE_CALLS"] = "1"
            self.report_changed()
            self.standard_reader, self.standard_trace, self.standard_native_call = _read_snapshot, trace_native_request, native_call
            self.report["standard_native_leaf_trace"] = "flushed stderr via trace_native_request"
            self.report_changed()
        pythoncom.CoInitialize()
        try:
            self.attach()
            if self.args.stage == "standards":
                self.standard_catalog()
            for kind in ("part", "assembly", "drawing"):
                self.run_case(kind)
            self.report["success"] = True
            self.report_changed()
        except BaseException as error:
            self.report["failure"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
            self.report_changed()
            self.persist()
        finally:
            self.cleanup()
            self.app = None
            self.live.clear()
            self.report_changed()
            self.originals.clear()
            self.report_changed()
            self.original_foreground = None
            pythoncom.CoUninitialize()
        return 0 if self.report["success"] else 1


def main():
    args = arguments()
    if sys.platform != "win32":
        raise SystemExit("native execution requires Windows; --help is portable")
    calibration = Calibration(args, owned_interface=globals().pop("_SWCLI_OWNED_INTERFACE", None))
    code = calibration.run()
    print(json.dumps({"success": calibration.report["success"], "report": str(calibration.output / "report.json"),
                      "failure": calibration.report.get("failure"), "cleanup_errors": calibration.report["cleanup_errors"]}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
