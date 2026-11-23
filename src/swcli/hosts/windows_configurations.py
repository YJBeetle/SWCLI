"""Read the current configuration through the SOLIDWORKS configuration manager.

No configuration activation, legacy API fallback, or binding retry is allowed.
"""
from typing import Any, Optional
from .windows import _com_value


def active_configuration_name(document: Any, *, allow_absent: bool = False) -> Optional[str]:
    manager = _com_value(document, "ConfigurationManager")
    active = _com_value(manager, "ActiveConfiguration") if manager is not None else None
    if active is None:
        if allow_absent:
            return None
        raise RuntimeError("native active configuration is unavailable")
    name = _com_value(active, "Name")
    if not isinstance(name, str) or not name.strip():
        raise RuntimeError("native active configuration name is unreadable")
    return name
