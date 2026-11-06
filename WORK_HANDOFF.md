# STL export options handoff

## Current status (2026-11-07)
- Internal native qualification **passed and independently audited**: run `42272270166`, code head `d8df4a874cc0c8460cf8615964420e7e9c20ff7b`. Original native/dist ZIP digests, installed wheel source-byte match, native part save/reopen, actual STL triangle/geometry/unit/encoding and per-request 1 save / 16 setters / 96 preference reads all verified.
- Exact six tuples are pinned in `src/swcli/stl_calibrated_profiles.py` and discoverable in schema `x-swcli-qualified-stl`. Enabled only for explicit exclusive native GitHub Windows 33.5.0 hidden owned workers and parts; others remain fail closed.
- Separate public CLI/TCP SDK/real MCP stdio gate is prepared; public CI and independent public audit are still required. **Not yet public accepted / merge-ready.**
- No permission/automatic-review blocker. No VM, DockerSW/MacSW, main, version or release changes. Coordinator owns final main integration.

The sections below retain stage history and the two original failures; later status supersedes earlier proposals without rewriting original evidence.

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

## Third internal calibration dispatched after native-point correction
- Commit/head `d8df4a874cc0c8460cf8615964420e7e9c20ff7b` pushed.
- Run https://github.com/YJBeetle/SWCLI/actions/runs/42272270166 ; exact own branch, `stl_options_targeted=true`, `stl_options_public=false`, `native_full=false`; no defaults, permissions, other branches or runs changed.
- This is one run for a changed sample/backend evidence head after two retained first-failure corrections; it is not a retry for queueing or a retry inside native code. Both failed original ZIPs/digests and first errors remain persistent.
- Public/merge-ready status remains **not accepted** until exact native outputs and independent audit, then separate public gate evidence are complete.

## Coordinator authorization refresh
- Coordinator relayed explicit user authorization to continue branch implementation, Chinese commits/push, targeted native calibration and separate public acceptance; independently verified precise capabilities may be enabled on this branch for the public gate. Main integration remains coordinator-owned.
- No authorization action is currently pending. No automatic approval rejection has occurred. No VM/DockerSW/MacSW action or credential output is needed. Continue the existing third run; do not repeat solved authorization steps or dispatch for normal queueing.

## Internal native acceptance independently audited (exact bounded scope)
- **Passed internal run:** https://github.com/YJBeetle/SWCLI/actions/runs/42272270166; head **`d8df4a874cc0c8460cf8615964420e7e9c20ff7b`**, all portable/package/native jobs succeeded. This is internal qualification, not default full/release or public acceptance.
- Native original ZIP SHA256 **`900b434d209730dc351377e589512be1743953638e949d0e090431054a487617`**, dist ZIP **`d0b4d09f305787977e578af085043a49a2bae4baddd96c502ef6fe60312b390f`**, each matched GitHub digest. Installed wheel copies of six backend/catalog/worker files were byte-compared with git objects at the exact head; all matched.
- Report SHA256 **`7a78f8e642e771e1737016ec0ff210c0f46b15eba1f4091750e9a5f9ff5989d3`**; trace **`754a2fe537a836d751f0377d308cff087d9be81b4ea3ceb118b1c69d31296099`**; saved/reopened native source **`07c0450bc74de4af0677f5e3210b4a06801dd764b3b8151e9f6dcb9998aa997a`**. Persistent original archives/unpacked files, wheel audit and independent audit JSON are under `evidence/ci/`.
- Native Windows 33.5.0 / owned hidden host / one stable COM worker. Each of six exports has one SaveAs3, 16 setters with correct void/bool return values and 96 preference reads. Exact requested/readback vectors, exact restored vector, source stamp/configuration/state and saved-file digest all verified.
- Curve results: coarse 48 triangles / max chord 0.3407421 mm / volume relative error 0.04507036; deviation-fine and fine 232 / 0.0151856 mm / 0.00199731; angle-fine 144 / 0.0380535 mm / 0.00506920. ASCII inch and binary meter both 232, scaled geometry matches fine.
- Opened only those six exact parameter tuples on explicitly opted-in exclusive native GitHub Windows 33.5.0 part hosts, pinned to actual enum vector. Other values, cm/foot, assemblies, ordinary/shared/interactive/Wine/other hosts remain refused. Every request still verifies exact native readback; model-dependent normalization is never accepted as requested.
- Qualification data in `src/swcli/stl_calibrated_profiles.py` was created only after the passing original artifact and independent audit. `x-swcli-qualified-stl` advertises exact profiles and conditional availability across protocol/SDK/MCP discovery.
- Next required stage: installed public CLI/daemon/SDK/MCP gate with internal toggle removed, then independent audit. **Not yet public accepted or merge-ready.**

- Strengthened the pending public gate to cross the actual official MCP SDK stdio transport (`initialize`, tool discovery, `execute`, matching structured/text receipts), not merely call `DaemonBridge` internally. A portable real-stdio test verifies the exact qualified tuple/lease/stamp/session reaches the TCP endpoint once and never starts/stops native lifecycle. Public-only CI step installs the existing declared MCP optional dependencies; default/internal/full gates are unchanged.

## Public gate pre-dispatch checks complete
- Complete local suite with real optional MCP/Pillow dependencies: **1845 passed, 26 platform skips**, 60.324 seconds.
- Targeted STL / actual MCP stdio suite: **26 passed**. Native tuple data has a typed SDK consumer example; generator/strict typing/8 negative consumer cases passed. Installed CLI/schema/product skill and workflow YAML checks passed; `git diff --check` clean.
- Public code/data remains bounded to internally audited six exact tuples and explicit exclusive Windows runner/part/native revision/enum mapping. Ready to commit/push this public-gate head and dispatch public-only once; no final/public acceptance claim yet.
