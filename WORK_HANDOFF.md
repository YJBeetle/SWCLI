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

## Commit / dispatched native calibration
- Implementation commit: `ff7f66bab0403a5b4e3dd7f6f0155ad56595eeda` (Chinese feature commit), pushed to origin/codex/swcli-step-export-options after the user explicitly approved this exact destination/head/payload and one dispatch.
- Single internal calibration run: https://github.com/YJBeetle/SWCLI/actions/runs/42262507658
- Event/head: workflow_dispatch / ff7f66bab0403a5b4e3dd7f6f0155ad56595eeda; inputs native_step_targeted=true, native_full=false; other workflow defaults.
- Initial state: portable/package jobs queued. Native calibration and output/save-reopen evidence remain unproven. Raw dispatch metadata: step-evidence/dispatch.json.
- Coordinator follow-up accepted: internal evidence alone is insufficient. After success, independently verify original artifact/head/digest/trace/save-reopen, then open only the exact proven range and add public CLI/daemon native acceptance plus SDK/MCP contract checks. Not merge-ready; no main merge/release.

## Public acceptance preparation (uncommitted; no second dispatch)
- Coordinator requires eventual merge-ready public proof. Prepared `verify-step-export-public.py`: one daemon-owned hidden host; public CLI exports six combinations, plus SDK and MCP bridge exports; CAS/foreign lease/illegal protocol/readonly rejection; native source close/read-only reopen/analytic measure; SHA256 and raw CLI/daemon traces; explicit host-process exit.
- Prepared separate `--export-report` output-readback mode in the native script. It refuses a mismatched public output digest, then imports the actual public files, verifies analytic geometry, native save/read-only reopen, and original STEP/native file hashes. These are two explicit groups (public writer, independent output observer), each owns one host and has no failure retry/replacement.
- Added default-off, dedicated-branch/manual-only `native_step_public_targeted` CI profile with a distinct public-profile+ref concurrency group. No public profile has run. Public revision allowlist is STILL empty pending original internal artifacts.
- Preparation verification: 19 STEP/offline harness tests pass; default-full guard tests and YAML parse pass. These additional uncommitted files were not part of ff7f66b or run 42262507658.
- Run 42262507658: Build wheel and Windows Python 3.9/3.14 jobs passed; native STEP job is queued for GitHub quota. No cancellation or duplicate dispatch.

## First native result: failed, original evidence retained
- Run 42262507658 / head ff7f66bab0403a5b4e3dd7f6f0155ad56595eeda completed failure at the first AP203/solid-surface case; no second case started, no retry/restart. Installer and cleanup completed. Not merge-ready and public allowlist remains empty.
- Original evidence ZIP: `step-evidence/internal-original-42262507658.zip`, artifact ID 13527496084. SHA256 `fe4470212b224bb965afd9ae77e8b5d96918dbc637526cd5df4cbc316ae877c6` exactly matches GitHub digest.
- Official installed SwConst: swStepAP=75, swStepExportPreference=142; solid/surface=0, wireframe=1, wireframe+sketches=2. Owned hidden host revision 33.5.0.
- AP203 output header CONFIG_CONTROL_DESIGN, size 16070, STEP SHA256 `4024956fff86d9aa261d6d17a288d323506a78ba69317abf8140421dc3631997`. Export, source readonly reopen, STEP import, imported native save and readonly reopen all returned success. Pref snapshot 203/0 restored 203/0; this first case did not exercise changing either preference.
- First failure is raw equality of the complete measurement dictionaries: volume/area identical; centroid Y changed from 7.72035238382826e-17 to -1.9852334701272667e-16 mm. Original report/trace/logs and native/STEP files extracted; independent audit `step-evidence/internal-audit.json`.
- Because the user explicitly prohibits relaxing assertions, prepared but DID NOT APPLY `step-evidence/proposed-numeric-readback.patch`. Proposal keeps exact body/segment topology, existing analytic volume/area/total-length tolerances (rel 1e-7, abs 1e-5), and adds analytic/pairwise centroid and per-segment 1e-9 mm bounds instead of bitwise float dictionary equality. Needs explicit user decision before replacing the assertion or rerunning. No public whitelist promotion from this failed run.


## Approved diagnostic correction / second internal head preparation
- User explicitly approved `proposed-numeric-readback.patch` and authorized pushing the correction, public acceptance scripts/isolated CI profile, diagnostics, documentation/tests to YJBeetle/SWCLI/codex/swcli-step-export-options; each repaired head gets only one necessary internal/public dispatch. Failed original evidence must be retained; only substantive fixes justify another run.
- Applied the approved physical-comparison correction: exact topology/method/schema; existing analytic volume/area/total-length thresholds unchanged; analytic and pairwise centroid/per-segment bounds 1e-9 mm. Added portable refusal tests for actual centroid, volume, area, topology and wire-length changes/nonfinite values.
- Additional public-phase preparation includes explicit native SaveAs3 attempted/possible-mutation flags and trace boundaries, fail-closed unknown original preferences, native input type-library SHA256/head identity. Public revision allowlist remains empty.
- Preparing a new commit and a single internal dispatch on that new head after portable/wiring checks. No public acceptance or whitelist promotion yet.
- Approved repair verification: full portable suite 1841 tests passed, 26 skipped (55.311 seconds); STEP/offline harness tests 22 passed; SDK generator/strict typing and 10 negative consumer fixtures passed; Python compilation/YAML and full/default CI guard tests passed. Logs in step-evidence/portable-second-head.log and sdk-types-second-head.log.
