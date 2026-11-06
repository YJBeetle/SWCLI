# Table defaults branch handoff

- Worktree: `/Users/YJBeetle/.codex/worktrees/docprops-table-defaults/SWCLI`
- Branch: `codex/docprops-table-defaults`
- Baseline: `3bda2c00489dde6a3d1e4521c548f751b1d1c197` (clean at start).
- Scope: five non-font defaults: template-settings toggle; BOM/general box and grid border weights. BOM/template settings cover part/assembly/drawing; General defaults are drawing-only per official docs. No table insertion/object editing.
- Public write status: **fail closed pending internal evidence**. `_CALIBRATED_PROFILES` is empty. Per the coordinator’s latest instruction, this branch must continue through public CLI/daemon acceptance and required SDK/MCP contracts before claiming merge-ready; it will not stop at an empty-whitelist candidate.
- No VM, local SOLIDWORKS, DockerSW pointers/branches/CI/images, MacSW, main merge or release touched.

## Interfaces

- `document.table-options` / `swcli document table-options`: returns complete `options` map of `{value,native_value}` or `{unavailable:"document_type"}`.
- `document.table-option-set` / `swcli document table-option-set`: `field`, typed `value`, full `expected_options`; required envelope `document_id`, `expected_update_stamp`, `lease_id`.
- CLI write uses `--document`, `--if-update-stamp`, `--lease`, `--if-options-json`.
- SDK `client.document.table_options()` / `table_option_set(...)`; MCP uses generic execute and catalog discovery.
- Setter receipt: `mutation.attempted`, `mutation.may_have_changed`; single setter; no retry/rollback/restart.

## Shared files changed for integration

- `src/swcli/operation_schemas.py`: two catalog entries, full snapshot validation, lease-guard classification for required write tokens (lease lifecycle operations remain excluded).
- `src/swcli/result_schemas.py`: two result shapes and scalar/applicability/lifecycle validation.
- `src/swcli/daemon/operations.py`: two handlers/imports.
- `src/swcli/cli.py`: two document subcommands.
- `src/swcli/sdk/_generated.py`, `src/swcli/sdk/models.py`: regenerated; regenerate after integrating schemas rather than merging generated conflicts manually.
- `.github/workflows/ci.yml`: default-off exact-branch/head `table_defaults_calibration` input/job; `table_defaults_head`; portable/package jobs skip only this manual calibration mode. Existing full/release guards remain intact; no PR secret trigger added.

## New files

- `src/swcli/document_tables.py`, `src/swcli/hosts/windows_document_tables.py`.
- `tests/test_document_tables.py`, `tests/test_table_defaults_calibration.py`.
- `scripts/ci/verify-table-defaults-calibration.py`, `scripts/ci/windows/calibrate-table-defaults.ps1`.
- `docs/design/document-table-defaults.md` (official source links, boundaries and protocol examples).
- Persistent original logs/artifacts: `docs/verification/table-defaults-evidence/` (ignored except its local .gitignore).

## Tests, commits and CI

- Focused 27 tests: pass, 1 platform skip. Includes related existing modeling-sequence release-policy tests.
- SDK generator + strict mypy + 8 negative consumer typing checks: pass.
- Full installed portable suite: **1834 tests passed, 32 skipped** (local Python 3.15). Final targeted suite after adding raw Boolean setter receipts: **56 passed**. First pre-install attempt had an isolated-import environment failure; next caught workflow job placement, fixed before final pass. These were not native failures.
- Installed resources and workflow YAML/events/exact-head/default-off routing: passed. Original local logs are in the persistent evidence directory.
- Official Toggle setter return wording is ambiguous relative to existing annotation calibration; new table setter records `native_returned`, and `False` fails closed without retry.
- Windows PowerShell syntax validation on `8ca545c`: passed in Windows Python 3.14 ordinary push CI; Python 3.9 and packaging also passed.
- Native calibration dispatched **once**: https://github.com/YJBeetle/SWCLI/actions/runs/42261481759 ; head `8ca545c8edc707fedbf5669934aed247ab905b91`. Parameters: `native_full=false`, `table_defaults_calibration=true`, `table_defaults_head=8ca545c8edc707fedbf5669934aed247ab905b91`. Result: **failed before any table preference getter/setter**. First failure: pywin32 exposes `GetExecutablePath` as a string property, while the candidate called it; `TypeError: str object is not callable`. Owned-host cleanup completed without errors. No geometry/state assertion was relaxed.
- Native limits: 600 seconds per bounded call, 1800 seconds per group. One owned host; part/assembly/drawing; first failure stops. Original report/native trace uploaded separately, `full_acceptance_eligible=false`.
- Implementation commit pushed: `df3fa41bac6073e308c93323c210a571228ce2a6`.
- Ordinary push CI on calibration head: https://github.com/YJBeetle/SWCLI/actions/runs/42261450305 (head `8ca545c`, **success**). Earlier implementation push: https://github.com/YJBeetle/SWCLI/actions/runs/42261249216 (head `df3fa41`).
- Artifact-scope tightening commit pushed: `8ca545c8edc707fedbf5669934aed247ab905b91`; focused calibration/release-policy tests passed.
- First dispatch command was **not executed**: automatic approval review rejected private-runtime/artifact disclosure as insufficiently established. Upload scope is now narrowed to `swcli-native-smoke/table-defaults/` only: generated fixture documents, report and traces; no installer/runtime/config/credential paths. The safer upload boundary passed targeted revalidation and automatic approval. The subsequent single dispatch succeeded; its result is pending.
- Remote ownership verified: public `YJBeetle/SWCLI`, authenticated account `YJBeetle`, permission ADMIN. Initial push review rejection was resolved by this read-only ownership check; the later push succeeded.

## Remaining integration/acceptance boundaries

- Public setters remain closed even after an internal native pass; native end-to-end public CLI/daemon acceptance and profile review are separate work.
- General defaults are intentionally unavailable on part/assembly even if a native getter happens to return an integer.
- Constants are read by exact names from the owning installation's official `swconst.tlb`; no numeric IDs are guessed or copied from unverified worktrees.
- No dependencies on other task branches. Internal calibration reuses the baseline owned-host/annotation fixture harness; changes to those shared harnesses must preserve its contracts.

## Public acceptance preparation (in progress, not merge-ready)

- New uncommitted `scripts/ci/verify-table-defaults-public.py` and `scripts/ci/windows/accept-table-defaults.ps1`: one owned hidden daemon, CLI→daemon→worker writes, native per-request trace/count/order checks, full CAS/lease/stamp/no-op/readonly cases, original fixture digest checks, save/reopen and analytic geometry; SDK and MCP bridge checks use the same real daemon.
- New uncommitted `tests/test_table_defaults_public.py`: SDK/MCP exact snapshot/context forwarding, trace corruption/reorder/extra setter/global preference rejection and pre-adapter refusal handling; initial targeted checks passed.
- Opening is still conditional on downloading and independently verifying the internal run’s original ZIP, GitHub artifact digest, head, report/trace and saved-reopen fixture hashes. Only proven version/type/field/value scope may be promoted; public acceptance will need its own exact-head CI run.

## First native failure and related fix

- Preserved original ZIP: `docs/verification/table-defaults-evidence/run-42261481759/original.zip`.
- GitHub artifact ID `13527120695`, name `table-defaults-internal-42261481759-1`.
- Original ZIP/GitHub digest verified equal: `sha256:a482eb9aed4184ed6a6150130894dc8b29a3717c1d44d3bfaf4139181eb49375`.
- Report SHA256 `afb23a5832c588778117ca30d562b8f0029cad9bd5926132dab2e73730412d5c`; harness trace `45fc6b9acbc0da4249e485c1e8eb63b090ea829621932c874a3dbc4d5d8f2952`; native trace `8fdbdb893b8bab2db75dfe3acbfc9ba09275d0f8b60158d9c3fb0d1037661526`.
- Actual source fix: use existing `_com_value(app, "GetExecutablePath")` once, supporting either pywin32 property or method. New property/method tests verify one read/no retry.
- Baseline analytic fixture preparation temporarily disables/restores sketch inference (two known pre-table calls). No table preference setter ran before failure. Independent auditing separates this existing owned-fixture behavior from table operations and validates nested trace frames.
- A related-fix internal calibration run will be needed on the next pushed head; it has not been dispatched yet. Public acceptance remains blocked on clean audited internal evidence.
- Public preparation now includes exact version/type/field/(before raw, after raw) transition admission, still **empty**. Unproved values, directions, revisions and types remain closed. The public mode checks pinned remote artifact provenance and independent local report/trace/fixture hashes before preparing private runtime inputs; it uses dedicated table concurrency, not full/release concurrency.

- Related-fix preflight: **65 focused tests passed, 3 optional MCP/platform skips**; SDK generation/strict types/8 negative consumers passed. No repeated full suite was run for coordinator messages.
