"""Exact native table transitions; populated only after original evidence audit."""

# (exact RevisionNumber, document type) -> field -> (before raw, after raw).
# The unchanged target pair permits an observed no-op, not an extra transition.
PROFILES = {
    ('33.5.0', 2): {
        'all.use_template_settings': [(True, False), (False, False)],
        'bom.box_border': [(0, 1), (1, 1)],
        'bom.grid_border': [(0, 1), (1, 1)],
    },
    ('33.5.0', 3): {
        'all.use_template_settings': [(False, True), (True, True)],
        'bom.box_border': [(0, 1), (1, 1)],
        'bom.grid_border': [(0, 1), (1, 1)],
        'general.box_border': [(0, 1), (1, 1)],
        'general.grid_border': [(0, 1), (1, 1)],
    },
}

INTERNAL_PROOF = {
    'run_id': 42301331238,
    'head': '50db73af937cd78aa9adcd8c4bfdd5467c956533',
    'artifact_id': 13545815581,
    'artifact_name': 'table-defaults-internal-42301331238-1',
    'artifact_digest': 'sha256:7e473478064998f3e116329d29007f8f21c441be74d7827a7d3bfbc90fc2f4f6',
    'report_sha256': 'f04b79376ea8e5e5fd7569c7d20feb28ae6193215ee9dc29695c3bca5dbbd7f9',
    'native_trace_sha256': 'd95c6b1ac3c577cb4a90772a83b7f47f51b618adabeab5880cf03bbd7812ef13',
    'harness_trace_sha256': 'eb97a6e5fb77dae6d1f46f63122c9847d90dc965c16a319df92b87f8d5393afa',
}
