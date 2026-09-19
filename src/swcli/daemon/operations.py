"""Typed operations executed by the resident COM worker."""

from __future__ import annotations

from typing import Any, Dict

from ..hosts.windows_documents import (
    close_active_windows_document,
    diagnose_active_windows_document,
    export_active_windows_document,
    inspect_active_windows_document,
    open_windows_document,
    rebuild_active_windows_document,
    render_active_windows_document,
)
from ..hosts.windows_parts import create_box_part_windows


OPERATIONS = (
    "document.open",
    "document.inspect",
    "document.close",
    "document.diagnose",
    "document.rebuild",
    "document.render",
    "document.export",
    "part.create-box",
)


def _parameters(
    operation: str, parameters: Dict[str, Any], allowed: set[str], required: set[str]
) -> Dict[str, Any]:
    unexpected = sorted(set(parameters) - allowed)
    if unexpected:
        raise ValueError(
            f"unsupported {operation} parameters: {', '.join(unexpected)}"
        )
    missing = sorted(name for name in required if parameters.get(name) is None)
    if missing:
        raise ValueError(f"{operation} requires {', '.join(missing)}")
    return parameters


def execute_operation(app: Any, operation: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    if operation == "document.open":
        values = _parameters(
            operation,
            parameters,
            {"path", "read_only", "configuration"},
            {"path"},
        )
        return open_windows_document(
            str(values["path"]),
            read_only=bool(values.get("read_only", False)),
            configuration=str(values.get("configuration", "")),
            app=app,
        )
    if operation == "document.inspect":
        values = _parameters(
            operation, parameters, {"detail", "max_features"}, set()
        )
        return inspect_active_windows_document(
            detail=str(values.get("detail", "summary")),
            max_features=int(values.get("max_features", 500)),
            app=app,
        )
    if operation == "document.close":
        values = _parameters(operation, parameters, {"discard"}, set())
        return close_active_windows_document(
            discard=bool(values.get("discard", False)), app=app
        )
    if operation == "document.diagnose":
        values = _parameters(operation, parameters, {"max_features"}, set())
        return diagnose_active_windows_document(
            max_features=int(values.get("max_features", 500)), app=app
        )
    if operation == "document.rebuild":
        values = _parameters(
            operation,
            parameters,
            {"force", "top_only", "max_features"},
            set(),
        )
        return rebuild_active_windows_document(
            force=bool(values.get("force", False)),
            top_only=bool(values.get("top_only", False)),
            max_features=int(values.get("max_features", 500)),
            app=app,
        )
    if operation == "document.render":
        values = _parameters(
            operation,
            parameters,
            {"output", "width", "height", "view", "fit", "overwrite"},
            {"output"},
        )
        return render_active_windows_document(
            str(values["output"]),
            width=int(values.get("width", 1024)),
            height=int(values.get("height", 768)),
            view=str(values.get("view", "current")),
            fit=bool(values.get("fit", True)),
            overwrite=bool(values.get("overwrite", False)),
            app=app,
        )
    if operation == "document.export":
        values = _parameters(
            operation, parameters, {"output", "overwrite"}, {"output"}
        )
        return export_active_windows_document(
            str(values["output"]),
            overwrite=bool(values.get("overwrite", False)),
            app=app,
        )
    if operation == "part.create-box":
        values = _parameters(
            operation,
            parameters,
            {"output", "width_mm", "height_mm", "depth_mm", "overwrite"},
            {"output", "width_mm", "height_mm", "depth_mm"},
        )
        return create_box_part_windows(
            str(values["output"]),
            width_mm=float(values["width_mm"]),
            height_mm=float(values["height_mm"]),
            depth_mm=float(values["depth_mm"]),
            overwrite=bool(values.get("overwrite", False)),
            app=app,
        )
    raise ValueError(f"unsupported operation: {operation}")
