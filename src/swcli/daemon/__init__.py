"""Resident SWCLI service and local protocol client."""

from .client import DEFAULT_ENDPOINT, call_daemon
from .main import main

__all__ = ["DEFAULT_ENDPOINT", "call_daemon", "main"]
