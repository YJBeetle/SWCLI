"""Opt-in bounded evidence around the original GLB save, without changing it."""
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys
import time
from uuid import uuid4

from .native_trace import native_call, current_request_context
from .windows import _com_value

MAX_FILES = 128
MAX_BYTES = 64 * 1024 * 1024
MAX_MODULES = 2048
PHASE_SECONDS = 15
PREFERENCE_GETTERS = {
    "swUserPreferenceToggle_e": "GetUserPreferenceToggle",
    "swUserPreferenceIntegerValue_e": "GetUserPreferenceIntegerValue",
    "swUserPreferenceDoubleValue_e": "GetUserPreferenceDoubleValue",
    "swUserPreferenceStringValue_e": "GetUserPreferenceStringValue",
}


def _error(exc):
    try:
        message = str(exc)[:1000]
    except Exception:
        message = "diagnostic exception message unavailable"
    return {"type": type(exc).__name__, "message": message}


def _notice(record):
    try:
        sys.stderr.write(json.dumps({"event": "swcli.glb-diagnostics", **record}, allow_nan=False) + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def _related(name):
    return (any(word in name.casefold() for word in ("gltf", "glb", "draco", "xrexport", "exportxr", "extendedreality"))
            or re.search(r"(?:^sw|^|_)XR(?:[A-Z_]|$)", name) is not None)


def _modules(pid):
    """Query only the observed SOLIDWORKS PID with read access."""
    import win32api
    import win32con
    import win32process
    started = time.monotonic()
    filters = ("sldgltf", "spaxgltf", "visgltf", "draco", "xrexporter")
    result = {"pid": pid, "status": "complete", "name_filters": list(filters), "modules": [], "errors": []}
    handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
    try:
        modules = win32process.EnumProcessModules(handle)
        result["enumerated_count"] = len(modules)
        if len(modules) > MAX_MODULES:
            raise RuntimeError("loaded module inventory exceeds bound")
        for module in modules:
            if time.monotonic() - started > PHASE_SECONDS:
                raise RuntimeError("loaded module inventory exceeded time bound")
            try:
                path = win32process.GetModuleFileNameEx(handle, module)
                if not any(word in PureWindowsPath(path).name.casefold() for word in filters):
                    continue
                row = {"path": path, "file_version": None, "product_version": None}
                result["modules"].append(row)
                info = win32api.GetFileVersionInfo(path, "\\")
                for field, prefix in (("file_version", "FileVersion"), ("product_version", "ProductVersion")):
                    high, low = info[prefix + "MS"], info[prefix + "LS"]
                    row[field] = [high >> 16, high & 65535, low >> 16, low & 65535]
            except Exception as exc:
                result["status"] = "incomplete"
                result["errors"].append(_error(exc))
    finally:
        handle.Close()
    return result


def _preferences(app):
    """Resolve names from the actual SW2025 typelib, then call known global getters."""
    import pythoncom
    path = Path(os.environ.get("SWCLI_GLB_DIAGNOSTICS_SWCONST", ""))
    if not path.is_absolute() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise RuntimeError("explicit bounded installed swconst.tlb is unavailable")
    library = pythoncom.LoadTypeLib(str(path))
    identity = library.GetLibAttr()
    result = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "major": identity[3], "status": "complete", "matches": []}
    if identity[3] != 33:
        raise RuntimeError("GLB diagnostic getters require the installed SW2025 typelib")
    count = library.GetTypeInfoCount()
    if count > 4096:
        raise RuntimeError("typelib type count exceeds bound")
    started = time.monotonic()
    for index in range(count):
        if time.monotonic() - started > PHASE_SECONDS:
            raise RuntimeError("typelib observation exceeded time bound")
        info = library.GetTypeInfo(index)
        attr = info.GetTypeAttr()
        if attr.typekind != pythoncom.TKIND_ENUM:
            continue
        enum_name = library.GetDocumentation(index)[0]
        if attr.cVars > 4096:
            raise RuntimeError("typelib enum size exceeds bound")
        for offset in range(attr.cVars):
            if time.monotonic() - started > PHASE_SECONDS:
                raise RuntimeError("typelib observation exceeded time bound")
            desc = info.GetVarDesc(offset)
            name = info.GetDocumentation(desc[0])[0]
            if not _related(name) and not _related(enum_name):
                continue
            if len(result["matches"]) >= MAX_FILES:
                raise RuntimeError("matching typelib entries exceed bound")
            row = {"enum": enum_name, "name": name, "id": desc.value if type(desc.value) is int else None, "read_status": "not-a-known-global-preference"}
            result["matches"].append(row)
            getter_name = PREFERENCE_GETTERS.get(enum_name)
            if getter_name is None or type(desc.value) is not int:
                continue
            try:
                value = native_call("glb-diagnostics-readonly", "ISldWorks." + getter_name + "." + name,
                                    lambda: getattr(app, getter_name)(desc.value))
                if (type(value) not in (bool, int, float, str) or
                        isinstance(value, float) and not math.isfinite(value) or
                        isinstance(value, str) and len(value) > 4096):
                    raise RuntimeError("preference observation is not a bounded finite scalar")
                row.update(read_status="observed", getter=getter_name, value=value)
            except Exception as exc:
                row.update(read_status="unknown", error=_error(exc))
    return result


class _Evidence:
    def __init__(self, app, staging, output):
        self.app = app
        self.staging = staging
        self.prefix = staging.stem
        self.directory = output.parent / ("swcli-glb-diagnostics-" + uuid4().hex)
        self.directory.mkdir()
        self.pid = None
        self.report = {"schema": 1, "worker_pid": os.getpid(), "staging_path": str(staging),
                       "output_path": str(output), "prefix": self.prefix, "phases": {}, **current_request_context(),
                       "bounds": {"files_per_phase": MAX_FILES, "bytes_per_phase": MAX_BYTES,
                                  "seconds_per_observation": PHASE_SECONDS, "modules": MAX_MODULES},
                       "file_access_monitor": {"status": "unknown", "reason": "no verified PID-scoped bounded OS file-access collector is available"}}

    def _files(self, phase):
        started = time.monotonic()
        remaining = MAX_BYTES
        rows = []
        with os.scandir(self.staging.parent) as entries:
            for entry in entries:
                if time.monotonic() - started > PHASE_SECONDS:
                    rows.append({"status": "incomplete", "reason": "directory observation exceeded time bound"})
                    break
                if not entry.name.startswith(self.prefix):
                    continue
                if len(rows) >= MAX_FILES:
                    rows.append({"status": "incomplete", "reason": "same-prefix file count exceeds bound"})
                    break
                row = {"name": entry.name}
                rows.append(row)
                try:
                    observed = entry.stat(follow_symlinks=False)
                    row.update(size_bytes=observed.st_size, mtime_ns=observed.st_mtime_ns,
                               file_attributes=getattr(observed, "st_file_attributes", None))
                    if (not stat.S_ISREG(observed.st_mode) or entry.is_symlink() or
                            getattr(observed, "st_file_attributes", 0) & 0x400):
                        row["status"] = "unknown-nonregular-or-reparse"
                        continue
                    if observed.st_size > remaining:
                        raise RuntimeError("same-prefix byte budget exceeded")
                    destination = self.directory / (phase + "-" + str(len(rows)) + ".bin")
                    row["copy"] = destination.name
                    digest = hashlib.sha256()
                    copied = 0
                    with open(entry.path, "rb") as source, destination.open("xb") as target:
                        before = os.fstat(source.fileno())
                        if not stat.S_ISREG(before.st_mode) or (before.st_dev, before.st_ino) != (observed.st_dev, observed.st_ino):
                            raise RuntimeError("source identity changed before evidence copy")
                        while True:
                            if time.monotonic() - started > PHASE_SECONDS:
                                raise RuntimeError("evidence copy exceeded time bound")
                            data = source.read(min(1024 * 1024, remaining + 1))
                            if not data:
                                break
                            if len(data) > remaining:
                                raise RuntimeError("same-prefix byte budget exceeded")
                            target.write(data)
                            digest.update(data)
                            copied += len(data)
                            remaining -= len(data)
                        after = os.fstat(source.fileno())
                    row.update(copy=destination.name, copied_bytes=copied, sha256=digest.hexdigest(),
                               status="copied", stable_while_reading=(observed.st_size == before.st_size == copied == after.st_size
                                   and observed.st_mtime_ns == before.st_mtime_ns == after.st_mtime_ns))
                except Exception as exc:
                    row.update(status="unknown", error=_error(exc))
        return rows

    def _write_manifest(self):
        temporary = self.directory / "manifest.new"
        temporary.write_text(json.dumps(self.report, ensure_ascii=True, allow_nan=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.directory / "manifest.json")

    def observe(self, phase, receipt):
        record = {"started_monotonic": time.monotonic(), "position": "pre-save" if phase == "before" else "post-save-before-validation"}
        self.report["phases"][phase] = record
        if phase == "before":
            try:
                self.pid = _com_value(self.app, "GetProcessID")
                if type(self.pid) is not int or self.pid <= 0:
                    raise RuntimeError("actual SOLIDWORKS PID is unavailable")
            except Exception as exc:
                self.pid = None
                record["pid_error"] = _error(exc)
            self.report["solidworks_pid"] = self.pid
            try:
                record["typelib_preferences"] = _preferences(self.app)
            except Exception as exc:
                record["typelib_preferences"] = {"status": "unknown", "error": _error(exc)}
        try:
            record["modules"] = _modules(self.pid) if self.pid else {"status": "unknown", "reason": "PID unavailable"}
        except Exception as exc:
            record["modules"] = {"status": "unknown", "error": _error(exc)}
        try:
            record["files"] = self._files(phase)
        except Exception as exc:
            record["files_error"] = _error(exc)
        if phase == "after":
            record["save_receipt"] = {key: receipt[key] for key in ("save_attempted", "api_saved", "save_errors", "save_warnings", "error") if key in receipt}
        record["finished_monotonic"] = time.monotonic()
        self._write_manifest()
        _notice({"phase": phase, "manifest": str(self.directory / "manifest.json"),
                 "staging_path": str(self.staging), "request_id": self.report["request_id"]})


@contextmanager
def glb_runtime_evidence(app, staging, output, receipt, *, enabled):
    if not enabled or os.environ.get("SWCLI_GLB_RUNTIME_DIAGNOSTICS") != "1":
        yield
        return
    evidence = None
    try:
        evidence = _Evidence(app, staging, output)
        evidence.observe("before", receipt)
    except Exception as exc:
        _notice({"phase": "before", "status": "unknown", "error": _error(exc)})
    try:
        yield
    finally:
        if evidence is not None:
            try:
                evidence.observe("after", receipt)
            except Exception as exc:
                _notice({"phase": "after", "status": "unknown", "error": _error(exc)})
