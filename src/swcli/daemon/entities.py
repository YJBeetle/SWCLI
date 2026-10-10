"""Internal short-lived face handles; not yet wired into public operations.

The owning document must supply complete, state-verified FaceBindings. This
registry does not infer ownership from names/geometry or accept serialized COM
objects. Its scope checks require fresh native observations from the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
import secrets
from typing import Any, Dict, List, Optional, Set, Tuple

from ..hosts.windows_entity_observation import FaceBinding, MAX_FACES
from ..hosts.windows_entity_references import MAX_REFERENCE_BYTES

_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"


class EntityNotFound(RuntimeError):
    """A short entity ID is absent from this owning document's registry."""


class EntityReferenceStale(RuntimeError):
    """A changed observed configuration/stamp permanently retired the handle."""


class EntityBindingConflict(RuntimeError):
    """Native identity or a complete same-scope binding cannot be verified."""


@dataclass(frozen=True)
class EntityEntry:
    binding: FaceBinding
    configuration: str
    update_stamp: int


def _scope(configuration: str, update_stamp: int) -> Tuple[str, int]:
    if not isinstance(configuration, str) or not configuration.strip():
        raise EntityBindingConflict("entity configuration is unavailable")
    if isinstance(update_stamp, bool) or not isinstance(update_stamp, int):
        raise EntityBindingConflict("entity update stamp is unavailable")
    return configuration, update_stamp


class EntityRegistry:
    """One document's bounded registry with a shared worker-issued token set.

    Same-scope repetition reuses only exact native identities, never byte hashes.
    A scope change retires IDs even if the caller later returns to the old scope.
    Close/worker replacement is an owning-document responsibility; close() makes
    this instance unusable and keeps the shared issued set intact.
    """

    def __init__(self, app: Any, document_id: str, *, issued_ids: Set[str]):
        self.app = app
        self.document_id = document_id
        self._issued_ids = issued_ids
        self._entries: Dict[str, EntityEntry] = {}
        self._stale_ids: Set[str] = set()
        self._scope: Optional[Tuple[str, int]] = None
        self._closed = False

    def _live(self) -> None:
        if self._closed:
            raise EntityNotFound("the owning document's entity registry is closed")

    def _refresh(self, scope: Tuple[str, int]) -> None:
        if self._scope is not None and self._scope != scope:
            self._stale_ids.update(self._entries)
            self._entries.clear()
        self._scope = scope

    def _same(self, first: Any, second: Any) -> bool:
        status = self.app.IsSame(first, second)
        if (
            isinstance(status, bool)
            or not isinstance(status, int)
            or status not in (0, 1)
        ):
            raise EntityBindingConflict(
                "native entity identity is unsupported or unknown"
            )
        return status == 1

    def register_faces(
        self,
        bindings: List[FaceBinding],
        *,
        configuration: str,
        update_stamp: int,
    ) -> List[str]:
        self._live()
        scope = _scope(configuration, update_stamp)
        if (
            not isinstance(bindings, (tuple, list))
            or not 0 < len(bindings) <= MAX_FACES
        ):
            raise EntityBindingConflict(
                "entity registration requires a complete bounded face list"
            )
        for binding in bindings:
            if (
                not isinstance(binding, FaceBinding)
                or binding.face is None
                or binding.body is None
                or not isinstance(binding.reference, bytes)
                or not 0 < len(binding.reference) <= MAX_REFERENCE_BYTES
            ):
                raise EntityBindingConflict("native face binding is incomplete")
        # Retired tokens do not revive if a later registration fails. The scope
        # itself is a fresh, verified read supplied by the owning observer.
        same_scope = self._scope == scope and bool(self._entries)
        self._refresh(scope)
        staged: Dict[str, EntityEntry] = {}
        for binding in bindings:
            if staged:
                first = next(iter(staged.values())).binding
                if not self._same(first.body, binding.body):
                    raise EntityBindingConflict(
                        "complete face bindings span different bodies"
                    )
            for previous in staged.values():
                if self._same(previous.binding.face, binding.face):
                    raise EntityBindingConflict(
                        "complete face bindings repeat an entity"
                    )
                if previous.binding.reference == binding.reference:
                    raise EntityBindingConflict(
                        "distinct face bindings share an ambiguous reference"
                    )
            matches = [
                token
                for token, previous in self._entries.items()
                if self._same(previous.binding.face, binding.face)
            ]
            if len(matches) > 1:
                raise EntityBindingConflict(
                    "multiple live IDs refer to one native face"
                )
            if matches:
                token = matches[0]
                if not self._same(self._entries[token].binding.body, binding.body):
                    raise EntityBindingConflict("native face body ownership changed")
            else:
                token = "e-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))
                while token in self._issued_ids or token in staged:
                    token = "e-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))
            staged[token] = EntityEntry(binding, *scope)
        if same_scope and set(staged) != set(self._entries):
            raise EntityBindingConflict(
                "complete native face set changed without a scope change"
            )
        # No usable partial registrations or issued-token state on failed reads.
        self._entries = staged
        self._issued_ids.update(staged)
        return list(staged)

    def resolve(
        self, entity_id: str, *, configuration: str, update_stamp: int
    ) -> EntityEntry:
        self._live()
        self._refresh(_scope(configuration, update_stamp))
        if entity_id in self._stale_ids:
            raise EntityReferenceStale(
                "entity scope changed; discover fresh handles explicitly"
            )
        try:
            return self._entries[entity_id]
        except KeyError as exc:
            raise EntityNotFound(
                "entity ID is absent from the selected document"
            ) from exc

    def close(self) -> None:
        self._entries.clear()
        self._stale_ids.clear()
        self._scope = None
        self._closed = True
