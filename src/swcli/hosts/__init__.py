"""Host discovery and automation adapters."""

from .windows import probe_windows_host, start_windows_host, stop_windows_host
from .windows_documents import (
    close_active_windows_document,
    diagnose_active_windows_document,
    inspect_active_windows_document,
    open_windows_document,
    render_active_windows_document,
    rebuild_active_windows_document,
)
from .windows_parts import create_box_part_windows

__all__ = [
    "close_active_windows_document",
    "create_box_part_windows",
    "diagnose_active_windows_document",
    "inspect_active_windows_document",
    "open_windows_document",
    "probe_windows_host",
    "render_active_windows_document",
    "rebuild_active_windows_document",
    "start_windows_host",
    "stop_windows_host",
]
