"""TEST ONLY: prepare one native equation in the production worker's STA.

No new protocol operation or production hook is installed. A private local
one-shot request is consumed only after a validated document.inspect for the
exact test session/document. All business requests still use installed SWCLI.
"""
import importlib.util
import json
import multiprocessing
from pathlib import Path
import sys

from swcli.daemon import server
from swcli.hosts.windows import _com_value

spec = importlib.util.spec_from_file_location(
    "equation_fixture", Path(__file__).with_name("verify-equation-dimension.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def install_fixture_hook(directory):
    directory = Path(directory).resolve(strict=True)
    original = server.execute_operation

    def execute(app, operation, parameters, **context):
        result = original(app, operation, parameters, **context)
        request = directory / "request.json"
        if operation != "document.inspect" or not result.get("ok") or not request.exists():
            return result
        values = json.loads(request.read_text(encoding="utf-8"))
        if (context.get("session_id") != values["session_id"]
                or context.get("document_id") != values["document_descriptor"]["document_id"]):
            return result
        request.rename(directory / "consumed.json")  # Never retry native mutation.
        receipt = directory / "result.json"
        try:
            fixture.require(result["document"]["document_id"] == values["document_descriptor"]["document_id"],
                            "fixture document identity changed")
            native = fixture.add_native_equation(
                process_id=values["process_id"], document_descriptor=values["document_descriptor"],
                native_name=values["native_name"], app=app)
            native.update(attachment="worker-owned-STA", visible=bool(_com_value(app, "Visible")))
            payload = {"success": True, "native_fixture": native}
        except Exception as exc:
            payload = {"success": False, "native_fixture": getattr(exc, "native_fixture", {}),
                       "error": {"type": type(exc).__name__, "message": str(exc)}}
        with receipt.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
        return result

    server.execute_operation = execute


# Windows spawn reimports this entry point before starting the real worker.
if __name__ in ("__main__", "__mp_main__"):
    install_fixture_hook(sys.argv[1])
    if __name__ == "__main__":
        multiprocessing.freeze_support()
        from swcli.cli import main
        raise SystemExit(main(sys.argv[2:]))
