"""Session-scoped document handles owned by the resident COM worker."""

from __future__ import annotations

import math
import ntpath
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Iterator, Optional

from ..hosts.windows import _com_value, _describe_document
from ..hosts.com_errors import DISCONNECTED_COM_HRESULTS, com_hresult
from ..hosts.windows_sketch_inspection import (
    SketchFeatureIdConflict,
    _feature_id,
    _same_feature,
)

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


class SketchNotFound(RuntimeError):
    """A sketch handle is absent from the selected document's live registry."""


class DimensionNotFound(RuntimeError):
    """A dimension handle is absent from the selected document's live registry."""


class DocumentPathConflict(RuntimeError):
    """A new native filename belongs to another open document."""


@dataclass
class DimensionEntry:
    """Exact native dimension and its registered owning sketch, not a name lookup."""

    sketch_id: str
    dimension: Any


@dataclass
class DocumentEntry:
    document_id: str
    document: Any
    sketches: Dict[str, Any] = field(default_factory=dict)
    sketch_ids_by_native_id: Dict[int, str] = field(default_factory=dict)
    dimensions: Dict[str, DimensionEntry] = field(default_factory=dict)
    dimensions_by_sketch: Dict[str, Dict[str, DimensionEntry]] = field(
        default_factory=dict
    )


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
                secrets.choice(_HANDLE_ALPHABET) for _ in range(_LEASE_TOKEN_LENGTH)
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

    def require_lease(
        self,
        entry: DocumentEntry,
        *,
        session_id: str,
        lease_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        active = self.active_lease(entry)
        if active is None:
            if lease_id is not None:
                raise DocumentLeaseNotFound(
                    f"lease '{lease_id}' does not exist or has expired"
                )
            return None
        if lease_id is None:
            raise DocumentLeaseConflict(
                f"document '{entry.document_id}' requires its active lease"
            )
        if active["lease_id"] != lease_id:
            raise DocumentLeaseConflict(
                f"lease '{lease_id}' does not own document '{entry.document_id}'"
            )
        if active["session_id"] != session_id:
            raise DocumentLeaseConflict(
                f"lease '{lease_id}' belongs to session '{active['session_id']}'"
            )
        return active

    def register(self, document: Any) -> DocumentEntry:
        key = _document_key(document)
        existing_id = self._ids_by_key.get(key)
        if existing_id is not None:
            entry = self._entries[existing_id]
            if entry.document is document:
                return entry
            try:
                compare = self.app.IsSame
            except AttributeError:
                same = False
            else:
                # COM wrappers can differ for the same native object. A path is
                # not identity: external close/reopen can reuse it between calls.
                try:
                    same = int(compare(entry.document, document)) == 1
                except Exception as exc:
                    if com_hresult(exc) not in DISCONNECTED_COM_HRESULTS:
                        raise
                    # GetDocuments returned a fresh live native object, but the
                    # formerly registered proxy is disconnected. Expire only
                    # the old document; busy/unknown errors remain fail-closed.
                    same = False
            if same:
                entry.document = document
                return entry
            self.forget(existing_id)
        entry = DocumentEntry(self._new_id(), document)
        self._entries[entry.document_id] = entry
        self._ids_by_key[key] = entry.document_id
        return entry

    def require_new_path(self, entry: DocumentEntry, path: str) -> None:
        key = ("path", ntpath.normcase(ntpath.normpath(path)))
        existing_id = self._ids_by_key.get(key)
        if existing_id is not None and existing_id != entry.document_id:
            raise DocumentPathConflict(
                "save-as destination belongs to another open document"
            )

    def refresh_key(self, entry: DocumentEntry) -> None:
        """Keep the ID, session, lease and sketch handles when native naming changes."""
        if self._entries.get(entry.document_id) is not entry:
            raise DocumentNotFound(
                f"document '{entry.document_id}' is no longer registered"
            )
        key = _document_key(entry.document)
        if key[0] == "path":
            self.require_new_path(entry, key[1])
        for old_key, document_id in tuple(self._ids_by_key.items()):
            if document_id == entry.document_id:
                del self._ids_by_key[old_key]
        self._ids_by_key[key] = entry.document_id

    def register_sketch(self, entry: DocumentEntry, feature: Any) -> str:
        if self._entries.get(entry.document_id) is not entry:
            raise DocumentNotFound(
                f"document '{entry.document_id}' is no longer registered"
            )
        # Read the incoming native ID before changing any registry state. GetID
        # is document-local, stable and never a substitute for the exact-object
        # comparison required when an already indexed ID appears again.
        native_id = _feature_id(feature)
        sketch_id = entry.sketch_ids_by_native_id.get(native_id)
        expired_id = None
        if sketch_id is not None:
            registered = entry.sketches[sketch_id]
            try:
                same = _same_feature(self.app, registered, feature)
            except Exception as exc:
                if com_hresult(exc) not in DISCONNECTED_COM_HRESULTS:
                    raise
                expired_id = sketch_id
            else:
                if not same:
                    raise SketchFeatureIdConflict(
                        "a registered native sketch ID refers to a different object"
                    )
                entry.sketches[sketch_id] = feature
                return sketch_id
        while True:
            token = "s-" + "".join(
                secrets.choice(_HANDLE_ALPHABET) for _ in range(_HANDLE_LENGTH)
            )
            if not any(token in item.sketches for item in self._entries.values()):
                if expired_id is not None:
                    del entry.sketches[expired_id]
                    del entry.sketch_ids_by_native_id[native_id]
                    for dimension_id in entry.dimensions_by_sketch.pop(expired_id, {}):
                        del entry.dimensions[dimension_id]
                entry.sketches[token] = feature
                entry.sketch_ids_by_native_id[native_id] = token
                return token

    def resolve_sketch(self, entry: DocumentEntry, sketch_id: str) -> Any:
        if (
            self._entries.get(entry.document_id) is not entry
            or sketch_id not in entry.sketches
        ):
            raise SketchNotFound(
                f"sketch '{sketch_id}' is not registered in document '{entry.document_id}'"
            )
        return entry.sketches[sketch_id]

    def register_dimension(
        self, entry: DocumentEntry, sketch_id: str, dimension: Any
    ) -> str:
        """Keep partial creations observable and reuse exact native owner-local IDs.

        Dimensions have no native ID used here, so comparisons are bounded to
        the registered owning sketch, not all dimensions in the document. This
        is per-owner indexing, not a constant-time identity lookup for arbitrary
        dimensions. Names and Python wrapper identity never select a handle.
        """
        self.resolve_sketch(entry, sketch_id)
        if dimension is None:
            raise ValueError("cannot register an absent native dimension")
        owned = entry.dimensions_by_sketch.get(sketch_id, {})
        expired_ids = []
        matched_id = None
        for dimension_id, registered in owned.items():
            try:
                status = self.app.IsSame(registered.dimension, dimension)
                if (
                    isinstance(status, bool)
                    or not isinstance(status, int)
                    or status not in (0, 1)
                ):
                    raise RuntimeError(
                        "SOLIDWORKS could not compare native dimension identity"
                    )
            except Exception as exc:
                if com_hresult(exc) not in DISCONNECTED_COM_HRESULTS:
                    raise
                expired_ids.append(dimension_id)
            else:
                if status == 1:
                    matched_id = dimension_id
                    break

        # Defer cleanup until every required comparison and token allocation
        # succeeds. A later busy/unknown COM error must leave all handles intact.
        if matched_id is None:
            while True:
                token = "m-" + "".join(
                    secrets.choice(_HANDLE_ALPHABET) for _ in range(_HANDLE_LENGTH)
                )
                if not any(token in item.dimensions for item in self._entries.values()):
                    break
        for dimension_id in expired_ids:
            del entry.dimensions[dimension_id]
            del owned[dimension_id]
        if matched_id is not None:
            owned[matched_id].dimension = dimension
            return matched_id

        registered = DimensionEntry(sketch_id, dimension)
        entry.dimensions[token] = registered
        entry.dimensions_by_sketch.setdefault(sketch_id, {})[token] = registered
        return token

    def resolve_dimension(
        self, entry: DocumentEntry, dimension_id: str
    ) -> DimensionEntry:
        if (
            self._entries.get(entry.document_id) is not entry
            or dimension_id not in entry.dimensions
        ):
            raise DimensionNotFound(
                f"dimension '{dimension_id}' is not registered in document "
                f"'{entry.document_id}'"
            )
        registered = entry.dimensions[dimension_id]
        self.resolve_sketch(entry, registered.sketch_id)
        return registered

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
        entry.sketches.clear()
        entry.sketch_ids_by_native_id.clear()
        entry.dimensions.clear()
        entry.dimensions_by_sketch.clear()
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
    def temporarily_activate(
        self, entry: DocumentEntry
    ) -> Iterator[list[Dict[str, str]]]:
        """Activate a target without rebuilding, then restore the prior document."""

        warnings: list[Dict[str, str]] = []
        previous = _com_value(self.app, "ActiveDoc")
        if self.is_active(entry):
            yield warnings
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
            yield warnings
        finally:
            if previous is not None:
                try:
                    restore_errors = win32com.client.VARIANT(
                        pythoncom.VT_BYREF | pythoncom.VT_I4, 0
                    )
                    previous_title = str(_com_value(previous, "GetTitle"))
                    restored = self.app.ActivateDoc3(
                        previous_title, False, 1, restore_errors
                    )
                    active = _com_value(self.app, "ActiveDoc")
                    try:
                        compare = self.app.IsSame
                    except AttributeError:
                        same = active is previous
                    else:
                        same = (
                            active is not None and int(compare(active, previous)) == 1
                        )
                    if restored is None or not same:
                        raise DocumentActivationFailed(
                            "SOLIDWORKS did not restore the previous foreground "
                            f"document (ActivateDoc3 status {int(restore_errors.value)})"
                        )
                except Exception as exc:
                    # Do not discard a completed native mutation or its handles
                    # merely because restoring the user's foreground failed.
                    warnings.append(
                        {
                            "code": "document-foreground-restore-failed",
                            "message": str(exc),
                        }
                    )

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
