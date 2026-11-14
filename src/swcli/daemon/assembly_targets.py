"""Worker/STA/document/session-local typed handles and readonly full-scope CAS.

Never calls an owner getter, resolves a reference, activates, or writes CAD.
Only the reviewed complete native observer establishes face ownership.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import secrets
import threading

from ..assembly_target_contracts import canonical, census_value
from ..hosts.native_trace import native_call
from ..hosts.windows_assembly_target_observation import AssemblyFaceBinding


class AssemblyTargetNotFound(RuntimeError):
    pass


class AssemblyTargetStale(RuntimeError):
    pass


class AssemblyTargetConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    targets: tuple
    value: dict
    bindings: tuple
    source_documents: tuple


class AssemblyTargetRegistry:
    MAX_SESSIONS = 16
    MAX_ISSUED = 16384

    def __init__(self, app, document, document_id, *, issued_ids):
        self.app, self.document, self.document_id = app, document, document_id
        self.thread_id = threading.get_ident()
        self.issued_ids = issued_ids
        self.snapshots = {}
        self.stale = set()
        self.closed = False

    def live(self):
        if threading.get_ident() != self.thread_id:
            raise AssemblyTargetConflict('assembly handles belong to the owning STA thread')
        if self.closed:
            raise AssemblyTargetNotFound('assembly target registry is closed')

    def same(self, first, second):
        self.live()
        status = native_call('assembly-target-registry', 'ISldWorks.IsSame', lambda: self.app.IsSame(first, second))
        if type(status) is not int or status not in (0, 1):
            raise AssemblyTargetConflict('native assembly target identity is unknown')
        return status == 1

    def retire(self, session):
        self.live()
        old = self.snapshots.pop(session, None)
        if old is not None:
            self.stale.add(old.snapshot_id)

    def invalidate_all(self):
        # Closed registries are already retired; failure cleanup is idempotent.
        if self.closed:
            return
        self.live()
        for session in tuple(self.snapshots):
            self.retire(session)

    def invalidate_after_failure(self):
        """Retire without replacing the original exception or touching CAD."""
        try:
            self.invalidate_all()
        except Exception as secondary:
            # A retirement error cannot leave a live grant or replace the first
            # business/native error. This owning-STA fallback uses only Python
            # state, never another native probe, retry or close-document call.
            self.closed = True
            self.snapshots.clear()
            self.document = self.app = None
            self.retirement_error = type(secondary).__name__

    def close(self):
        self.live()
        for session in tuple(self.snapshots):
            self.retire(session)
        self.snapshots.clear()
        self.document = self.app = None
        self.closed = True

    def lookup(self, session, snapshot_id, target_ids):
        self.live()
        snapshot = self.snapshots.get(session)
        if snapshot is None or snapshot.snapshot_id != snapshot_id:
            error = AssemblyTargetStale if snapshot_id in self.stale else AssemblyTargetNotFound
            raise error('snapshot is unavailable in this worker/document/session')
        known = {t['target_id'] for t in snapshot.targets}
        if (not isinstance(target_ids, (tuple, list)) or not target_ids
                or len(set(target_ids)) != len(target_ids)
                or any(type(t) is not str or t not in known for t in target_ids)):
            raise AssemblyTargetNotFound('target kind or snapshot/document/session scope differs')
        return snapshot

    def capacity(self, session):
        self.live()
        if session not in self.snapshots and len(self.snapshots) >= self.MAX_SESSIONS:
            raise AssemblyTargetConflict('assembly target session capacity reached')
        if len(self.issued_ids) + 129 > self.MAX_ISSUED:
            raise AssemblyTargetConflict('assembly target token capacity reached; restart worker explicitly')

    def _new(self, prefix, staged):
        # Bounded allocation; no potentially infinite collision retry.
        for _ in range(32):
            token = prefix + secrets.token_hex(16)
            if token not in self.issued_ids and token not in staged:
                staged.add(token)
                return token
        raise AssemblyTargetConflict('could not allocate a unique target token')

    def stage(self, session, census, source_documents):
        self.capacity(session)
        value = census_value(census.value)
        bindings = tuple(census.bindings)
        if len(bindings) != value['face_count'] or len(source_documents) != 2:
            raise AssemblyTargetConflict('incomplete native target binding batch')
        flat = [f for c in value['components'] for f in c['faces']]
        for binding, face in zip(bindings, flat):
            if (not isinstance(binding, AssemblyFaceBinding)
                    or any(getattr(binding, field) is None for field in
                           ('component', 'source', 'original_mapped', 'resolved', 'body'))
                    or type(binding.reference) is not bytes or not binding.reference
                    or hashlib.sha256(binding.reference).hexdigest() != face['reference_sha256']):
                raise AssemblyTargetConflict('native target binding/reference is incomplete')
        if any(source is None for source in source_documents):
            raise AssemblyTargetConflict('source document identity unavailable')
        staged = set()
        snapshot_id = self._new('as-', staged)
        targets = tuple(dict(target_id=self._new('at-', staged), kind='assembly-face',
                             component_name=c['name'], face_index=f['index'])
                        for c in value['components'] for f in c['faces'])
        return Snapshot(snapshot_id, targets, value, bindings, tuple(source_documents))

    def publish(self, session, snapshot):
        self.live()
        tokens = {snapshot.snapshot_id, *(t['target_id'] for t in snapshot.targets)}
        if tokens & self.issued_ids:
            raise AssemblyTargetConflict('staged token was already issued')
        self.retire(session)
        self.issued_ids.update(tokens)
        self.snapshots[session] = snapshot

    def compare(self, old, census, source_documents):
        self.live()
        value = census_value(census.value)
        if canonical(old.value) != canonical(value) or len(old.bindings) != len(census.bindings):
            raise AssemblyTargetStale('complete target census changed')
        if len(source_documents) != len(old.source_documents) or any(
                not self.same(a, b) for a, b in zip(old.source_documents, source_documents)):
            raise AssemblyTargetStale('source document native identity changed')
        matched = set()
        for previous in old.bindings:
            matches = [i for i, fresh in enumerate(census.bindings)
                       if self.same(previous.component, fresh.component)
                       and self.same(previous.resolved, fresh.resolved)]
            if len(matches) != 1 or matches[0] in matched:
                raise AssemblyTargetStale('native target mapping is missing, repeated or ambiguous')
            fresh = census.bindings[matches[0]]
            if (previous.reference != fresh.reference or any(
                    not self.same(getattr(previous, k), getattr(fresh, k))
                    for k in ('source', 'original_mapped', 'body'))):
                raise AssemblyTargetStale('native source/mapped/body/reference identity changed')
            matched.add(matches[0])
        if len(matched) != len(census.bindings):
            raise AssemblyTargetStale('incomplete native target bijection')
        return deepcopy(value)
