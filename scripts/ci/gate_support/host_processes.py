"""Read-only native process inventory for an isolated CI runner/container.

Do not confuse Wine's Windows PID with a Unix PID, or assume a PID is never
recycled. Only numeric IDs are retained; process command lines are not evidence.
"""
import csv
import ntpath
import subprocess
import sys


def solidworks_process_ids(*, timeout=10):
    windows = sys.platform == "win32"
    command = ["tasklist", "/FO", "CSV", "/NH"] if windows else ["ps", "-axo", "pid=,comm="]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("Native process inventory is unavailable")
    ids = []
    rows = csv.reader(result.stdout.splitlines()) if windows else (
        line.strip().split(None, 1) for line in result.stdout.splitlines() if line.strip())
    for row in rows:
        if len(row) < 2:
            raise RuntimeError("Malformed native process inventory")
        name, pid = (row[0], row[1]) if windows else (row[1], row[0])
        if not pid.isdecimal():
            raise RuntimeError("Native process inventory has an invalid PID")
        if ntpath.basename(name.strip('"')).casefold() == "sldworks.exe":
            ids.append(int(pid))
    return ids
