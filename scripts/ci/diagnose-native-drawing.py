"""CI-only direct COM control. No swcli imports, daemon, registry, save or retry.

Run with the adapter's Windows Python in a disposable installed CI prefix.
One child owns one STA/SOLIDWORKS instance for both opens. The supervisor
enforces the original per-call budget and only terminates the acquired PID.
This is diagnostic evidence, never functional/full acceptance.
"""
import argparse
import csv
import hashlib
import json
import math
import multiprocessing
import ntpath
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

BACKTRACE_TIMEOUT_SECONDS = 30
BACKTRACE_MAX_BYTES = 2 * 1024 * 1024


def owned_threads(pid):
    """Enumerate only this native PID's threads; never use WineDbg's bt all.

    bt all can attach to other Wine processes, even with an initial PID.
    Explicit thread IDs retain the probe's ownership boundary.
    """
    import ctypes
    from ctypes import wintypes
    if type(pid) is not int or pid <= 0:
        raise ValueError("Invalid owned process ID")

    class ThreadEntry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ThreadID", wintypes.DWORD), ("th32OwnerProcessID", wintypes.DWORD),
                    ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Thread32First.argtypes = kernel.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
    kernel.Thread32First.restype = kernel.Thread32Next.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
    if snapshot is None or snapshot == ctypes.c_void_p(-1).value:
        raise OSError("Thread snapshot unavailable")
    try:
        entry = ThreadEntry()
        entry.dwSize = ctypes.sizeof(entry)
        found = []
        more = kernel.Thread32First(snapshot, ctypes.byref(entry))
        if not more:
            raise OSError("Thread snapshot is empty")
        while more:
            if entry.th32OwnerProcessID == pid:
                found.append(int(entry.th32ThreadID))
            entry.dwSize = ctypes.sizeof(entry)
            more = kernel.Thread32Next(snapshot, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES, not a partial inventory
            raise OSError("Thread snapshot enumeration failed")
        if not found or len(found) > 256:
            raise RuntimeError("Owned thread inventory missing or exceeds diagnostic bound")
        return sorted(set(found))
    finally:
        kernel.CloseHandle(snapshot)


def timeout_backtrace(record, output_dir, *, clock=time.monotonic):
    """Post-failure text only. Never allows a failed CAD call to pass later."""
    observation = {"after_failure": True, "tool": "winedbg", "timeout_seconds": BACKTRACE_TIMEOUT_SECONDS,
                   "max_bytes": BACKTRACE_MAX_BYTES, "success": False}
    record["timeout_backtrace"] = observation
    started = clock()
    try:
        host = record.get("host", {})
        pid = host.get("process_id")
        if (record.get("error", {}).get("type") != "NativeCallTimeout"
                or record["error"].get("call") != "OpenDoc6"
                or host.get("owned_by_probe") is not True or host.get("owned_by_daemon") is not False
                or type(pid) is not int or pid <= 0):
            raise RuntimeError("Native timeout and probe ownership required")
        if pid not in native_pids():
            raise RuntimeError("Owned native host already exited")
        threads = owned_threads(pid)
        if any(type(tid) is not int or tid <= 0 for tid in threads) or not threads or len(threads) > 256:
            raise RuntimeError("Invalid owned thread inventory")
        debugger = Path(os.environ["SystemRoot"]) / "system32/winedbg.exe"
        if not debugger.is_file():
            raise RuntimeError("Bundled Wine debugger is unavailable")
        commands = "echo \"probe-backtrace-begin\"\n" + "\n".join("bt " + str(tid) for tid in threads)
        commands += '\ninfo share\necho "probe-backtrace-end"\ndetach\n'
        observation.update(process_id=pid, thread_ids=threads, call=record["error"]["call"],
                           sequence=record["error"]["sequence"], evidence="timeout-backtrace.log")
        environment = dict(os.environ, WINEDEBUG="-all", _NT_SYMBOL_PATH="", _NT_ALT_SYMBOL_PATH="")
        with tempfile.TemporaryFile() as stream:
            try:
                result = subprocess.run([str(debugger), "--command", commands, str(pid)],
                                        stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                        timeout=BACKTRACE_TIMEOUT_SECONDS, env=environment)
                observation["exit_code"] = result.returncode
            finally:
                stream.seek(0)
                data = stream.read(BACKTRACE_MAX_BYTES + 1)
                observation["truncated"] = len(data) > BACKTRACE_MAX_BYTES
                with (output_dir / "timeout-backtrace.log").open("xb") as output:
                    output.write(data[:BACKTRACE_MAX_BYTES])
            # Exit zero alone does not prove commands parsed or stacks were captured.
            observation["frame_lines"] = len(re.findall(rb"(?m)^(?:=>|\s+)\d+\s+0x[0-9a-fA-F]+", data))
            observation["success"] = (result.returncode == 0 and not observation["truncated"]
                                      and b"probe-backtrace-end" in data and b"Backtrace:" in data
                                      and observation["frame_lines"] > 0
                                      and b"syntax error" not in data.lower() and b"Can't attach" not in data)
    except Exception as error:
        observation["diagnostic_error"] = type(error).__name__
    finally:
        observation["elapsed_seconds"] = clock() - started


def diagnose_timeout(args, record, checkpoint):
    if (getattr(args, "timeout_backtrace", False)
            and record.get("error", {}).get("type") == "NativeCallTimeout"
            and record["error"].get("call") == "OpenDoc6"):
        record["success"] = False
        checkpoint()  # Commit the business failure before any debugger attaches.
        timeout_backtrace(record, args.output_dir)
        checkpoint()


def value(obj, name):
    member = getattr(obj, name)
    return member() if callable(member) else member


def native_pids():
    result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                            text=True, timeout=10, check=True)
    rows = list(csv.reader(result.stdout.splitlines()))
    if not rows or any(len(row) < 2 or not row[1].isdecimal() for row in rows):
        raise RuntimeError("Native process inventory is unavailable")
    return [int(row[1]) for row in rows if ntpath.basename(row[0]).lower() == "sldworks.exe"]


def wait_for_exit(pid, *, timeout=30, clock=time.monotonic, sleep=time.sleep):
    """Read-only shutdown observation, not another CAD request or restart."""
    deadline = clock() + timeout
    while True:
        remaining = native_pids()
        if pid not in remaining or clock() >= deadline:
            return remaining
        sleep(0.2)


def validate_receipt(record):
    host = record.get("host", {})
    pid = host.get("process_id")
    opened = [event for event in record["events"] if event.get("event") == "opened"]
    closed = [event for event in record["events"] if event.get("event") == "closed"]
    if (type(pid) is not int or pid <= 0 or host.get("owned_by_probe") is not True
            or host.get("owned_by_daemon") is not False
            or [event.get("index") for event in opened] != [1, 2]
            or [event.get("index") for event in closed] != [1, 2]
            or any(event.get("process_id") != pid or event.get("api_errors") != 0
                   or event.get("api_warnings") != 0 for event in opened)
            or any(event.get("open_document_count") != 0 for event in closed)):
        raise RuntimeError("Direct control lacks two same-host clean open/close observations")


def stop_owned_worker(process, record):
    if process.pid is None or not process.is_alive():
        return
    # Never substitute process-name/global termination when acquisition failed.
    pid = record.get("host", {}).get("process_id")
    try:
        if type(pid) is int and pid > 0:
            killed = subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=30)
            if killed.returncode and pid in native_pids():
                record["cleanup_errors"].append({"type": "OwnedHostCleanupFailed"})
        else:
            record["cleanup_errors"].append({"type": "HostOwnershipNotEstablished"})
    except Exception as error:
        record["cleanup_errors"].append({"type": type(error).__name__, "stage": "owned-host-cleanup"})
    finally:
        process.terminate()
        process.join(10)
        if process.is_alive():
            record["cleanup_errors"].append({"type": "WorkerCleanupFailed"})


def direct_roundtrip(client, pythoncom, path, emit, *, visible=False,
                     startup_timeout=300, clock=time.monotonic, sleep=time.sleep):
    """Keep the native chain independent of all SWCLI adapter/worker helpers."""
    sequence = 0
    app = None
    failure = None

    def call(name, function):
        nonlocal sequence
        sequence += 1
        number, started = sequence, clock()
        emit({"event": "native-call", "phase": "begin", "call": name, "sequence": number,
              "monotonic_seconds": started})
        result = function()
        emit({"event": "native-call", "phase": "end", "call": name, "sequence": number,
              "duration_seconds": clock() - started})
        return result

    try:
        # Unknown ROT errors are not absence and must not launch another host.
        try:
            client.GetActiveObject("SldWorks.Application")
        except pythoncom.com_error as error:
            if error.hresult & 0xFFFFFFFF not in (0x800401E3, 0x80040154):
                raise
        else:
            raise RuntimeError("Direct probe refuses an existing COM host")
        app = call("DispatchEx", lambda: client.DispatchEx("SldWorks.Application"))
        pid = int(call("GetProcessID", lambda: value(app, "GetProcessID")))
        if pid <= 0:
            raise RuntimeError("Invalid acquired host PID")
        emit({"event": "host-acquired", "process_id": pid, "owned_by_probe": True,
              "owned_by_daemon": False})
        if visible:
            app.UserControl = True
        else:
            app.UserControlBackground = True
        app.Visible = visible
        deadline = clock() + startup_timeout
        while not call("StartupProcessCompleted", lambda: value(app, "StartupProcessCompleted")):
            if clock() >= deadline:
                raise TimeoutError("Native host startup exceeded its budget")
            pythoncom.PumpWaitingMessages()
            sleep(0.2)
        emit({"event": "ready", "process_id": pid, "visible": bool(value(app, "Visible")),
              "revision": str(value(app, "RevisionNumber")),
              "command_in_progress": bool(value(app, "CommandInProgress"))})
        if bool(value(app, "Visible")) is not visible:
            raise RuntimeError("Incorrect native host visibility")
        if int(call("GetDocumentCount", lambda: value(app, "GetDocumentCount"))) != 0:
            raise RuntimeError("Direct probe requires an empty new host")
        for index in (1, 2):
            errors = client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            warnings = client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            document = call("OpenDoc6", lambda: app.OpenDoc6(str(path), 3, 1, "", errors, warnings))
            if document is None or int(errors.value) != 0 or int(warnings.value) != 0:
                raise RuntimeError("Direct writable drawing open failed or warned")
            title = str(value(document, "GetTitle"))
            if (int(value(document, "GetType")) != 3
                    or ntpath.normcase(str(value(document, "GetPathName"))) != ntpath.normcase(str(path))):
                raise RuntimeError("Direct open returned a different document")
            if int(value(app, "GetProcessID")) != pid:
                raise RuntimeError("Native host changed inside the control")
            emit({"event": "opened", "index": index, "process_id": pid,
                  "api_errors": int(errors.value), "api_warnings": int(warnings.value)})
            # Release the exact return reference before CloseDoc. Do not invoke
            # structure traversal, registry discovery, gc, delay or a failed API again.
            document = None
            call("CloseDoc", lambda: app.CloseDoc(title))
            count = int(call("GetDocumentCount", lambda: value(app, "GetDocumentCount")))
            emit({"event": "closed", "index": index, "open_document_count": count})
            if count != 0:
                raise RuntimeError("Direct close left open documents")
    except Exception as error:
        failure = {"type": type(error).__name__, "message": str(error)}
        emit({"event": "case-error", "error": failure})
        raise
    finally:
        if app is not None:
            try:
                call("ExitApp", lambda: value(app, "ExitApp"))
            except Exception as error:
                emit({"event": "cleanup-error", "error": {"type": type(error).__name__, "message": str(error)}})
                if failure is None:
                    raise
            app = None


def worker(connection, path, visible, startup_timeout):
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    try:
        direct_roundtrip(win32com.client, pythoncom, path, connection.send,
                         visible=visible, startup_timeout=startup_timeout)
        connection.send({"event": "finished", "success": True})
    except Exception:
        # The first error was sent before attempting cleanup. A failed process
        # cannot acquire a success marker just because cleanup subsequently works.
        connection.send({"event": "finished", "success": False})
        raise
    finally:
        pythoncom.CoUninitialize()
        connection.close()


def monitor(process, connection, record, checkpoint, *, request_timeout, startup_timeout,
            clock=time.monotonic):
    started = clock()
    last_progress = started
    ready = False
    active = None
    finished = False
    while True:
        if connection.poll(0.1):
            try:
                event = connection.recv()
            except EOFError:
                break
            record["events"].append(event)
            event["observed_elapsed_seconds"] = clock() - started
            last_progress = clock()
            if event["event"] == "host-acquired":
                record["host"] = event
            elif event["event"] == "ready":
                ready = True
                record["ready"] = event
            elif event["event"] == "native-call":
                active = (event, clock()) if event["phase"] == "begin" else None
            elif event["event"] == "case-error":
                record.setdefault("error", event["error"])
            elif event["event"] == "cleanup-error":
                record["cleanup_errors"].append(event["error"])
            elif event["event"] == "finished":
                finished = event["success"] is True
            checkpoint()
        elif not process.is_alive():
            break
        now = clock()
        if ((not ready and now - started > startup_timeout)
                or (active and now - active[1] > (30 if active[0]["call"] == "ExitApp" else request_timeout))
                or (ready and active is None and now - last_progress > 30)):
            error = {"type": "NativeCallTimeout", "call": active[0]["call"] if active else None,
                     "sequence": active[0]["sequence"] if active else None,
                     "message": "Direct native control exceeded its retained budget"}
            if "error" in record:
                record["cleanup_errors"].append(error)
            else:
                record["error"] = error
            checkpoint()
            return False
    process.join(10)
    return finished and process.exitcode == 0 and "error" not in record and not record["cleanup_errors"]


def run(args):
    if sys.platform != "win32" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Direct COM probe is restricted to isolated Windows CI/Wine runners")
    if getattr(args, "timeout_backtrace", False) and not os.environ.get("WINEPREFIX"):
        raise RuntimeError("Wine-only timeout backtrace requires the isolated prefix")
    if (getattr(args, "timeout_backtrace", False)
            and not (Path(os.environ.get("SystemRoot", "")) / "system32/winedbg.exe").is_file()):
        raise RuntimeError("Requested Wine debugger is missing; refuse an uninstrumented repeat")
    if not (0 < args.request_timeout <= 600 and 0 < args.startup_timeout <= 300
            and math.isfinite(args.request_timeout) and math.isfinite(args.startup_timeout)):
        raise ValueError("Direct probe cannot increase the accepted request/startup budgets")
    source = args.source.resolve(strict=True)
    if source.suffix.lower() != ".slddrw" or source.stat().st_size < 512:
        raise RuntimeError("Direct control requires the official drawing fixture")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    receipt = args.output_dir / "native-com.json"
    with receipt.open("x", encoding="utf-8") as stream:
        stream.write("{}\n")
    record = {"completed": False, "success": False, "diagnostic_case": "drawing-native-reopen",
              "coverage_scope": "direct-native-control", "full_acceptance_eligible": False,
              "save_attempted": False, "structure_inspected": False, "events": [], "cleanup_errors": [],
              "request_timeout_seconds": args.request_timeout, "startup_timeout_seconds": args.startup_timeout}
    record["timeout_backtrace_requested"] = getattr(args, "timeout_backtrace", False)

    def checkpoint():
        temporary = receipt.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(receipt)

    process = None
    try:
        if native_pids():
            raise RuntimeError("Direct control refuses pre-existing SOLIDWORKS processes")
        args.work_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="native-drawing-", dir=args.work_dir) as temporary:
            fixture = Path(temporary)
            if any(path.is_symlink() for path in source.parent.rglob("*")):
                raise RuntimeError("Native fixture bundle contains a symlink")
            shutil.copytree(source.parent, fixture, dirs_exist_ok=True)
            target = fixture / "drawing.SLDDRW"
            with target.open("xb") as stream:
                stream.write(source.read_bytes())
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            record.update(source_sha256_before=before, copy_sha256_before=hashlib.sha256(target.read_bytes()).hexdigest(),
                          path=str(target), visible_requested=args.visible)
            if record["copy_sha256_before"] != before:
                raise RuntimeError("Private drawing copy does not match its source")
            context = multiprocessing.get_context("spawn")
            receiver, sender = context.Pipe(duplex=False)
            process = context.Process(target=worker, args=(sender, str(target), args.visible, args.startup_timeout))
            try:
                checkpoint()
                process.start()
                sender.close()
                record["success"] = monitor(process, receiver, record, checkpoint,
                                            request_timeout=args.request_timeout, startup_timeout=args.startup_timeout)
                diagnose_timeout(args, record, checkpoint)
            finally:
                stop_owned_worker(process, record)
                receiver.close()
                record["source_sha256_after"] = hashlib.sha256(source.read_bytes()).hexdigest()
                record["copy_sha256_after"] = hashlib.sha256(target.read_bytes()).hexdigest()
                if record["source_sha256_after"] != before or record["copy_sha256_after"] != before:
                    raise RuntimeError("Direct control changed drawing bytes without saving")
        remaining = wait_for_exit(record.get("host", {}).get("process_id"))
        record["remaining_process_ids"] = remaining
        if remaining or record["cleanup_errors"]:
            record["success"] = False
        if not record["success"]:
            raise RuntimeError("Direct native drawing control failed; see native-com.json")
        validate_receipt(record)
    except Exception as error:
        record["success"] = False
        record.setdefault("error", {"type": type(error).__name__, "message": str(error)})
        raise
    finally:
        record["completed"] = True
        checkpoint()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--request-timeout", type=float, default=600)
    parser.add_argument("--startup-timeout", type=float, default=300)
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--timeout-backtrace", action="store_true",
                        help="Wine CI only: bounded text stacks after OpenDoc6 already failed its deadline")
    run(parser.parse_args())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
