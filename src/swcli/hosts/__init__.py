"""Host discovery and automation adapters."""

from .windows import probe_windows_host, start_windows_host, stop_windows_host
from .windows_documents import (
    inspect_active_windows_document,
    open_windows_document,
)

__all__ = [
    "inspect_active_windows_document",
    "open_windows_document",
    "probe_windows_host",
    "start_windows_host",
    "stop_windows_host",
]
