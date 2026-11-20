"""Bind the scoped Windows font worker to the watchdog's process handle."""
import json
import os
from pathlib import Path
import sys


def base_launch(environment):
    # Match CPython's Windows multiprocessing spawn. The venv executable
    # otherwise creates an intermediate redirector with a different PID.
    executable = sys._base_executable
    if not os.path.isabs(executable) or not Path(executable).is_file():
        raise ValueError("absolute base Python executable unavailable")
    env = dict(environment)
    env.pop("__PYVENV_LAUNCHER__", None)
    if os.path.normcase(executable) != os.path.normcase(sys.executable):
        env["__PYVENV_LAUNCHER__"] = sys.executable
    return executable, env


def windows_process_image():
    import ctypes
    from ctypes import wintypes

    get_module_file_name = ctypes.WinDLL("kernel32", use_last_error=True).GetModuleFileNameW
    get_module_file_name.argtypes = (wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD)
    get_module_file_name.restype = wintypes.DWORD
    path = ctypes.create_unicode_buffer(32768)
    length = get_module_file_name(None, path, len(path))
    if not 0 < length < len(path):
        raise OSError("Windows failed to report the worker process image")
    return path.value


def worker_identity(claimed_parent, expected_prefix, stream):
    parent, worker = os.getppid(), os.getpid()
    if claimed_parent is None or claimed_parent <= 0 or parent != claimed_parent:
        raise ValueError("worker parent PID does not match watchdog PID")
    if not sys.flags.isolated or not expected_prefix or os.path.normcase(sys.prefix) != os.path.normcase(expected_prefix):
        raise ValueError("worker did not retain the watchdog Python prefix in isolated mode")
    if stream.readline(32) != f"{worker}\n".encode("ascii"):
        raise ValueError("watchdog launch pipe did not identify this worker PID")
    image = windows_process_image()
    if not os.path.samefile(image, sys._base_executable):
        raise ValueError("worker image is not its base Python executable")
    return dict(parent_pid=parent, claimed_parent_pid=claimed_parent, worker_pid=worker,
                spawned_pid=worker, process_image=image, base_executable=sys._base_executable,
                prefix=sys.prefix, isolated=True)


def add_worker_options(parser):
    parser.add_argument("--watchdog-pid", type=int, help=__doc__)
    parser.add_argument("--watchdog-prefix", help=__doc__)
    parser.add_argument("--supervision-probe", action="store_true", help="verify Windows process identity without COM")


def verify_worker_launch(args, parser):
    """Reject a Windows scoped worker before any output or COM call."""
    proof = None
    if args.scope is not None and sys.platform == "win32":
        if args.watchdog_pid is None or sys.stdin is None or sys.stdin.isatty():
            parser.error("scoped Windows worker requires the font watchdog launch pipe")
        try:
            proof = worker_identity(args.watchdog_pid, args.watchdog_prefix, sys.stdin.buffer)
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
    elif args.supervision_probe or args.watchdog_pid is not None or args.watchdog_prefix is not None:
        parser.error("supervision options require a scoped Windows worker")
    return proof


def write_worker_output(output, proof):
    output.mkdir()
    if proof is not None:
        with (output / "supervision.json").open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(proof, indent=2) + "\n")


def check_worker_proof(path, *, worker_pid, parent_pid, executable, prefix):
    proof = json.loads(path.read_text(encoding="utf-8"))
    for key, expected in (("worker_pid", worker_pid), ("spawned_pid", worker_pid),
                          ("parent_pid", parent_pid), ("claimed_parent_pid", parent_pid)):
        if type(proof[key]) is not int or proof[key] != expected:
            raise ValueError("supervision receipt has a mismatched " + key)
    if (proof["isolated"] is not True
            or os.path.normcase(proof["prefix"]) != os.path.normcase(prefix)
            or not os.path.samefile(proof["process_image"], executable)
            or not os.path.samefile(proof["base_executable"], executable)):
        raise ValueError("supervision receipt does not match the launched Python environment")
