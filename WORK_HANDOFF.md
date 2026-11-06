# STEP export options handoff

## Scope / coordination (2026-11-07)
- Worktree: swcli-step-export-options/SWCLI; branch codex/swcli-step-export-options.
- Baseline HEAD: 3bda2c00489dde6a3d1e4521c548f751b1d1c197; initially clean; no .codegraph directory.
- Own only STEP/STP options. Proposed additive document.export parameters: step_protocol (`ap203`, `ap214`) and step_geometry (`solid-surface`, `wireframe`, `wireframe-sketches`). STL/GLB untouched.
- Shared files: operation_schemas.py, cli.py, daemon/operations.py, daemon/server.py, hosts/windows_documents.py, generated SDK, CI workflow. Integrator must reconcile additive edits from other export branches.
- STEP preferences are application-global: require trusted daemon-owned invisible host scope, serialized worker, native type-library enum resolution, complete preference snapshot/CAS before changes, checked setters/readbacks and finally restore verification. Shared/visible hosts fail closed.
- Uncalibrated public writes remain disabled. A targeted manual CI-only calibration scope will exercise the identical worker/adapter; public release eligibility remains separate from this evidence.
- Official API supports swStepAP values 203/214 and swStepExportPreference with swAcisOutputGeometryPreference_e. No AP242 assumption.

## Tests / commit / native evidence
- Initial inspection only; implementation, portable tests, commit/push and single branch-head workflow_dispatch pending.
- No local VM use, main merge, version change, release, DockerSW pointer or MacSW changes.

## Implementation / portable verification phase
- Implemented additive `step_protocol` + `step_geometry` request/CLI/generated SDK fields; MCP uses the existing execute surface. Both options, STEP/STP extension, live lease and expected stamp are required together.
- New `windows_step_export.py` resolves the installed official enum names; supports AP203/AP214 and solid-surface/wireframe/wireframe-sketches only. Restricts to clean writable non-editing parts in an owned hidden worker scope. Revision allowlist remains empty: public writes fail closed pending reviewed native/public acceptance.
- Complete two-preference snapshot/CAS, setter/readback, post-export desired readback, finally original restore/readback, original-error preservation plus partial mutation/restore evidence; failed restoration quarantines the worker. STEP schema/termination/entity-family verification precedes atomic output publication.
- Native script plans six combinations in one owned host. Checks default public gate rejection separately, explicit background document identity, real STEP schema and hashes, analytic box/wire geometry after LoadFile4, native save and readonly reopen. No restart/retry; 600-second native and 1800-second group watchdogs.
- CI input `native_step_targeted` defaults false, dedicated branch/manual event only. STEP uses `swcli-step-export-{github.ref}` concurrency, cancel-in-progress=false; full/release keep `swcli-hosted-windows-solidworks`. No other runs canceled or dispatched.
- Targeted portable tests: 17 passed. SDK strict typing/generation: passed, including 10 negative consumer fixtures. YAML parsing and CI event/branch truth table passed. Existing mesh export tests: 8 passed.
- Initial full suite found only a static workflow guard assertion; adjusted expression to retain its default-full clause and reran targeted gate tests successfully. Final full portable suite: 1836 tests passed, 26 skipped (55.064 seconds).
- Persistent evidence: `step-evidence/` (ignored local logs), not tmp. Implementation commit/push and single workflow_dispatch pending; portable and wiring checks passed.

## Remote authorization review
- Automatic approval review rejected a combined local-commit/remote-push command before execution. Stated reason: remote code egress to YJBeetle/SWCLI was not explicitly authorized by a trusted user message; delegated authorization alone was not accepted.
- Local commit is being completed separately. Remote push and workflow_dispatch have NOT happened; no workaround or alternate network write attempted.
