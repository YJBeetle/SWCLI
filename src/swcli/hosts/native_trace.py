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


_STATE: ContextVar[Optional[_TraceState]] = ContextVar("swcli_native_trace", default=None)


def _emit(state: _TraceState, sequence: int, stage: str, call: str,
          phase: str, started: float, error: Optional[BaseException] = None) -> None:
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
    return result


@contextmanager
def trace_native_request(request_id: str, operation: str) -> Iterator[None]:
    """Enable only for this request when the daemon inherits the exact toggle."""
    if os.environ.get("SWCLI_TRACE_NATIVE_CALLS") != "1":
        yield
        return
    state = _TraceState(request_id, operation)
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
