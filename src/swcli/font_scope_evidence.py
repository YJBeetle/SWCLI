"""Durable, observation-only table font witnesses for owned diagnostics."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re

from .font_scope_candidates import NEXT_FONT_LINKED_READS
from .font_snapshot import font_snapshot

TABLE_WITNESS_BOUNDARIES = ("initial", "changed-typeface", "changed-bold", "changed-italic",
    "changed-underline", "changed-strikeout", "changed-height_mm", "reopened-millimeters",
    "changed-height_points", "reopened-points")


class LinkedFontJournal:
    """Persist begin/per-type/complete records before the next native operation.

    A partial boundary stays partial. No append retry, truncation or recovery is
    attempted. Original values and explicit old/new member pairs are retained;
    a completed witness never claims object or cell inheritance acceptance.
    """
    def __init__(self, path, *, kind, source_head):
        if kind not in ("part", "assembly", "drawing"):
            raise ValueError("unknown font witness document kind")
        if not isinstance(source_head, str) or re.fullmatch(r"[0-9a-f]{40}", source_head) is None:
            raise ValueError("font witness requires the exact source head")
        self.path = Path(path)
        if self.path.exists():
            raise FileExistsError("font witness journal must be fresh")
        self.kind, self.source_head = kind, source_head
        self.labels = tuple(NEXT_FONT_LINKED_READS["tables"])
        self.previous, self.current, self.boundary = None, {}, None
        self.index, self.failed = 0, False

    def _write(self, phase, **values):
        if self.failed:
            raise RuntimeError("font witness journal already failed; no retry")
        record = dict(evidence_kind="linked-font-read-witness", source_head=self.source_head,
            kind=self.kind, boundary=self.boundary, boundary_index=self.index, phase=phase,
            public_acceptance=False, inheritance_acceptance=False, **values)
        try:
            payload = (json.dumps(record, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
            with self.path.open("ab") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            self.failed = True
            raise
        return record

    def begin(self, boundary, *, mutation):
        if self.boundary is not None or self.index >= len(TABLE_WITNESS_BOUNDARIES):
            raise RuntimeError("font witness boundary is already active or exhausted")
        if boundary != TABLE_WITNESS_BOUNDARIES[self.index]:
            raise ValueError("font witness boundary missing or out of order")
        if (type(mutation) is not dict or set(mutation) != {"attempted", "may_have_changed"}
                or any(type(value) is not bool for value in mutation.values())):
            raise ValueError("font witness mutation receipt is incomplete")
        self.boundary = boundary
        self.current = {}
        self._write("begin", before=deepcopy(self.previous), mutation=deepcopy(mutation))

    def observe(self, label, font, native_font):
        if self.boundary is None or len(self.current) >= len(self.labels):
            raise RuntimeError("font witness has no pending font")
        if label != self.labels[len(self.current)]:
            raise ValueError("linked font type missing, repeated or out of order")
        if font_snapshot(native_font) != font:
            raise ValueError("linked native and normalized font differ")
        after = dict(font=deepcopy(font), native_font=deepcopy(native_font))
        before = None if self.previous is None else deepcopy(self.previous[label])
        changes = {} if before is None else {
            member: dict(before=before["native_font"][member], after=value)
            for member, value in native_font.items() if before["native_font"][member] != value}
        self._write("font", label=label, before=before, after=after, changes=changes)
        self.current[label] = after

    def complete(self):
        if tuple(self.current) != self.labels:
            raise RuntimeError("all five linked fonts are required; boundary remains partial")
        changes = {} if self.previous is None else {
            label: {member: dict(before=self.previous[label]["native_font"][member], after=value)
                    for member, value in values["native_font"].items()
                    if self.previous[label]["native_font"][member] != value}
            for label, values in self.current.items()}
        record = self._write("complete", before=deepcopy(self.previous), after=deepcopy(self.current), changes=changes)
        self.previous = deepcopy(self.current)
        self.boundary = None
        self.index += 1
        return record
