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
