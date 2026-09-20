"""Typed operations executed by the resident COM worker."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..hosts.windows_documents import (
    open_windows_document_with_handle,
    close_active_windows_document,
    diagnose_active_windows_document,
    export_active_windows_document,
    inspect_active_windows_document,
    rebuild_active_windows_document,
    render_active_windows_document,
    save_active_windows_document,
)
from ..hosts.windows_parts import create_box_part_windows_with_handle
from .documents import DEFAULT_SESSION_ID, DocumentEntry, DocumentRegistry


OPERATIONS = (
    "document.open",
    "document.list",
    "document.use",
    "document.inspect",
    "document.close",
    "document.save",
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


def _with_document(
    result: Dict[str, Any],
    documents: DocumentRegistry,
    entry: DocumentEntry,
    *,
    session_id: str,
    descriptor: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if descriptor is None:
        descriptor = documents.describe(entry, session_id=session_id)
    if isinstance(result.get("document"), dict):
        result["document"].update(
            {
                "document_id": descriptor["document_id"],
                "current": descriptor["current"],
                "active": descriptor["active"],
            }
        )
    else:
        result["document"] = descriptor
    result["session_id"] = session_id
    return result


def execute_operation(
    app: Any,
    operation: str,
    parameters: Dict[str, Any],
    *,
    documents: Optional[DocumentRegistry] = None,
    session_id: str = DEFAULT_SESSION_ID,
    document_id: Optional[str] = None,
) -> Dict[str, Any]:
    if operation == "document.open":
        values = _parameters(
            operation,
            parameters,
            {"path", "read_only", "configuration"},
            {"path"},
        )
        result, opened_document = open_windows_document_with_handle(
            str(values["path"]),
            read_only=bool(values.get("read_only", False)),
            configuration=str(values.get("configuration", "")),
            app=app,
        )
        if documents is not None and result.get("ok"):
            if opened_document is None:
                raise RuntimeError(
                    "SOLIDWORKS returned no document after a successful open"
                )
            entry = documents.register(opened_document)
            documents.set_current(entry, session_id=session_id)
            return _with_document(result, documents, entry, session_id=session_id)
        return result
    if operation == "document.list":
        _parameters(operation, parameters, set(), set())
        if documents is None:
            raise RuntimeError("document registry is unavailable")
        return documents.list(session_id=session_id)
    if operation == "document.use":
        _parameters(operation, parameters, set(), set())
        if documents is None:
            raise RuntimeError("document registry is unavailable")
        if document_id is None:
            raise ValueError("document.use requires document_id")
        entry = documents.use(document_id, session_id=session_id)
        return {
            "ok": True,
            "action": "document.use",
            "session_id": session_id,
            "document": documents.describe(entry, session_id=session_id),
        }

    entry = None
    if operation.startswith("document.") and documents is not None:
        entry = documents.resolve(document_id, session_id=session_id)

    if operation == "document.inspect":
        values = _parameters(
            operation, parameters, {"detail", "max_features"}, set()
        )
        result = inspect_active_windows_document(
            detail=str(values.get("detail", "summary")),
            max_features=int(values.get("max_features", 500)),
            app=app,
            document=entry.document if entry is not None else None,
        )
        return (
            _with_document(result, documents, entry, session_id=session_id)
            if documents is not None and entry is not None
            else result
        )
    if operation == "document.close":
        values = _parameters(operation, parameters, {"discard"}, set())
        descriptor = (
            documents.describe(entry, session_id=session_id)
            if documents is not None and entry is not None
            else None
        )
        result = close_active_windows_document(
            discard=bool(values.get("discard", False)),
            app=app,
            document=entry.document if entry is not None else None,
        )
        if documents is not None and entry is not None:
            if result.get("ok") and descriptor is not None:
                descriptor = dict(descriptor)
                descriptor.update({"active": False, "current": False})
            result = _with_document(
                result,
                documents,
                entry,
                session_id=session_id,
                descriptor=descriptor,
            )
            if result.get("ok"):
                documents.forget(entry.document_id)
        return result
    if operation == "document.save":
        _parameters(operation, parameters, set(), set())
        result = save_active_windows_document(
            app=app, document=entry.document if entry is not None else None
        )
        return (
            _with_document(result, documents, entry, session_id=session_id)
            if documents is not None and entry is not None
            else result
        )
    if operation == "document.diagnose":
        values = _parameters(operation, parameters, {"max_features"}, set())
        result = diagnose_active_windows_document(
            max_features=int(values.get("max_features", 500)),
            app=app,
            document=entry.document if entry is not None else None,
        )
        return (
            _with_document(result, documents, entry, session_id=session_id)
            if documents is not None and entry is not None
            else result
        )
    if operation == "document.rebuild":
        values = _parameters(
            operation,
            parameters,
            {"force", "top_only", "max_features"},
            set(),
        )
        result = rebuild_active_windows_document(
            force=bool(values.get("force", False)),
            top_only=bool(values.get("top_only", False)),
            max_features=int(values.get("max_features", 500)),
            app=app,
            document=entry.document if entry is not None else None,
        )
        return (
            _with_document(result, documents, entry, session_id=session_id)
            if documents is not None and entry is not None
            else result
        )
    if operation == "document.render":
        values = _parameters(
            operation,
            parameters,
            {"output", "width", "height", "view", "fit", "overwrite"},
            {"output"},
        )
        kwargs = {
            "width": int(values.get("width", 1024)),
            "height": int(values.get("height", 768)),
            "view": str(values.get("view", "current")),
            "fit": bool(values.get("fit", True)),
            "overwrite": bool(values.get("overwrite", False)),
            "app": app,
            "document": entry.document if entry is not None else None,
        }
        if documents is not None and entry is not None:
            with documents.temporarily_activate(entry):
                result = render_active_windows_document(
                    str(values["output"]), **kwargs
                )
            return _with_document(
                result, documents, entry, session_id=session_id
            )
        return render_active_windows_document(str(values["output"]), **kwargs)
    if operation == "document.export":
        values = _parameters(
            operation,
            parameters,
            {"output", "overwrite", "strict"},
            {"output"},
        )
        kwargs = {
            "overwrite": bool(values.get("overwrite", False)),
            "strict": bool(values.get("strict", False)),
            "app": app,
            "document": entry.document if entry is not None else None,
        }
        if documents is not None and entry is not None:
            with documents.temporarily_activate(entry):
                result = export_active_windows_document(
                    str(values["output"]), **kwargs
                )
            return _with_document(
                result, documents, entry, session_id=session_id
            )
        return export_active_windows_document(str(values["output"]), **kwargs)
    if operation == "part.create-box":
        values = _parameters(
            operation,
            parameters,
            {
                "output",
                "width_mm",
                "height_mm",
                "depth_mm",
                "template",
                "overwrite",
            },
            {"output", "width_mm", "height_mm", "depth_mm"},
        )
        result, created_document = create_box_part_windows_with_handle(
            str(values["output"]),
            width_mm=float(values["width_mm"]),
            height_mm=float(values["height_mm"]),
            depth_mm=float(values["depth_mm"]),
            template=(
                str(values["template"]) if values.get("template") is not None else None
            ),
            overwrite=bool(values.get("overwrite", False)),
            app=app,
        )
        if documents is not None and result.get("ok"):
            if created_document is None:
                raise RuntimeError(
                    "SOLIDWORKS returned no document after creating a part"
                )
            entry = documents.register(created_document)
            documents.set_current(entry, session_id=session_id)
            return _with_document(result, documents, entry, session_id=session_id)
        return result
    raise ValueError(f"unsupported operation: {operation}")
