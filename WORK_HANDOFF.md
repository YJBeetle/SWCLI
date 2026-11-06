# STL export options handoff

## Scope / interface proposal (2026-11-07)
- Worktree `/Users/YJBeetle/.codex/worktrees/swcli-stl-export-options/SWCLI`; branch `codex/swcli-stl-export-options`; clean baseline `3bda2c00489dde6a3d1e4521c548f751b1d1c197`.
- No `.codegraph/` exists. No local VM use. No edits to DockerSW, MacSW, other worktrees, version or release gates.
- Proposed `document.export.parameters.stl_options`: closed object with `encoding` (`binary`/`ascii`), `unit` (`mm`/`cm`/`m`/`inch`/`foot`), `deviation_mm`, `angle_degrees`. Only STL output accepts it. No GLB semantics.
- Official mapping: ISldWorks Get/SetUserPreferenceToggle(swSTLBinaryFormat), IntegerValue(swExportStlUnits/swSTLQuality), DoubleValue(swSTLDeviation/swSTLAngleTolerance). Exact constants must come from installed swconst.tlb at calibration; tolerances need readback and actual curved-output evidence.
- Shared interfaces potentially touched: operation_schemas.py, cli.py, daemon/operations.py, daemon/server.py, generated SDK, ci.yml. Coordinate conflicts before integration; no cross-worktree edits.
- Safety proposal: public options fail closed pending calibration. Calibration only on a disposable isolated Windows runner with a worker-owned SOLIDWORKS process, never shared-interactive attach; serialized worker + OS named mutex, snapshot all preferences before writes, exact set/readback, one export, finally restore/readback. Preserve first native error and cleanup errors separately. No CAD rollback or retry.

## Evidence / status
- Inventory complete; implementation / portable tests / native evidence pending.
- Official source: https://help.solidworks.com/2019/english/api/swconst/filesaveasstloptions.htm
- CI run/head/parameters: none yet. No public/native acceptance claimed.

## Implementation phase / coordination update
- STL-specific four-field closed request object is wired CLI -> protocol -> daemon -> worker, generated SDK and MCP forwarding.
- Product bounds: deviation 0.01..1.0 mm, angle 0.5..30 degrees; converted to meters/radians under official default API unit convention. These are SWCLI bounds, not claimed full native limits.
- Constants resolved by exact names from installed swconst.tlb; no guessed integer enum IDs.
- Calibration-only global transaction requires worker-owned hidden app on explicit disposable GitHub runner, exact-one SLDWORKS process inventory, named OS mutex, full-vector snapshot/CAS/readback, single SaveAs3, full finally restoration and readback. Unknown restoration retires worker. Source identity/stamp/configuration and partial-state observations are retained; no document rollback or native retry.
- Parent reported cross-branch cancellation in shared native concurrency. This branch now uses `swcli-stl-options-${github.ref}` only for explicit targeted input; existing default full/release group remains `swcli-hosted-windows-solidworks`, `cancel-in-progress: false`.
- Initial portable full run: 1831 tests, 32 skips, one summary-wiring failure found and fixed without weakening existing assertion. New source-finally placement regression was caught by targeted test and fixed before dispatch. Final rerun pending.
- Native run: not dispatched yet. Public STL option writes remain fail closed; internal calibration is not public/full acceptance.

## Portable verification complete
- Final complete suite: **1833 tests passed, 32 platform/optional-dependency skips**, 47.952 seconds; persistent `evidence/portable/unittest-final.log`.
- Targeted STL suite: 14 passed. Existing summary suite: 22 passed. SDK generator/strict mypy/8 consumer refusals passed; installed CLI/schema/product-skill check passed without COM; workflow YAML parsed; `git diff --check` passed.
- Logs under `evidence/portable/` remain local persistent artifacts, excluded from source commits by `evidence/.gitignore`.
- Implementation files: `stl_options.py`, `hosts/windows_stl_options.py`, existing export adapter/handler/worker, CLI/catalog/result schemas/generated SDK, dedicated verifier/tests, documentation and explicitly gated manual CI input.
- Next authorized stage: Chinese implementation commit and push this branch, then one `workflow_dispatch` of `ci.yml` with `stl_options_targeted=true`, `native_full=false` against the matching branch HEAD. No local VM, main merge or release.

## Native dispatch (one authorized request)
- Implementation commit / tested HEAD: `3664d4b99df98aa75d9df3aa8e252316ee602f53` (`feat: 添加隔离校准的STL格式参数与偏好恢复验证`), pushed to `codex/swcli-stl-export-options`.
- Run: https://github.com/YJBeetle/SWCLI/actions/runs/42262477609
- Workflow `ci.yml`, `workflow_dispatch`, ref `codex/swcli-stl-export-options`, inputs `stl_options_targeted=true`, `native_full=false`; existing media/assets/cleanup/cache defaults unchanged. Exactly one dispatch submitted, no other branch targeted.
- Request/response and run snapshots under persistent `evidence/ci/`. Result pending; no native or public acceptance claimed.

## Public promotion plan (after independent native evidence audit)
- Parent requires public CLI/daemon acceptance beyond an internal-only candidate. Do not call this branch merge-ready at the current stage.
- Safety boundary proposed for public promotion: explicitly configured disposable isolated GitHub Windows runner; worker-owned hidden host, exact-one SLDWORKS process, OS mutex and serialized worker remain mandatory. Ordinary/shared/interactive or non-isolated deployments continue to refuse global preference writes.
- Promote only the exact parameter tuples actually proven by retained outputs, pinned to observed native revision and installed enum mapping. Schema-wide numeric bounds must not become an unverified general write allowlist.
- Prepare a separate public gate that uses installed CLI plus SDK/MCP through the daemon, no internal-calibration toggle, verifies negative guards before setters, source/background identity, save/reopen, actual binary/ASCII/unit geometry, full preference restore and per-request single-save trace. A necessary public CI is a separate phase, not a rerun for normal queueing.
- Native audit helper `scripts/ci/audit-stl-evidence.py` is drafted locally (not part of dispatched HEAD) to independently re-read retained mesh/source bytes, digests, exact vectors, request-correlated begin/end/set/read/save trace and stable worker identity before any promotion.
- While the original native run is preparing its runner, the local verifier now has an uncommitted `--phase public` scaffold. It removes the internal calibration toggle, requires explicit isolated public mode, runs CLI plus SDK/MCP exports and native stale-stamp/foreign-lease/unproven-profile/read-only guard refusals. It remains unusable until an audited qualification file and runtime enforcement are populated from actual passing native evidence; no range has been opened or second CI dispatched.

## First native failure retained / bounded correction
- Run `42262477609` completed **failure** at the first STL case, after installation and native source save/reopen succeeded. No `SaveAs3` export call occurred. App revision `33.5.0`, owned hidden host PID 4512; source state unchanged.
- Original native artifact ID `13526159120`, ZIP `evidence/ci/original-42262477609.zip`, SHA256 **`b83b79ceb578096b3bd5db9ac8f77ebf8efbdf27bb7d50b23eaf039e9e1a32e8`**, equal to GitHub artifact digest. Saved/reopened source SHA256 **`fd7c82324a9fc13ea664c04e6c96dab709f61972e1a498eed2ff0871fac3e699`**.
- Root cause: implementation wrongly required boolean success from **ISldWorks.SetUserPreferenceToggle**, whose official signature is **void**. Original report/trace show toggle calls ended without COM exception; before/after full preference vectors are identical, although conservative status handling flagged restoration failure and retired worker.
- Correction: require `None` for app toggle setters and true for app integer/double setters; retain per-set/restore return types/values. Exact vector CAS/readback/restoration assertions, single save, 600/1800, isolated host and fail-closed public boundary are unchanged. This corrects an API return contract; it does not relax a native geometry assertion.
- Added real void-vs-boolean portable contract coverage and fixed MCP forwarding test to validate a correctly shaped swcli/v1 envelope. Next native dispatch is authorized only after this correction is committed, pushed and targeted checks pass.
