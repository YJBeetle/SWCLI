"""Exact native table transitions; populated only after original evidence audit."""

# (exact RevisionNumber, document type) -> field -> (before raw, after raw).
# The unchanged target pair permits an observed no-op, not an extra transition.
PROFILES = {}
INTERNAL_PROOF = {}
