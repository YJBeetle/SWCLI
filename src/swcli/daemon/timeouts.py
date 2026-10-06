"""Validate waits before performing network or host-lifecycle side effects."""

import math
import threading


def validate_timeout(value, *, name, margin=0.0):
    message = f"{name} must be positive, finite and within platform timer limits"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(message)
    try:
        seconds = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(message) from exc
    if not math.isfinite(seconds) or not 0 < seconds <= threading.TIMEOUT_MAX - margin:
        raise ValueError(message)
    return seconds
