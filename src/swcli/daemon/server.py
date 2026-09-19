"""Local swclid supervisor with a replaceable single-threaded COM worker."""

from __future__ import annotations

import json
import multiprocessing
import queue
import socketserver
import subprocess
import threading
import time
from typing import Any, Dict, Optional

from .. import PROTOCOL_VERSION, __version__
from ..hosts.windows import PROG_ID, _com_value, wait_windows_host_ready
from .operations import OPERATIONS, execute_operation


MAX_REQUEST_BYTES = 16 * 1024 * 1024


def _error_response(
    request_id: str, code: str, message: str, *, duration_ms: float = 0.0
) -> Dict[str, Any]:
    return {
        "api_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "success": False,
        "duration_ms": duration_ms,
        "error": {"code": code, "message": message},
    }


def _success_response(
    request_id: str, result: Any, *, duration_ms: float = 0.0
) -> Dict[str, Any]:
    return {
        "api_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "success": True,
        "duration_ms": duration_ms,
        "result": result,
    }


def validate_request(request: Any) -> Dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("request must be a JSON object")
    if request.get("api_version") != PROTOCOL_VERSION:
        raise ValueError("unsupported api_version")
    for name in ("request_id", "operation"):
        if not isinstance(request.get(name), str) or not request[name]:
            raise ValueError(f"{name} must be a non-empty string")
    if not isinstance(request.get("parameters"), dict):
        raise ValueError("parameters must be an object")
    timeout_ms = request.get("timeout_ms", 600000)
    if not isinstance(timeout_ms, int) or timeout_ms < 1:
        raise ValueError("timeout_ms must be a positive integer")
    request["timeout_ms"] = timeout_ms
    return request


def _describe_app(app: Any, startup_wait_seconds: float) -> Dict[str, Any]:
    revision = str(_com_value(app, "RevisionNumber"))
    return {
        "revision": revision,
        "solidworks_revision": revision,
        "process_id": int(_com_value(app, "GetProcessID")),
        "visible": bool(_com_value(app, "Visible")),
        "startup_wait_seconds": startup_wait_seconds,
    }


def configure_resident_app(app: Any, *, visible: bool) -> None:
    """Select the official foreground or background resident lifetime mode."""

    if visible:
        app.UserControl = True
        app.Visible = True
    else:
        app.UserControlBackground = True
        app.Visible = False


def _worker_main(
    request_queue: Any,
    response_queue: Any,
    ready_queue: Any,
    visible: bool,
    startup_timeout_seconds: float,
) -> None:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    app = None
    try:
        app = win32com.client.DispatchEx(PROG_ID)
        # SOLIDWORKS exposes separate lifetime controls for visible and hidden
        # resident automation. Both keep the application alive across requests.
        configure_resident_app(app, visible=visible)
        waited = wait_windows_host_ready(
            app, timeout_seconds=startup_timeout_seconds
        )
        ready_queue.put({"ok": True, "host": _describe_app(app, waited)})

        while True:
            request = request_queue.get()
            if request is None:
                break
            started_at = time.monotonic()
            request_id = str(request["request_id"])
            try:
                try:
                    _com_value(app, "RevisionNumber")
                except Exception as exc:
                    response_queue.put(
                        _error_response(
                            request_id,
                            "HostDisconnected",
                            f"SOLIDWORKS COM host is no longer available: {exc}",
                        )
                    )
                    break
                if request["operation"] == "__daemon.shutdown__":
                    if _com_value(app, "ActiveDoc") is not None:
                        response_queue.put(
                            _error_response(
                                request_id,
                                "ActiveDocument",
                                "refusing to stop swclid while a document is open",
                            )
                        )
                        continue
                    response_queue.put(
                        _success_response(request_id, {"stopping": True})
                    )
                    break
                result = execute_operation(
                    app, str(request["operation"]), dict(request["parameters"])
                )
                duration_ms = (time.monotonic() - started_at) * 1000.0
                if isinstance(result, dict) and not result.get("ok", True):
                    error = result.get("error") or {}
                    response = _error_response(
                        request_id,
                        str(error.get("type", "OperationFailed")),
                        str(error.get("message", "operation failed")),
                        duration_ms=duration_ms,
                    )
                    response["result"] = result
                else:
                    response = _success_response(
                        request_id, result, duration_ms=duration_ms
                    )
            except Exception as exc:
                response = _error_response(
                    request_id,
                    type(exc).__name__,
                    str(exc),
                    duration_ms=(time.monotonic() - started_at) * 1000.0,
                )
            response_queue.put(response)
    except Exception as exc:
        ready_queue.put(
            {"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}}
        )
    finally:
        if app is not None:
            try:
                if _com_value(app, "ActiveDoc") is None:
                    _com_value(app, "ExitApp")
            except Exception:
                pass
        pythoncom.CoUninitialize()


class WorkerManager:
    """Own one worker process and serialize all COM-bound requests through it."""

    def __init__(
        self,
        *,
        visible: bool = False,
        startup_timeout_seconds: float = 120.0,
        host_platform: str = "windows",
    ) -> None:
        self.visible = visible
        self.startup_timeout_seconds = startup_timeout_seconds
        self.host_platform = host_platform
        self._context = multiprocessing.get_context("spawn")
        self._lock = threading.Lock()
        self._process: Optional[Any] = None
        self._request_queue: Optional[Any] = None
        self._response_queue: Optional[Any] = None
        self.host: Dict[str, Any] = {}
        self._start_worker()

    def _start_worker(self) -> None:
        self._request_queue = self._context.Queue()
        self._response_queue = self._context.Queue()
        ready_queue = self._context.Queue()
        self._process = self._context.Process(
            target=_worker_main,
            args=(
                self._request_queue,
                self._response_queue,
                ready_queue,
                self.visible,
                self.startup_timeout_seconds,
            ),
            name="swclid-com-worker",
        )
        self._process.start()
        try:
            ready = ready_queue.get(timeout=self.startup_timeout_seconds + 5.0)
        except queue.Empty as exc:
            self._terminate_worker()
            raise TimeoutError("SOLIDWORKS worker startup timed out") from exc
        if not ready.get("ok"):
            self._terminate_worker()
            error = ready.get("error") or {}
            raise RuntimeError(
                f"SOLIDWORKS worker failed: {error.get('type')}: {error.get('message')}"
            )
        self.host = dict(ready["host"])
        self.host["platform"] = self.host_platform

    def _terminate_worker(self) -> None:
        forced = False
        if self._process is not None and self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=5.0)
            forced = True
            if self._process.is_alive():
                self._process.kill()
                self._process.join(timeout=5.0)
        if forced and self.host.get("process_id"):
            subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(self.host["process_id"]),
                    "/T",
                    "/F",
                ],
                check=False,
                capture_output=True,
            )
        self._process = None
        self.host = {}

    def call(self, request: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            if self._process is None or not self._process.is_alive():
                self._start_worker()
            assert self._request_queue is not None
            assert self._response_queue is not None
            self._request_queue.put(request)
            timeout_seconds = request["timeout_ms"] / 1000.0
            try:
                response = self._response_queue.get(timeout=timeout_seconds)
            except queue.Empty:
                self._terminate_worker()
                return _error_response(
                    request["request_id"],
                    "WorkerTimeout",
                    f"operation exceeded {request['timeout_ms']}ms; worker was replaced",
                    duration_ms=float(request["timeout_ms"]),
                )
            if (response.get("error") or {}).get("code") == "HostDisconnected":
                self._process.join(timeout=5.0)
                if self._process.is_alive():
                    self._terminate_worker()
                else:
                    self._process = None
                    self.host = {}
            return response

    def health(self) -> Dict[str, Any]:
        return {
            "server_version": __version__,
            "protocol_versions": [PROTOCOL_VERSION],
            "operations": list(OPERATIONS),
            "worker_alive": bool(
                self._process is not None and self._process.is_alive()
            ),
            "host": self.host,
        }

    def shutdown(self, request: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            if self._process is None or not self._process.is_alive():
                return _success_response(request["request_id"], {"stopping": True})
            assert self._request_queue is not None
            assert self._response_queue is not None
            control = dict(request)
            control["operation"] = "__daemon.shutdown__"
            self._request_queue.put(control)
            try:
                response = self._response_queue.get(timeout=15.0)
            except queue.Empty:
                return _error_response(
                    request["request_id"],
                    "ShutdownTimeout",
                    "COM worker did not stop within 15 seconds",
                )
            if response.get("success"):
                self._process.join(timeout=15.0)
            return response

    def close(self) -> None:
        with self._lock:
            self._terminate_worker()


class SwclidServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: Any, manager: Optional[WorkerManager] = None):
        self.manager = manager
        super().__init__(address, SwclidRequestHandler)

    def request_shutdown(self) -> None:
        threading.Thread(target=self.shutdown, daemon=True).start()


class SwclidRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline(MAX_REQUEST_BYTES + 1)
        request_id = "invalid-request"
        try:
            if not raw:
                return
            if len(raw) > MAX_REQUEST_BYTES:
                raise ValueError("request exceeds the maximum supported size")
            request = validate_request(json.loads(raw.decode("utf-8")))
            request_id = request["request_id"]
            if self.server.manager is None:
                response = _error_response(
                    request_id,
                    "Starting",
                    "swclid has bound the endpoint but its COM worker is not ready",
                )
            elif request["operation"] == "daemon.health":
                response = _success_response(request_id, self.server.manager.health())
            elif request["operation"] == "daemon.shutdown":
                response = self.server.manager.shutdown(request)
                if response.get("success"):
                    self.server.request_shutdown()
            else:
                response = self.server.manager.call(request)
        except Exception as exc:
            response = _error_response(request_id, type(exc).__name__, str(exc))
        self.wfile.write(
            json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
            + b"\n"
        )
