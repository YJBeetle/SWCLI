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

## Corrected native calibration dispatched
- Fix commit `bcad03abcb3e6cc15e8dbabd0c04e506f086979c` pushed; 19 targeted tests + 42 result/SDK/default mesh/operation regressions passed, SDK generator/strict typing passed.
- Run https://github.com/YJBeetle/SWCLI/actions/runs/42266554774 ; `ci.yml`, same branch/ref, `stl_options_targeted=true`, `native_full=false`, existing other defaults. One dispatch for this corrected HEAD, after actual first-failure fix; no queue-based rerun, no other run cancelled.
- First failed run and all original bytes/digests remain retained. Runtime public writes remain disabled. Public gate scaffold is now committed but deliberately cannot run until audited native qualification and exact runtime policy are implemented.

- Prepared (uncommitted) separate default-off `stl_options_public` manual workflow input and installed CLI/SDK/MCP public step, unique `swcli-stl-options-public-${github.ref}` concurrency. Mutually exclusive modes are checked before private setup; default full/release condition/group is retained. No public dispatch yet and no runtime qualification/profile list has been created.

- Prepared (uncommitted) public runtime enforcement: single explicit internal/public runner mode; no shared/visible/unobserved identity; parts only; exact option tuple + native revision + installed enum vector pinned to an audited qualification module. That module does not exist yet, so public mode still refuses all STL preference writes. Added policy tests for missing qualification, unproven tuple, assembly, wrong revision/enum and ambiguous opt-in. Explicit `active` selector is refused for option writes; a stable `d-...` ID is required.

## Second native failure / exact native point correction
- Run `42266554774`, head `bcad03abcb3e6cc15e8dbabd0c04e506f086979c`, failed at full readback before any STL SaveAs3. Native app setter evidence confirms integer/double `bool true`, toggle `NoneType/null` as documented. The void fix is evidenced, not assumed.
- Original ZIP `evidence/ci/original-42266554774.zip`, SHA256 **`2fdb447d3649dc44865d80277f0588fef03c2a353c7816b0620fe7ceee5fe8d1`**, matched GitHub artifact digest. Machine-readable failure summary retains report/trace/source digests.
- Only mismatch: requested `swSTLDeviation=0.0005 m`, native readback **`0.0005335936864527374 m`**. Angle and all other requested settings retained exactly. Full original preference vector restored exactly, cleanup errors empty, source stamp/configuration/modified state unchanged. Zero native export calls.
- No assertion was loosened. `0.5 mm` remains rejected when native normalizes it. Added a portable reproduction asserting this refusal/restoration.
- Corrected internal sample requests use explicit observed native deviation points: coarse **`0.5335936864527374 mm`**, fine **`0.015392125570752039 mm`** (the preexisting native value that the same run restored exactly); SI conversion of both round-trips exactly. Coarse angle 30 degrees is already exactly retained; next explicit fine angle request is 10 degrees. All original independent-deviation/angle A/B triangle, geometric-error, unit/encoding, source and exact-readback assertions remain.
- No native or public acceptance claimed yet. New public runtime/gate preparation remains missing its audited qualification data, so all public writes remain closed.

- Added per-set full preference snapshots (read-only diagnostics under the same mutex) so any remaining normalization/coupling can be attributed to its exact setter. The final exact vector barrier, restore verification and one-save rule remain unchanged; successful trace now requires 16 setter calls and 96 preference reads (8 original + 8 CAS + 64 intermediate + 8 final + 8 restored).
- Complete local portable suite after public-policy and sample corrections: **1843 tests passed, 32 skips**; SDK typing/generator and workflow YAML checks passed. The public qualification data is still absent; this is not merge-ready/public accepted.
