"""Helpers for accessing the versioned SWCLI protocol schemas."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, Dict

from . import PROTOCOL_VERSION


SCHEMA_NAMES = ("request", "response", "capabilities")


def load_schema(name: str, version: str = PROTOCOL_VERSION) -> Dict[str, Any]:
    if name not in SCHEMA_NAMES:
        raise ValueError(f"unknown schema: {name}")
    if version != PROTOCOL_VERSION:
        raise ValueError(f"unsupported protocol version: {version}")

    schema_path = resources.files("swcli").joinpath(
        "schemas", "v1", f"{name}.schema.json"
    )
    return json.loads(schema_path.read_text(encoding="utf-8"))
