"""Document-local face/edge handles with one conservative observed scope.

The owning document must supply complete, state-verified bindings per kind. This
registry does not infer ownership from names/geometry or accept serialized COM
objects. Its scope checks require fresh native observations from the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
import secrets
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..hosts.windows_entity_observation import FaceBinding, MAX_FACES
from ..hosts.windows_edge_observation import EdgeBinding, MAX_EDGES
from ..hosts.windows_entity_references import MAX_REFERENCE_BYTES
from ..hosts.native_trace import native_call

_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"


class EntityNotFound(RuntimeError):
    """A short entity ID is absent from this owning document's registry."""


class EntityReferenceStale(RuntimeError):
    """A changed observed configuration/stamp permanently retired the handle."""


class EntityBindingConflict(RuntimeError):
    """Native identity or a complete same-scope binding cannot be verified."""


@dataclass(frozen=True)
class EntityEntry:
    binding: Union[FaceBinding, EdgeBinding]
    configuration: str
    update_stamp: int

    @property
    def kind(self) -> str:
        return "face" if isinstance(self.binding, FaceBinding) else "edge"


def _entity(binding: Union[FaceBinding, EdgeBinding]) -> Any:
    return binding.face if isinstance(binding, FaceBinding) else binding.edge


def _scope(configuration: str, update_stamp: int) -> Tuple[str, int]:
    if not isinstance(configuration, str) or not configuration.strip():
        raise EntityBindingConflict("entity configuration is unavailable")
    if isinstance(update_stamp, bool) or not isinstance(update_stamp, int):
        raise EntityBindingConflict("entity update stamp is unavailable")
    return configuration, update_stamp


class EntityRegistry:
    """One document's bounded registry with a shared worker-issued token set.

    Complete sets are checked per kind; all kinds share scope/body ownership.
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
        self._complete_kinds: Set[str] = set()
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
            self._complete_kinds.clear()
        self._scope = scope

    def observe_scope(self, *, configuration: str, update_stamp: int) -> None:
        """Retire old IDs after a verified scope read, without issuing new ones.

        Geometry may fail after the scope was read. Such a failure must not let
        the caller revive old handles by returning to a previous configuration.
        """
        self._live()
        self._refresh(_scope(configuration, update_stamp))

    def _same(self, first: Any, second: Any) -> bool:
        status = native_call(
            "entity-registry",
            "ISldWorks.IsSame",
            lambda: self.app.IsSame(first, second),
        )
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
        return self._register(
            bindings, kind="face", configuration=configuration, update_stamp=update_stamp
        )

    def register_edges(
        self,
        bindings: List[EdgeBinding],
        *,
        configuration: str,
        update_stamp: int,
    ) -> List[str]:
        return self._register(
            bindings, kind="edge", configuration=configuration, update_stamp=update_stamp
        )

    def _register(
        self,
        bindings: Union[List[FaceBinding], List[EdgeBinding]],
        *,
        kind: str,
        configuration: str,
        update_stamp: int,
    ) -> List[str]:
        self._live()
        scope = _scope(configuration, update_stamp)
        binding_type, limit = (
            (FaceBinding, MAX_FACES) if kind == "face" else (EdgeBinding, MAX_EDGES)
        )
        if (
            not isinstance(bindings, (tuple, list))
            or not 0 < len(bindings) <= limit
        ):
            raise EntityBindingConflict(
                f"entity registration requires a complete bounded {kind} list"
            )
        for binding in bindings:
            if (
                not isinstance(binding, binding_type)
                or _entity(binding) is None
                or binding.body is None
                or not isinstance(binding.reference, bytes)
                or not 0 < len(binding.reference) <= MAX_REFERENCE_BYTES
            ):
                raise EntityBindingConflict(f"native {kind} binding is incomplete")
        # Retired tokens do not revive if a later registration fails. The scope
        # itself is a fresh, verified read supplied by the owning observer.
        same_scope = self._scope == scope and kind in self._complete_kinds
        self._refresh(scope)
        previous_kind = {
            token: entry for token, entry in self._entries.items() if entry.kind == kind
        }
        other_kinds = {
            token: entry for token, entry in self._entries.items() if entry.kind != kind
        }
        staged: Dict[str, EntityEntry] = {}
        for binding in bindings:
            if other_kinds:
                first_other = next(iter(other_kinds.values())).binding
                if not self._same(first_other.body, binding.body):
                    raise EntityBindingConflict("native entity kinds span different bodies")
                if any(
                    previous.binding.reference == binding.reference
                    for previous in other_kinds.values()
                ):
                    raise EntityBindingConflict(
                        "native entity kinds share an ambiguous reference"
                    )
            if staged:
                first = next(iter(staged.values())).binding
                if not self._same(first.body, binding.body):
                    raise EntityBindingConflict(
                        f"complete {kind} bindings span different bodies"
                    )
            for previous in staged.values():
                if self._same(_entity(previous.binding), _entity(binding)):
                    raise EntityBindingConflict(
                        f"complete {kind} bindings repeat an entity"
                    )
                if previous.binding.reference == binding.reference:
                    raise EntityBindingConflict(
                        f"distinct {kind} bindings share an ambiguous reference"
                    )
            matches = [
                token
                for token, previous in previous_kind.items()
                if self._same(_entity(previous.binding), _entity(binding))
            ]
            if len(matches) > 1:
                raise EntityBindingConflict(
                    f"multiple live IDs refer to one native {kind}"
                )
            if matches:
                token = matches[0]
                if not self._same(self._entries[token].binding.body, binding.body):
                    raise EntityBindingConflict(f"native {kind} body ownership changed")
            else:
                token = "e-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))
                while token in self._issued_ids or token in staged:
                    token = "e-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))
            staged[token] = EntityEntry(binding, *scope)
        if same_scope and set(staged) != set(previous_kind):
            raise EntityBindingConflict(
                f"complete native {kind} set changed without a scope change"
            )
        # No usable partial registrations or issued-token state on failed reads.
        self._entries = {**other_kinds, **staged}
        self._complete_kinds.add(kind)
        self._issued_ids.update(staged)
        return list(staged)

    def resolve(
        self, entity_id: str, *, configuration: str, update_stamp: int, kind: str = "face"
    ) -> EntityEntry:
        self._live()
        if kind not in ("face", "edge"):
            raise EntityBindingConflict("entity kind must be face or edge")
        self._refresh(_scope(configuration, update_stamp))
        if entity_id in self._stale_ids:
            raise EntityReferenceStale(
                "entity scope changed; discover fresh handles explicitly"
            )
        try:
            entry = self._entries[entity_id]
        except KeyError as exc:
            raise EntityNotFound(
                "entity ID is absent from the selected document"
            ) from exc
        if entry.kind != kind:
            raise EntityNotFound("entity ID belongs to another entity kind")
        return entry

    def close(self) -> None:
        self._entries.clear()
        self._complete_kinds.clear()
        self._stale_ids.clear()
        self._scope = None
        self._closed = True
