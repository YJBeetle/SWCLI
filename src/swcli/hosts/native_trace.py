"""Opt-in, flushed call boundaries on the owning worker thread.

Diagnostics contain correlation/method names, never native argument/result
payloads. Logging failure must not replace a CAD return value or exception.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import json
import os
import sys
import time
from typing import Any, Callable, Iterator, Optional


@dataclass
class _TraceState:
    request_id: str
    operation: str
    sequence: int = 0
    native_calls: bool = True


_STATE: ContextVar[Optional[_TraceState]] = ContextVar("swcli_native_trace", default=None)


def _emit(state: _TraceState, sequence: int, stage: str, call: str,
          phase: str, started: float, error: Optional[BaseException] = None) -> None:
    if not state.native_calls:
        return
    try:
        now = time.monotonic()
        record = {
            "event": "swcli.native-call",
            "request_id": state.request_id,
            "operation": state.operation,
            "worker_pid": os.getpid(),
            "sequence": sequence,
            "stage": stage,
            "call": call,
            "phase": phase,
            "monotonic_seconds": now,
        }
        if phase != "begin":
            record["duration_ms"] = max(0.0, (now - started) * 1000)
        if error is not None:
            record["exception_type"] = type(error).__name__
        sys.stderr.write(json.dumps(record, ensure_ascii=True, allow_nan=False) + "\n")
        sys.stderr.flush()
    except Exception:
        # Diagnostics are best-effort, not a second native failure mechanism.
        pass


def native_call(stage: str, call: str, function: Callable[[], Any]) -> Any:
    state = _STATE.get()
    if state is None:
        return function()
    state.sequence += 1
    sequence = state.sequence
    started = time.monotonic()
    _emit(state, sequence, stage, call, "begin", started)
    try:
        result = function()
    except BaseException as exc:
        _emit(state, sequence, stage, call, "error", started, exc)
        raise
    _emit(state, sequence, stage, call, "end", started)
    if (stage == "read" and call == "GetDefinition" and
            os.environ.get("SWCLI_TRACE_DEFINITION_INTERFACES") == "1"):
        try:
            from .windows_definition_identity import record_definition_identity
            record_definition_identity(result, request_id=state.request_id,
                                       operation=state.operation, sequence=sequence)
        except Exception:
            pass  # Observation must never replace the original native result.
    if state.native_calls and stage == "dimension-observation" and call == "IDimension.GetSystemValue3":
        try:
            # Shape only, from this original return; never re-invoke the getter
            # or log native dimension/configuration values.
            record = {"event": "swcli.native-return-shape", "request_id": state.request_id,
                      "operation": state.operation, "sequence": sequence, "worker_pid": os.getpid(),
                      "call": call, "return_type": type(result).__name__,
                      "container_length": len(result) if isinstance(result, (tuple, list)) else None}
            sys.stderr.write(json.dumps(record, ensure_ascii=True, allow_nan=False) + "\n")
            sys.stderr.flush()
        except Exception:
            pass
    return result


def current_request_context() -> dict:
    """Read correlation metadata for an opt-in diagnostic on this worker."""
    state = _STATE.get()
    return {"request_id": state.request_id if state is not None else None,
            "operation": state.operation if state is not None else None}


@contextmanager
def trace_native_request(request_id: str, operation: str) -> Iterator[None]:
    """Enable only for this request when the daemon inherits the exact toggle."""
    native_calls = os.environ.get("SWCLI_TRACE_NATIVE_CALLS") == "1"
    if not native_calls and os.environ.get("SWCLI_TRACE_DEFINITION_INTERFACES") != "1":
        yield
        return
    state = _TraceState(request_id, operation, native_calls=native_calls)
    token = _STATE.set(state)
    started = time.monotonic()
    _emit(state, 0, "operation", operation, "begin", started)
    try:
        yield
    except BaseException as exc:
        _emit(state, 0, "operation", operation, "error", started, exc)
        raise
    else:
        _emit(state, 0, "operation", operation, "end", started)
    finally:
        _STATE.reset(token)
