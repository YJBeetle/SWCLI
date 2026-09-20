"""Local swclid supervisor with a replaceable single-threaded COM worker."""

from __future__ import annotations

import json
import multiprocessing
import queue
import re
import socketserver
import subprocess
import threading
import time
from typing import Any, Dict, Optional

from .. import PROTOCOL_VERSION, __version__
from ..hosts.windows import PROG_ID, _com_value, wait_windows_host_ready
from .documents import DEFAULT_SESSION_ID, DocumentRegistry
from .operations import OPERATIONS, execute_operation


MAX_REQUEST_BYTES = 16 * 1024 * 1024
DOCUMENT_ID_PATTERN = re.compile(r"^d-[0-9a-hjkmnp-tv-z]{6}$")


class ExistingHostRequiresAttach(RuntimeError):
    """Raised when exclusive startup finds a user-controlled SOLIDWORKS host."""


class WorkerStartupError(RuntimeError):
    """Preserve a worker startup error code across the process boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


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
    session_id = request.get("session_id")
    if session_id is not None and (
        not isinstance(session_id, str) or not session_id
    ):
        raise ValueError("session_id must be a non-empty string when provided")
    document_id = request.get("document_id")
    if document_id is not None and (
        not isinstance(document_id, str)
        or (
            document_id != "active"
            and DOCUMENT_ID_PATTERN.fullmatch(document_id) is None
        )
    ):
        raise ValueError("document_id must be a d-... ID or 'active'")
    timeout_ms = request.get("timeout_ms", 600000)
    if not isinstance(timeout_ms, int) or timeout_ms < 1:
        raise ValueError("timeout_ms must be a positive integer")
    request["timeout_ms"] = timeout_ms
    return request


def _describe_app(
    app: Any, startup_wait_seconds: float, *, owned_by_daemon: bool
) -> Dict[str, Any]:
    revision = str(_com_value(app, "RevisionNumber"))
    return {
        "revision": revision,
        "solidworks_revision": revision,
        "language": str(_com_value(app, "GetCurrentLanguage")),
        "process_id": int(_com_value(app, "GetProcessID")),
        "visible": bool(_com_value(app, "Visible")),
        "startup_wait_seconds": startup_wait_seconds,
        "owned_by_daemon": owned_by_daemon,
        "shared_interactive": not owned_by_daemon,
    }


def configure_resident_app(app: Any, *, visible: bool) -> None:
    """Select the official foreground or background resident lifetime mode."""

    if visible:
        app.UserControl = True
        app.Visible = True
    else:
        app.UserControlBackground = True
        app.Visible = False


def acquire_resident_app(
    com_client: Any, *, visible: bool, attach_existing: bool = False
) -> tuple[Any, bool]:
    """Create an owned instance, or explicitly attach to a user instance."""

    try:
        app = com_client.GetActiveObject(PROG_ID)
    except Exception:
        app = com_client.DispatchEx(PROG_ID)
        configure_resident_app(app, visible=visible)
        return app, True
    if not attach_existing:
        raise ExistingHostRequiresAttach(
            "SOLIDWORKS is already running; close it or restart with "
            "'sw-cli daemon start --attach-existing'"
        )
    return app, False


def _worker_main(
    request_queue: Any,
    response_queue: Any,
    ready_queue: Any,
    visible: bool,
    startup_timeout_seconds: float,
    attach_existing: bool,
) -> None:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    app = None
    owned_by_daemon = False
    documents = None
    try:
        app, owned_by_daemon = acquire_resident_app(
            win32com.client,
            visible=visible,
            attach_existing=attach_existing,
        )
        waited = wait_windows_host_ready(
            app, timeout_seconds=startup_timeout_seconds
        )
        documents = DocumentRegistry(app)
        ready_queue.put(
            {
                "ok": True,
                "host": _describe_app(
                    app, waited, owned_by_daemon=owned_by_daemon
                ),
            }
        )

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
                    app,
                    str(request["operation"]),
                    dict(request["parameters"]),
                    documents=documents,
                    session_id=str(
                        request.get("session_id") or DEFAULT_SESSION_ID
                    ),
                    document_id=request.get("document_id"),
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
                if owned_by_daemon and _com_value(app, "ActiveDoc") is None:
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
        attach_existing: bool = False,
    ) -> None:
        self.visible = visible
        self.startup_timeout_seconds = startup_timeout_seconds
        self.host_platform = host_platform
        self.attach_existing = attach_existing
        self._context = multiprocessing.get_context("spawn")
        self._lock = threading.Lock()
        self._process: Optional[Any] = None
        self._request_queue: Optional[Any] = None
        self._response_queue: Optional[Any] = None
        self._recovery_required: Optional[Dict[str, str]] = None
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
                self.attach_existing,
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
            raise WorkerStartupError(
                str(error.get("type", "WorkerStartupError")),
                str(error.get("message", "SOLIDWORKS worker failed to start")),
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
        if (
            forced
            and self.host.get("owned_by_daemon")
            and self.host.get("process_id")
        ):
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
            if self._recovery_required is not None:
                return _error_response(
                    request["request_id"],
                    self._recovery_required["code"],
                    self._recovery_required["message"],
                )
            if self._process is None or not self._process.is_alive():
                self._start_worker()
            assert self._request_queue is not None
            assert self._response_queue is not None
            self._request_queue.put(request)
            timeout_seconds = request["timeout_ms"] / 1000.0
            try:
                response = self._response_queue.get(timeout=timeout_seconds)
            except queue.Empty:
                shared_interactive = bool(self.host.get("shared_interactive"))
                self._terminate_worker()
                if shared_interactive:
                    message = (
                        f"operation exceeded {request['timeout_ms']}ms while using an "
                        "attached interactive SOLIDWORKS instance; its state is unknown. "
                        "Inspect SOLIDWORKS, then restart swclid before issuing more commands"
                    )
                    self._recovery_required = {
                        "code": "SharedHostRecoveryRequired",
                        "message": message,
                    }
                else:
                    message = (
                        f"operation exceeded {request['timeout_ms']}ms; worker and owned "
                        "SOLIDWORKS host were terminated"
                    )
                return _error_response(
                    request["request_id"],
                    "WorkerTimeout",
                    message,
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
            "recovery_required": self._recovery_required is not None,
            "recovery_error": self._recovery_required,
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
