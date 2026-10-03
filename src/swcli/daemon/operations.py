"""Typed operations executed by the resident COM worker."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..operation_schemas import (
    OPERATIONS,
    OPERATION_SCHEMAS,
    OPERATION_CATALOG,
    validate_operation_request,
)
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
from .documents import (
    DEFAULT_SESSION_ID,
    DocumentEntry,
    DocumentRegistry,
)


LEASE_GUARDED_OPERATIONS = frozenset(
    name for name, spec in OPERATION_CATALOG.items() if spec.lease_guarded
)
LEASE_TOKEN_OPERATIONS = frozenset(
    name for name, schema in OPERATION_SCHEMAS.items()
    if schema["x-swcli-context"]["lease_id"] != "forbidden"
)
UPDATE_STAMP_OPERATIONS = frozenset(
    name for name, schema in OPERATION_SCHEMAS.items()
    if schema["x-swcli-context"]["expected_update_stamp"] != "forbidden"
)


class DocumentUpdateConflict(RuntimeError):
    """The selected document changed after the caller last observed it."""


class DocumentUpdateStampUnavailable(RuntimeError):
    """The selected host cannot provide a native document update stamp."""


def _lease_ttl(parameters: Dict[str, Any]) -> float:
    value = parameters.get("ttl_seconds", 60)
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not 1 <= value <= 3600
    ):
        raise ValueError("ttl_seconds must be between 1 and 3600")
    return float(value)


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


@dataclass
class OperationContext:
    app: Any
    operation: str
    documents: Optional[DocumentRegistry]
    session_id: str
    document_id: Optional[str]
    lease_id: Optional[str]
    entry: Optional[DocumentEntry] = None


_HANDLERS = {}


def _register_handler(handler):
    if handler.__name__ in _HANDLERS:
        raise RuntimeError(f"duplicate operation handler: {handler.__name__}")
    _HANDLERS[handler.__name__] = handler
    return handler


@_register_handler
def document_open(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    result, opened_document = open_windows_document_with_handle(
        str(values["path"]),
        read_only=bool(values.get("read_only", False)),
        configuration=str(values.get("configuration", "")),
        app=context.app,
    )
    if context.documents is not None and result.get("ok"):
        if opened_document is None:
            raise RuntimeError(
                "SOLIDWORKS returned no document after a successful open"
            )
        context.entry = context.documents.register(opened_document)
        context.documents.set_current(context.entry, session_id=context.session_id)
        return _with_document(result, context.documents, context.entry, session_id=context.session_id)
    return result


@_register_handler
def document_list(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    if context.documents is None:
        raise RuntimeError("document registry is unavailable")
    return context.documents.list(session_id=context.session_id)


@_register_handler
def document_use(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    if context.documents is None:
        raise RuntimeError("document registry is unavailable")
    if context.document_id is None:
        raise ValueError("document.use requires document_id")
    context.entry = context.documents.use(context.document_id, session_id=context.session_id)
    return {
        "ok": True,
        "action": "document.use",
        "session_id": context.session_id,
        "document": context.documents.describe(context.entry, session_id=context.session_id),
    }


@_register_handler
def document_lease_renew(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    if context.documents is None:
        raise RuntimeError("document registry is unavailable")
    if context.lease_id is None:
        raise ValueError("document.lease.renew requires lease_id")
    lease = context.documents.renew_lease(
        context.lease_id,
        session_id=context.session_id,
        ttl_seconds=_lease_ttl(values),
    )
    return {
        "ok": True,
        "action": context.operation,
        "session_id": context.session_id,
        "lease": lease,
    }


@_register_handler
def document_lease_release(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    if context.documents is None:
        raise RuntimeError("document registry is unavailable")
    if context.lease_id is None:
        raise ValueError("document.lease.release requires lease_id")
    lease = context.documents.release_lease(context.lease_id, session_id=context.session_id)
    return {
        "ok": True,
        "action": context.operation,
        "session_id": context.session_id,
        "released": True,
        "lease": lease,
    }


@_register_handler
def document_lease_acquire(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    lease = context.documents.acquire_lease(
        context.entry,
        session_id=context.session_id,
        ttl_seconds=_lease_ttl(values),
    )
    return {
        "ok": True,
        "action": context.operation,
        "session_id": context.session_id,
        "lease": lease,
        "document": context.documents.describe(context.entry, session_id=context.session_id),
    }


@_register_handler
def document_lease_status(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    if context.documents is None or context.entry is None:
        raise RuntimeError("document registry is unavailable")
    lease = context.documents.active_lease(context.entry)
    if lease is not None and lease["session_id"] != context.session_id:
        lease = {key: value for key, value in lease.items() if key != "lease_id"}
    return {
        "ok": True,
        "action": context.operation,
        "session_id": context.session_id,
        "leased": lease is not None,
        "owned_by_session": lease is not None
        and lease["session_id"] == context.session_id,
        "lease": lease,
        "document": context.documents.describe(context.entry, session_id=context.session_id),
    }


@_register_handler
def document_inspect(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    result = inspect_active_windows_document(
        detail=str(values.get("detail", "summary")),
        max_features=int(values.get("max_features", 500)),
        app=context.app,
        document=context.entry.document if context.entry is not None else None,
    )
    return (
        _with_document(result, context.documents, context.entry, session_id=context.session_id)
        if context.documents is not None and context.entry is not None
        else result
    )


@_register_handler
def document_close(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    descriptor = (
        context.documents.describe(context.entry, session_id=context.session_id)
        if context.documents is not None and context.entry is not None
        else None
    )
    result = close_active_windows_document(
        discard=bool(values.get("discard", False)),
        app=context.app,
        document=context.entry.document if context.entry is not None else None,
    )
    if context.documents is not None and context.entry is not None:
        if result.get("ok") and descriptor is not None:
            descriptor = dict(descriptor)
            descriptor.update({"active": False, "current": False})
        result = _with_document(
            result,
            context.documents,
            context.entry,
            session_id=context.session_id,
            descriptor=descriptor,
        )
        if result.get("ok"):
            context.documents.forget(context.entry.document_id)
    return result


@_register_handler
def document_save(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    result = save_active_windows_document(
        app=context.app, document=context.entry.document if context.entry is not None else None
    )
    return (
        _with_document(result, context.documents, context.entry, session_id=context.session_id)
        if context.documents is not None and context.entry is not None
        else result
    )


@_register_handler
def document_diagnose(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    result = diagnose_active_windows_document(
        max_features=int(values.get("max_features", 500)),
        app=context.app,
        document=context.entry.document if context.entry is not None else None,
    )
    return (
        _with_document(result, context.documents, context.entry, session_id=context.session_id)
        if context.documents is not None and context.entry is not None
        else result
    )


@_register_handler
def document_rebuild(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    result = rebuild_active_windows_document(
        force=bool(values.get("force", False)),
        top_only=bool(values.get("top_only", False)),
        max_features=int(values.get("max_features", 500)),
        app=context.app,
        document=context.entry.document if context.entry is not None else None,
    )
    return (
        _with_document(result, context.documents, context.entry, session_id=context.session_id)
        if context.documents is not None and context.entry is not None
        else result
    )


@_register_handler
def document_render(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    kwargs = {
        "width": int(values.get("width", 1024)),
        "height": int(values.get("height", 768)),
        "view": str(values.get("view", "current")),
        "fit": bool(values.get("fit", True)),
        "overwrite": bool(values.get("overwrite", False)),
        "app": context.app,
        "document": context.entry.document if context.entry is not None else None,
    }
    return render_active_windows_document(str(values["output"]), **kwargs)


@_register_handler
def document_export(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    kwargs = {
        "overwrite": bool(values.get("overwrite", False)),
        "strict": bool(values.get("strict", False)),
        "app": context.app,
        "document": context.entry.document if context.entry is not None else None,
    }
    return export_active_windows_document(str(values["output"]), **kwargs)


@_register_handler
def part_create_box(context: OperationContext, values: Dict[str, Any]) -> Dict[str, Any]:
    result, created_document = create_box_part_windows_with_handle(
        str(values["output"]),
        width_mm=float(values["width_mm"]),
        height_mm=float(values["height_mm"]),
        depth_mm=float(values["depth_mm"]),
        template=(
            str(values["template"]) if values.get("template") is not None else None
        ),
        overwrite=bool(values.get("overwrite", False)),
        app=context.app,
    )
    if context.documents is not None and result.get("ok"):
        if created_document is None:
            raise RuntimeError(
                "SOLIDWORKS returned no document after creating a part"
            )
        context.entry = context.documents.register(created_document)
        context.documents.set_current(context.entry, session_id=context.session_id)
        return _with_document(result, context.documents, context.entry, session_id=context.session_id)
    return result


_expected_handlers = {
    spec.handler for spec in OPERATION_CATALOG.values() if spec.handler is not None
}
if set(_HANDLERS) != _expected_handlers:
    raise RuntimeError("operation catalog and worker handlers differ")


def execute_operation(
    app: Any,
    operation: str,
    parameters: Dict[str, Any],
    *,
    documents: Optional[DocumentRegistry] = None,
    session_id: str = DEFAULT_SESSION_ID,
    document_id: Optional[str] = None,
    expected_update_stamp: Optional[int] = None,
    lease_id: Optional[str] = None,
) -> Dict[str, Any]:
    values = validate_operation_request(
        operation, parameters, document_id=document_id,
        expected_update_stamp=expected_update_stamp, lease_id=lease_id,
    )
    spec = OPERATION_CATALOG[operation]
    if spec.handler is None:
        raise ValueError(f"operation belongs to the supervisor: {operation}")
    context = OperationContext(app, operation, documents, session_id, document_id, lease_id)
    if spec.selected_document and documents is not None:
        context.entry = documents.resolve(document_id, session_id=session_id)
        if expected_update_stamp is not None:
            actual = documents.describe(context.entry, session_id=session_id).get("update_stamp")
            if actual is None:
                raise DocumentUpdateStampUnavailable(
                    "the selected document does not expose GetUpdateStamp"
                )
            if actual != expected_update_stamp:
                raise DocumentUpdateConflict(
                    "the selected document changed: expected update stamp "
                    f"{expected_update_stamp}, found {actual}"
                )
        if spec.lease_guarded:
            documents.require_lease(context.entry, session_id=session_id, lease_id=lease_id)
    activation = (
        documents.temporarily_activate(context.entry)
        if spec.temporary_activation and documents is not None and context.entry is not None
        else nullcontext()
    )
    with activation:
        result = _HANDLERS[spec.handler](context, values)
    if spec.temporary_activation and documents is not None and context.entry is not None:
        return _with_document(result, documents, context.entry, session_id=session_id)
    return result
