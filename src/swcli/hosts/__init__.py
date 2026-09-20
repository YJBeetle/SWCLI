"""Host discovery and automation adapters."""

from .windows import (
    doctor_windows_host,
    wait_windows_host_ready,
)
from .windows_documents import (
    RENDER_VIEWS,
    close_active_windows_document,
    diagnose_active_windows_document,
    export_active_windows_document,
    inspect_active_windows_document,
    open_windows_document,
    render_active_windows_document,
    rebuild_active_windows_document,
)
from .windows_parts import create_box_part_windows

__all__ = [
    "RENDER_VIEWS",
    "close_active_windows_document",
    "create_box_part_windows",
    "diagnose_active_windows_document",
    "export_active_windows_document",
    "inspect_active_windows_document",
    "open_windows_document",
    "doctor_windows_host",
    "render_active_windows_document",
    "rebuild_active_windows_document",
    "wait_windows_host_ready",
]
