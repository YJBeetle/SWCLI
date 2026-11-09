"""Exact native table transitions; populated only after original evidence audit."""

# (exact RevisionNumber, document type) -> field -> (before raw, after raw).
# The unchanged target pair permits an observed no-op, not an extra transition.
PROFILES = {
    ('33.5.0', 1): {
        'all.use_template_settings': [(True, False), (False, False)],
        'bom.box_border': [(0, 1), (1, 1)],
        'bom.grid_border': [(0, 1), (1, 1)],
    },
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
    'run_id': 42415716434,
    'head': 'f1881a7421200e46028652538892c15a366f2ef8',
    'artifact_id': 13591813168,
    'artifact_name': 'table-defaults-internal-42415716434-1',
    'artifact_digest': 'sha256:7e1d8fcd8c1d8b26346024305c0f30a0c77536b2ea4ade06f3c694e382db9e8e',
    'report_sha256': '9e4c61044958cbe5ae6964820e8e800e87f003871ca419850e56c319dfd566cf',
    'native_trace_sha256': '0ceb9245963abf13eeaef13162c3ef6318fbd405d16fa8096ee69260684d0127',
    'harness_trace_sha256': '3926c138fae2f4747ff53ecbd6608c9a61960d3e3a132a7eea2f51a6231d6af9',
}
