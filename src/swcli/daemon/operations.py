"""Typed operations executed by the resident COM worker."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..operation_schemas import (
    OPERATIONS,
    OPERATION_SCHEMAS,
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
    {
        "document.close",
        "document.save",
        "document.rebuild",
        "document.render",
        "document.export",
    }
)

LEASE_TOKEN_OPERATIONS = frozenset(
    name
    for name, schema in OPERATION_SCHEMAS.items()
    if schema["x-swcli-context"]["lease_id"] != "forbidden"
)

UPDATE_STAMP_OPERATIONS = frozenset(
    name
    for name, schema in OPERATION_SCHEMAS.items()
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
        operation,
        parameters,
        document_id=document_id,
        expected_update_stamp=expected_update_stamp,
        lease_id=lease_id,
    )
    if operation == "document.open":
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
        if documents is None:
            raise RuntimeError("document registry is unavailable")
        return documents.list(session_id=session_id)
    if operation == "document.use":
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

    if operation == "document.lease.renew":
        if documents is None:
            raise RuntimeError("document registry is unavailable")
        if lease_id is None:
            raise ValueError("document.lease.renew requires lease_id")
        lease = documents.renew_lease(
            lease_id,
            session_id=session_id,
            ttl_seconds=_lease_ttl(values),
        )
        return {
            "ok": True,
            "action": operation,
            "session_id": session_id,
            "lease": lease,
        }
    if operation == "document.lease.release":
        if documents is None:
            raise RuntimeError("document registry is unavailable")
        if lease_id is None:
            raise ValueError("document.lease.release requires lease_id")
        lease = documents.release_lease(lease_id, session_id=session_id)
        return {
            "ok": True,
            "action": operation,
            "session_id": session_id,
            "released": True,
            "lease": lease,
        }

    entry = None
    if operation.startswith("document.") and documents is not None:
        entry = documents.resolve(document_id, session_id=session_id)
        if expected_update_stamp is not None:
            actual_update_stamp = documents.describe(
                entry, session_id=session_id
            ).get("update_stamp")
            if actual_update_stamp is None:
                raise DocumentUpdateStampUnavailable(
                    "the selected document does not expose GetUpdateStamp"
                )
            if actual_update_stamp != expected_update_stamp:
                raise DocumentUpdateConflict(
                    "the selected document changed: expected update stamp "
                    f"{expected_update_stamp}, found {actual_update_stamp}"
                )

    if operation == "document.lease.acquire":
        if documents is None or entry is None:
            raise RuntimeError("document registry is unavailable")
        lease = documents.acquire_lease(
            entry,
            session_id=session_id,
            ttl_seconds=_lease_ttl(values),
        )
        return {
            "ok": True,
            "action": operation,
            "session_id": session_id,
            "lease": lease,
            "document": documents.describe(entry, session_id=session_id),
        }
    if operation == "document.lease.status":
        if documents is None or entry is None:
            raise RuntimeError("document registry is unavailable")
        lease = documents.active_lease(entry)
        if lease is not None and lease["session_id"] != session_id:
            lease = {key: value for key, value in lease.items() if key != "lease_id"}
        return {
            "ok": True,
            "action": operation,
            "session_id": session_id,
            "leased": lease is not None,
            "owned_by_session": lease is not None
            and lease["session_id"] == session_id,
            "lease": lease,
            "document": documents.describe(entry, session_id=session_id),
        }

    if (
        operation in LEASE_GUARDED_OPERATIONS
        and documents is not None
        and entry is not None
    ):
        documents.require_lease(
            entry, session_id=session_id, lease_id=lease_id
        )

    if operation == "document.inspect":
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
        result = save_active_windows_document(
            app=app, document=entry.document if entry is not None else None
        )
        return (
            _with_document(result, documents, entry, session_id=session_id)
            if documents is not None and entry is not None
            else result
        )
    if operation == "document.diagnose":
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
