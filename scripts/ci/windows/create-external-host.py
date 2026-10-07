"""Test-only external COM owner; no swcli import, daemon or consent automation."""

import json
import os
import sys
import time


def value(app, name):
    member = getattr(app, name)
    return member() if callable(member) else member


def create_host(com_client, pump, emit, *, clock=time.monotonic, sleep=time.sleep):
    app = com_client.DispatchEx("SldWorks.Application")
    ready = False
    try:
        pid = int(value(app, "GetProcessID"))
        emit({"phase": "host-acquired", "process_id": pid})
        app.UserControl = True
        app.Visible = True
        deadline = clock() + 120
        while not bool(value(app, "StartupProcessCompleted")):
            if clock() >= deadline:
                raise TimeoutError("external COM host startup did not complete")
            pump()
            sleep(0.2)
        result = {
            "phase": "ready",
            "process_id": pid,
            "fixture_process_id": os.getpid(),
            "revision": str(value(app, "RevisionNumber")),
            "visible": bool(value(app, "Visible")),
            "user_control": bool(value(app, "UserControl")),
        }
        if not result["visible"] or not result["user_control"]:
            raise RuntimeError("external COM host did not retain foreground lifetime")
        emit(result)
        ready = True
        # Release our COM reference on exit. UserControl keeps the external
        # instance alive independently of both this fixture and swclid.
        return result
    finally:
        if not ready:
            try:
                app.ExitApp()
            except Exception as exc:
                print(f"external fixture cleanup failed: {exc}", file=sys.stderr)


def main():
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    try:
        try:
            win32com.client.GetActiveObject("SldWorks.Application")
        except pythoncom.com_error as exc:
            if exc.hresult & 0xFFFFFFFF not in (0x800401E3, 0x80040154):
                raise
        else:
            raise RuntimeError("external fixture refuses to reuse an existing host")
        create_host(
            win32com.client,
            pythoncom.PumpWaitingMessages,
            lambda result: print(json.dumps(result, allow_nan=False), flush=True),
        )
    finally:
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
