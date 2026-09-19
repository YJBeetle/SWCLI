"""Host discovery and automation adapters."""

from .windows import probe_windows_host, start_windows_host, stop_windows_host

__all__ = ["probe_windows_host", "start_windows_host", "stop_windows_host"]
