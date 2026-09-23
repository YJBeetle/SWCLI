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
from collections import OrderedDict
from copy import deepcopy
from typing import Any, Callable, Dict, Optional

from .. import PROTOCOL_VERSION, __version__
from ..hosts.windows import PROG_ID, _com_value, wait_windows_host_ready
from ..operation_schemas import operation_schemas, validate_operation_request
from .documents import DEFAULT_SESSION_ID, DocumentRegistry
from .operations import (
    LEASE_TOKEN_OPERATIONS,
    OPERATIONS,
    UPDATE_STAMP_OPERATIONS,
    execute_operation,
)


MAX_REQUEST_BYTES = 16 * 1024 * 1024
REQUEST_REPLAY_MAX_ENTRIES = 1024
REQUEST_REPLAY_MAX_BYTES = 64 * 1024 * 1024
HOST_PROBE_INTERVAL_SECONDS = 1.0
HOST_PROBE_FAILURE_LIMIT = 3
TRANSIENT_COM_HRESULTS = {
    0x80010001,  # RPC_E_CALL_REJECTED
    0x8001010A,  # RPC_E_SERVERCALL_RETRYLATER
    0x8001010B,  # RPC_E_SERVERCALL_REJECTED
}
DISCONNECTED_COM_HRESULTS = {
    0x800401FD,  # CO_E_OBJNOTCONNECTED
    0x80010108,  # RPC_E_DISCONNECTED
    0x800706BA,  # HRESULT_FROM_WIN32(RPC_S_SERVER_UNAVAILABLE)
}
DOCUMENT_ID_PATTERN = re.compile(r"^d-[0-9a-hjkmnp-tv-z]{6}$")
LEASE_ID_PATTERN = re.compile(r"^l-[0-9a-hjkmnp-tv-z]{12}$")


class ExistingHostRequiresAttach(RuntimeError):
    """Raised when exclusive startup finds a user-controlled SOLIDWORKS host."""


class ExistingHostNotFound(RuntimeError):
    """Raised when explicit attach was requested but no active host exists."""


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
    allowed_fields = {
        "api_version",
        "request_id",
        "session_id",
        "document_id",
        "expected_update_stamp",
        "lease_id",
        "operation",
        "parameters",
        "timeout_ms",
    }
    unexpected = sorted(set(request) - allowed_fields)
    if unexpected:
        raise ValueError(f"unsupported request fields: {', '.join(unexpected)}")
    for name in ("request_id", "operation"):
        if not isinstance(request.get(name), str) or not request[name]:
            raise ValueError(f"{name} must be a non-empty string")
    if len(request["request_id"]) > 128:
        raise ValueError("request_id must not exceed 128 characters")
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
    expected_update_stamp = request.get("expected_update_stamp")
    if expected_update_stamp is not None and (
        not isinstance(expected_update_stamp, int)
        or isinstance(expected_update_stamp, bool)
    ):
        raise ValueError("expected_update_stamp must be an integer when provided")
    if (
        expected_update_stamp is not None
        and request["operation"] not in UPDATE_STAMP_OPERATIONS
    ):
        raise ValueError(
            "expected_update_stamp is not supported for "
            f"{request['operation']}"
        )
    lease_id = request.get("lease_id")
    if lease_id is not None and (
        not isinstance(lease_id, str)
        or LEASE_ID_PATTERN.fullmatch(lease_id) is None
    ):
        raise ValueError("lease_id must be an l-... lease token")
    if lease_id is not None and request["operation"] not in LEASE_TOKEN_OPERATIONS:
        raise ValueError(f"lease_id is not supported for {request['operation']}")
    timeout_ms = request.get("timeout_ms", 600000)
    if not isinstance(timeout_ms, int) or timeout_ms < 1:
        raise ValueError("timeout_ms must be a positive integer")
    request["timeout_ms"] = timeout_ms
    validate_operation_request(
        request["operation"],
        request["parameters"],
        document_id=document_id,
        expected_update_stamp=expected_update_stamp,
        lease_id=lease_id,
    )
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
        if attach_existing:
            raise ExistingHostNotFound(
                "--attach-existing requires an already running SOLIDWORKS instance"
            )
        app = com_client.DispatchEx(PROG_ID)
        configure_resident_app(app, visible=visible)
        return app, True
    if not attach_existing:
        raise ExistingHostRequiresAttach(
            "SOLIDWORKS is already running; close it or restart with "
            "'sw-cli daemon start --attach-existing'"
        )
    return app, False


def _host_disconnected_error(exc: BaseException) -> Dict[str, str]:
    return {
        "code": "HostDisconnected",
        "message": f"SOLIDWORKS COM host is no longer available: {exc}",
    }


def _com_hresult(exc: BaseException) -> Optional[int]:
    """Return an unsigned HRESULT from pywin32 or a compatible exception."""

    value = getattr(exc, "hresult", None)
    if not isinstance(value, int) and exc.args and isinstance(exc.args[0], int):
        value = exc.args[0]
    if not isinstance(value, int):
        return None
    return value & 0xFFFFFFFF


def _wait_for_worker_request(
    request_queue: Any,
    lifecycle_queue: Any,
    app: Any,
    *,
    probe_interval_seconds: float = HOST_PROBE_INTERVAL_SECONDS,
    failure_limit: int = HOST_PROBE_FAILURE_LIMIT,
) -> Any:
    """Wait for work while probing COM from the worker's owning STA thread."""

    consecutive_failures = 0
    while True:
        try:
            return request_queue.get(timeout=probe_interval_seconds)
        except queue.Empty:
            try:
                _com_value(app, "RevisionNumber")
            except Exception as exc:
                hresult = _com_hresult(exc)
                if hresult in TRANSIENT_COM_HRESULTS:
                    consecutive_failures = 0
                    continue
                consecutive_failures += 1
                if (
                    hresult not in DISCONNECTED_COM_HRESULTS
                    and consecutive_failures < failure_limit
                ):
                    continue
                lifecycle_queue.put(
                    {
                        "event": "host-disconnected",
                        "error": _host_disconnected_error(exc),
                    }
                )
                return None
            else:
                consecutive_failures = 0


def _worker_main(
    request_queue: Any,
    response_queue: Any,
    lifecycle_queue: Any,
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
        lifecycle_queue.put(
            {
                "ok": True,
                "phase": "host-acquired",
                "host": {
                    "process_id": int(_com_value(app, "GetProcessID")),
                    "owned_by_daemon": owned_by_daemon,
                },
            }
        )
        waited = wait_windows_host_ready(
            app, timeout_seconds=startup_timeout_seconds
        )
        documents = DocumentRegistry(app)
        lifecycle_queue.put(
            {
                "ok": True,
                "phase": "ready",
                "host": _describe_app(
                    app, waited, owned_by_daemon=owned_by_daemon
                ),
            }
        )

        while True:
            request = _wait_for_worker_request(
                request_queue, lifecycle_queue, app
            )
            if request is None:
                break
            started_at = time.monotonic()
            request_id = str(request["request_id"])
            try:
                try:
                    _com_value(app, "RevisionNumber")
                except Exception as exc:
                    error = _host_disconnected_error(exc)
                    response_queue.put(
                        _error_response(
                            request_id,
                            error["code"],
                            error["message"],
                        )
                    )
                    lifecycle_queue.put(
                        {"event": "host-disconnected", "error": error}
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
                    expected_update_stamp=request.get("expected_update_stamp"),
                    lease_id=request.get("lease_id"),
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
        lifecycle_queue.put(
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
        startup_reporter: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.visible = visible
        self.startup_timeout_seconds = startup_timeout_seconds
        self.host_platform = host_platform
        self.attach_existing = attach_existing
        self.startup_reporter = startup_reporter
        self._context = multiprocessing.get_context("spawn")
        self._lock = threading.Lock()
        self._process: Optional[Any] = None
        self._request_queue: Optional[Any] = None
        self._response_queue: Optional[Any] = None
        self._lifecycle_queue: Optional[Any] = None
        self._request_cache: OrderedDict[
            str, tuple[str, Dict[str, Any], int]
        ] = OrderedDict()
        self._request_cache_bytes = 0
        self._recovery_required: Optional[Dict[str, str]] = None
        self.host: Dict[str, Any] = {}
        self._start_worker()

    def _start_worker(self) -> None:
        self._request_queue = self._context.Queue()
        self._response_queue = self._context.Queue()
        self._lifecycle_queue = self._context.Queue()
        self._process = self._context.Process(
            target=_worker_main,
            args=(
                self._request_queue,
                self._response_queue,
                self._lifecycle_queue,
                self.visible,
                self.startup_timeout_seconds,
                self.attach_existing,
            ),
            name="swclid-com-worker",
        )
        self._process.start()
        deadline = time.monotonic() + self.startup_timeout_seconds + 5.0
        while True:
            try:
                ready = self._lifecycle_queue.get(
                    timeout=max(0.0, deadline - time.monotonic())
                )
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
            if ready.get("phase") == "host-acquired":
                if self.startup_reporter is not None:
                    self.startup_reporter(dict(self.host))
                continue
            if ready.get("phase") == "ready":
                return
            self._terminate_worker()
            raise WorkerStartupError(
                "InvalidStartupEvent",
                "SOLIDWORKS worker returned an unknown startup phase",
            )

    def _refresh_worker_state_locked(self) -> None:
        latest_disconnect: Optional[Dict[str, str]] = None
        lifecycle_queue = getattr(self, "_lifecycle_queue", None)
        if lifecycle_queue is not None:
            while True:
                try:
                    event = lifecycle_queue.get_nowait()
                except queue.Empty:
                    break
                if event.get("event") == "host-disconnected":
                    error = event.get("error") or {}
                    latest_disconnect = {
                        "code": str(error.get("code", "HostDisconnected")),
                        "message": str(
                            error.get(
                                "message", "SOLIDWORKS COM host disconnected"
                            )
                        ),
                    }
        if latest_disconnect is not None:
            self._recovery_required = latest_disconnect
            self.host = {}

        if self._process is not None and not self._process.is_alive():
            self._process.join(timeout=0.0)
            self._process = None
            self.host = {}
            if self._recovery_required is None:
                self._recovery_required = {
                    "code": "WorkerExited",
                    "message": (
                        "SOLIDWORKS COM worker exited unexpectedly; restart swclid "
                        "before issuing more commands"
                    ),
                }

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
            self._refresh_worker_state_locked()
            replay = self._replay_response(request)
            if replay is not None:
                return replay
            if self._recovery_required is not None:
                response = _error_response(
                    request["request_id"],
                    self._recovery_required["code"],
                    self._recovery_required["message"],
                )
                self._remember_response(request, response)
                return response
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
                response = _error_response(
                    request["request_id"],
                    "WorkerTimeout",
                    message,
                    duration_ms=float(request["timeout_ms"]),
                )
                self._remember_response(request, response)
                return response
            if (response.get("error") or {}).get("code") == "HostDisconnected":
                error = response["error"]
                self._recovery_required = {
                    "code": str(error["code"]),
                    "message": str(error["message"]),
                }
                self._process.join(timeout=5.0)
                if self._process.is_alive():
                    self._terminate_worker()
                else:
                    self._process = None
                    self.host = {}
            self._remember_response(request, response)
            return response

    @staticmethod
    def _request_fingerprint(request: Dict[str, Any]) -> str:
        semantic_request = {
            key: value
            for key, value in request.items()
            if key not in {"request_id", "timeout_ms"}
        }
        return json.dumps(
            semantic_request,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def _replay_response(
        self, request: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        cache = getattr(self, "_request_cache", None)
        if cache is None:
            cache = OrderedDict()
            self._request_cache = cache
        request_id = request["request_id"]
        cached = cache.get(request_id)
        if cached is None:
            return None
        fingerprint, response, _ = cached
        cache.move_to_end(request_id)
        if fingerprint != self._request_fingerprint(request):
            return _error_response(
                request_id,
                "RequestIdConflict",
                "request_id was already used for a different request",
            )
        replay = deepcopy(response)
        replay["replayed"] = True
        return replay

    def _remember_response(
        self, request: Dict[str, Any], response: Dict[str, Any]
    ) -> None:
        cache = getattr(self, "_request_cache", None)
        if cache is None:
            cache = OrderedDict()
            self._request_cache = cache
        request_id = request["request_id"]
        previous = cache.pop(request_id, None)
        if previous is not None:
            self._request_cache_bytes = max(
                0,
                getattr(self, "_request_cache_bytes", 0) - previous[2],
            )
        response_copy = deepcopy(response)
        response_size = len(
            json.dumps(
                response_copy,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if response_size > REQUEST_REPLAY_MAX_BYTES:
            return
        cache[request_id] = (
            self._request_fingerprint(request),
            response_copy,
            response_size,
        )
        self._request_cache_bytes = (
            getattr(self, "_request_cache_bytes", 0) + response_size
        )
        cache.move_to_end(request_id)
        while (
            len(cache) > REQUEST_REPLAY_MAX_ENTRIES
            or self._request_cache_bytes > REQUEST_REPLAY_MAX_BYTES
        ):
            _, (_, _, evicted_size) = cache.popitem(last=False)
            self._request_cache_bytes -= evicted_size

    def health(self) -> Dict[str, Any]:
        acquired = self._lock.acquire(blocking=False)
        try:
            if acquired:
                self._refresh_worker_state_locked()
            worker_alive = bool(
                self._process is not None and self._process.is_alive()
            )
            recovery_error = self._recovery_required
            host = dict(self.host) if self.host else None
        finally:
            if acquired:
                self._lock.release()

        host_connected = bool(
            worker_alive and host and recovery_error is None
        )
        return {
            "server_version": __version__,
            "protocol_versions": [PROTOCOL_VERSION],
            "operations": list(OPERATIONS),
            "operation_schemas": operation_schemas(),
            "request_replay": {
                "supported": True,
                "max_entries": REQUEST_REPLAY_MAX_ENTRIES,
                "max_bytes": REQUEST_REPLAY_MAX_BYTES,
                "scope": "daemon",
            },
            "worker_alive": worker_alive,
            "host_connected": host_connected,
            "recovery_required": recovery_error is not None,
            "recovery_error": recovery_error,
            "host": host,
        }

    def shutdown(self, request: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._refresh_worker_state_locked()
            if self._process is None:
                return _success_response(
                    request["request_id"],
                    {
                        "stopping": True,
                        "host_already_disconnected": self._recovery_required
                        is not None,
                    },
                )
            assert self._request_queue is not None
            assert self._response_queue is not None
            control = dict(request)
            control["operation"] = "__daemon.shutdown__"
            self._request_queue.put(control)
            deadline = time.monotonic() + 15.0
            while True:
                try:
                    response = self._response_queue.get(
                        timeout=min(0.25, max(0.0, deadline - time.monotonic()))
                    )
                    break
                except queue.Empty:
                    self._refresh_worker_state_locked()
                    if self._process is None:
                        return _success_response(
                            request["request_id"],
                            {
                                "stopping": True,
                                "host_already_disconnected": True,
                            },
                        )
                    if time.monotonic() >= deadline:
                        return _error_response(
                            request["request_id"],
                            "ShutdownTimeout",
                            "COM worker did not stop within 15 seconds",
                        )
            if (response.get("error") or {}).get("code") == "HostDisconnected":
                self._recovery_required = dict(response["error"])
                self._process.join(timeout=5.0)
                if self._process.is_alive():
                    self._terminate_worker()
                else:
                    self._process = None
                    self.host = {}
                return _success_response(
                    request["request_id"],
                    {"stopping": True, "host_already_disconnected": True},
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
            payload = json.loads(raw.decode("utf-8"))
            if isinstance(payload, dict):
                candidate_request_id = payload.get("request_id")
                if (
                    isinstance(candidate_request_id, str)
                    and candidate_request_id
                    and len(candidate_request_id) <= 128
                ):
                    request_id = candidate_request_id
            request = validate_request(payload)
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
