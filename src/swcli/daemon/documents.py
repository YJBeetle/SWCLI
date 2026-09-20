"""Session-scoped document handles owned by the resident COM worker."""

from __future__ import annotations

import math
import ntpath
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Iterator, Optional

from ..hosts.windows import _com_value, _describe_document


_HANDLE_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
_HANDLE_LENGTH = 6
_LEASE_TOKEN_LENGTH = 12
DEFAULT_SESSION_ID = "default"


class DocumentNotFound(RuntimeError):
    """The requested short-lived document handle is not registered."""


class NoCurrentDocument(RuntimeError):
    """The selected session has no remembered current document."""


class NoActiveDocument(RuntimeError):
    """SOLIDWORKS has no foreground document for the active selector."""


class DocumentActivationFailed(RuntimeError):
    """SOLIDWORKS could not make a required target document active."""


class DocumentLeaseConflict(RuntimeError):
    """Another client holds the selected document lease."""


class DocumentLeaseNotFound(RuntimeError):
    """A requested document lease does not exist or has expired."""


@dataclass
class DocumentEntry:
    document_id: str
    document: Any


@dataclass
class DocumentLease:
    lease_id: str
    document_id: str
    session_id: str
    expires_at: float


def _documents(value: Any) -> Iterable[Any]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return value
    try:
        return tuple(value)
    except TypeError:
        return (value,)


def _document_key(document: Any) -> tuple[Any, ...]:
    description = _describe_document(document)
    path = str(description["path"])
    if path:
        return ("path", ntpath.normcase(ntpath.normpath(path)))
    return (
        "unsaved",
        int(description["type"]),
        str(description["title"]).casefold(),
    )


class DocumentRegistry:
    """Map short-lived IDs to documents and remember a current ID per session."""

    def __init__(
        self, app: Any, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.app = app
        self._clock = clock
        self._entries: Dict[str, DocumentEntry] = {}
        self._ids_by_key: Dict[tuple[Any, ...], str] = {}
        self._current_by_session: Dict[str, str] = {}
        self._leases_by_id: Dict[str, DocumentLease] = {}
        self._lease_id_by_document: Dict[str, str] = {}

    def _new_id(self) -> str:
        while True:
            suffix = "".join(
                secrets.choice(_HANDLE_ALPHABET) for _ in range(_HANDLE_LENGTH)
            )
            document_id = f"d-{suffix}"
            if document_id not in self._entries:
                return document_id

    def _new_lease_id(self) -> str:
        while True:
            suffix = "".join(
                secrets.choice(_HANDLE_ALPHABET)
                for _ in range(_LEASE_TOKEN_LENGTH)
            )
            lease_id = f"l-{suffix}"
            if lease_id not in self._leases_by_id:
                return lease_id

    def _purge_expired_leases(self) -> None:
        now = self._clock()
        for lease_id, lease in tuple(self._leases_by_id.items()):
            if lease.expires_at <= now:
                self._forget_lease(lease_id)

    def _forget_lease(self, lease_id: str) -> None:
        lease = self._leases_by_id.pop(lease_id, None)
        if lease is None:
            return
        if self._lease_id_by_document.get(lease.document_id) == lease_id:
            del self._lease_id_by_document[lease.document_id]

    def _describe_lease(self, lease: DocumentLease) -> Dict[str, Any]:
        return {
            "lease_id": lease.lease_id,
            "document_id": lease.document_id,
            "session_id": lease.session_id,
            "expires_in_seconds": max(0.0, lease.expires_at - self._clock()),
        }

    def acquire_lease(
        self, entry: DocumentEntry, *, session_id: str, ttl_seconds: float
    ) -> Dict[str, Any]:
        if not math.isfinite(ttl_seconds) or ttl_seconds <= 0:
            raise ValueError("lease ttl_seconds must be positive and finite")
        self._purge_expired_leases()
        existing_id = self._lease_id_by_document.get(entry.document_id)
        if existing_id is not None:
            existing = self._leases_by_id[existing_id]
            if existing.session_id != session_id:
                raise DocumentLeaseConflict(
                    f"document '{entry.document_id}' is leased by session "
                    f"'{existing.session_id}'"
                )
            existing.expires_at = self._clock() + ttl_seconds
            return self._describe_lease(existing)

        lease = DocumentLease(
            lease_id=self._new_lease_id(),
            document_id=entry.document_id,
            session_id=session_id,
            expires_at=self._clock() + ttl_seconds,
        )
        self._leases_by_id[lease.lease_id] = lease
        self._lease_id_by_document[entry.document_id] = lease.lease_id
        return self._describe_lease(lease)

    def renew_lease(
        self, lease_id: str, *, session_id: str, ttl_seconds: float
    ) -> Dict[str, Any]:
        if not math.isfinite(ttl_seconds) or ttl_seconds <= 0:
            raise ValueError("lease ttl_seconds must be positive and finite")
        self._purge_expired_leases()
        lease = self._leases_by_id.get(lease_id)
        if lease is None:
            raise DocumentLeaseNotFound(
                f"lease '{lease_id}' does not exist or has expired"
            )
        if lease.session_id != session_id:
            raise DocumentLeaseConflict(
                f"lease '{lease_id}' belongs to session '{lease.session_id}'"
            )
        lease.expires_at = self._clock() + ttl_seconds
        return self._describe_lease(lease)

    def release_lease(self, lease_id: str, *, session_id: str) -> Dict[str, Any]:
        self._purge_expired_leases()
        lease = self._leases_by_id.get(lease_id)
        if lease is None:
            raise DocumentLeaseNotFound(
                f"lease '{lease_id}' does not exist or has expired"
            )
        if lease.session_id != session_id:
            raise DocumentLeaseConflict(
                f"lease '{lease_id}' belongs to session '{lease.session_id}'"
            )
        result = self._describe_lease(lease)
        self._forget_lease(lease_id)
        return result

    def active_lease(self, entry: DocumentEntry) -> Optional[Dict[str, Any]]:
        self._purge_expired_leases()
        lease_id = self._lease_id_by_document.get(entry.document_id)
        if lease_id is None:
            return None
        return self._describe_lease(self._leases_by_id[lease_id])

    def register(self, document: Any) -> DocumentEntry:
        key = _document_key(document)
        existing_id = self._ids_by_key.get(key)
        if existing_id is not None:
            entry = self._entries[existing_id]
            entry.document = document
            return entry
        entry = DocumentEntry(self._new_id(), document)
        self._entries[entry.document_id] = entry
        self._ids_by_key[key] = entry.document_id
        return entry

    def sync(self) -> None:
        open_documents = list(_documents(_com_value(self.app, "GetDocuments")))
        open_keys = set()
        for document in open_documents:
            key = _document_key(document)
            open_keys.add(key)
            self.register(document)

        closed_ids = {
            document_id
            for key, document_id in self._ids_by_key.items()
            if key not in open_keys
        }
        for document_id in closed_ids:
            self.forget(document_id)

    def forget(self, document_id: str) -> None:
        entry = self._entries.pop(document_id, None)
        if entry is None:
            return
        lease_id = self._lease_id_by_document.get(document_id)
        if lease_id is not None:
            self._forget_lease(lease_id)
        for key, registered_id in tuple(self._ids_by_key.items()):
            if registered_id == document_id:
                del self._ids_by_key[key]
        for session_id, current_id in tuple(self._current_by_session.items()):
            if current_id == document_id:
                del self._current_by_session[session_id]

    def resolve(
        self, selector: Optional[str], *, session_id: str = DEFAULT_SESSION_ID
    ) -> DocumentEntry:
        if selector == "active":
            document = _com_value(self.app, "ActiveDoc")
            if document is None:
                raise NoActiveDocument("SOLIDWORKS has no active document")
            return self.register(document)

        self.sync()
        document_id = selector
        if document_id is None:
            document_id = self._current_by_session.get(session_id)
            if document_id is None:
                raise NoCurrentDocument(
                    f"session '{session_id}' has no current document; open, create, "
                    "or select one with 'sw-cli document use DOCUMENT_ID'"
                )
        entry = self._entries.get(document_id)
        if entry is None:
            raise DocumentNotFound(
                f"document '{document_id}' is not open in this worker session"
            )
        return entry

    def use(self, document_id: str, *, session_id: str) -> DocumentEntry:
        if document_id in {"active", "current"}:
            raise DocumentNotFound("document use requires an exact d-... document ID")
        entry = self.resolve(document_id, session_id=session_id)
        self._current_by_session[session_id] = entry.document_id
        return entry

    def set_current(self, entry: DocumentEntry, *, session_id: str) -> None:
        self._current_by_session[session_id] = entry.document_id

    def describe(
        self, entry: DocumentEntry, *, session_id: str = DEFAULT_SESSION_ID
    ) -> Dict[str, Any]:
        description = _describe_document(entry.document)
        active = _com_value(self.app, "ActiveDoc")
        description.update(
            {
                "document_id": entry.document_id,
                "current": self._current_by_session.get(session_id)
                == entry.document_id,
                "active": active is not None
                and _document_key(active) == _document_key(entry.document),
            }
        )
        return description

    def is_active(self, entry: DocumentEntry) -> bool:
        active = _com_value(self.app, "ActiveDoc")
        return active is not None and _document_key(active) == _document_key(
            entry.document
        )

    @contextmanager
    def temporarily_activate(self, entry: DocumentEntry) -> Iterator[None]:
        """Activate a target without rebuilding, then restore the prior document."""

        previous = _com_value(self.app, "ActiveDoc")
        if self.is_active(entry):
            yield
            return

        import pythoncom
        import win32com.client

        errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        title = str(_com_value(entry.document, "GetTitle"))
        activated = self.app.ActivateDoc3(title, False, 1, errors)
        if activated is None or not self.is_active(entry):
            raise DocumentActivationFailed(
                f"SOLIDWORKS could not activate document '{entry.document_id}' "
                f"(ActivateDoc3 status {int(errors.value)})"
            )
        try:
            yield
        finally:
            if previous is not None:
                restore_errors = win32com.client.VARIANT(
                    pythoncom.VT_BYREF | pythoncom.VT_I4, 0
                )
                previous_title = str(_com_value(previous, "GetTitle"))
                self.app.ActivateDoc3(previous_title, False, 1, restore_errors)

    def list(self, *, session_id: str) -> Dict[str, Any]:
        self.sync()
        items = [
            self.describe(entry, session_id=session_id)
            for entry in self._entries.values()
        ]
        items.sort(
            key=lambda item: (
                str(item["path"]).casefold(),
                item["document_id"],
            )
        )
        return {
            "ok": True,
            "action": "document.list",
            "session_id": session_id,
            "current_document_id": self._current_by_session.get(session_id),
            "documents": items,
            "count": len(items),
        }
