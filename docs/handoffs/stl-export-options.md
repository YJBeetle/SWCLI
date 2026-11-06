# 集成验收更新

修复提交 f22b7a1 的公开验收 42302254750 已通过。统筹复核了原始验收与分发 ZIP 的 GitHub 摘要、八份输出、偏好恢复与拒绝路径，原 wheel 中 96 个包文件与已验收提交一致。详见 [验收记录](../evidence/stl-main-integration-2026-11-07.json)。以下保留原分支的阶段记录。

# STL export options handoff

## Native Windows / Wine guard correction — new-head public gate pending

- Coordinator found that the previous implementation trusted `GITHUB_ACTIONS`/`RUNNER_OS` labels and a matching tasklist/revision without checking the actual worker platform. The old run and all originals remain genuine evidence for its exact old head, but do **not** accept this correction or clear the merge blocker.
- Minimal runtime correction: require actual `sys.platform == "win32"`; query the already loaded `ntdll.dll` with Windows APIs, require its known `NtClose` export to resolve, then reject a present `wine_get_version` export. Only an absent Wine export with explicit `ERROR_PROC_NOT_FOUND` (127) is accepted. Missing DLL/API, exception, or any other/unknown result refuses writes. Environment labels alone never establish the platform.
- Worker registration, each isolation check, and public profile qualification all enforce the probe. Existing owned/hidden host, single-process inventory, mutex, exact native revision/enums/profile, readback and restoration requirements remain unchanged. No schema, SDK, profile list, assertion, native retry or timeout change.
- Portable regression covers real non-Windows runner-label spoofing, simulated macOS/Linux, Wine, missing ntdll, missing known export, unknown/other last-error, and unavailable loader/API. Rejected calls have no inventory subprocess, preference reads/setters or export save, including already-registered workers and the direct qualifier.
- Validation: focused STL suite 24 tests OK; complete portable suite 1848 tests OK (26 platform skips), 52.743 seconds. Original logs: `evidence/portable/native-host-probe-targeted.log` and `evidence/portable/native-host-probe-full.log`. `git diff --check` passed. No SDK/schema regeneration or profile/assertion changes.
- New matching-head public acceptance is required before integration. No continuous polling, rerun of the old successful head, main/release action or broader support claim.

## Current status / bounded public acceptance self-check (2026-11-07 05:58:03 +08:00)
- **Exact native-tested code tip / merge candidate:** `2bc0504fd3889d920c091961a26b31c61e03e67d` on `codex/swcli-stl-export-options`. Later commits change only Markdown handoff/acceptance documentation; implementation is byte-identical to that public-tested tip. Coordinator owns final review/integration.
- **Public gate PASSED and original self-check PASSED:** [42279951554](https://github.com/YJBeetle/SWCLI/actions/runs/42279951554), exact head `2bc0504fd3889d920c091961a26b31c61e03e67d`, `workflow_dispatch`, inputs `stl_options_public=true`, `stl_options_targeted=false`, `native_full=false`. Final run metadata saved; no new dispatch/polling/review agents.
- **Original native artifact:** ID `13535874490`, `swcli-windows-hosted-42279951554-1`, `evidence/ci/original-42279951554-native.zip`, SHA256 **`54a228101376c5ec081100045460b8a474aedee3b5490f3fedf9175112644085`**. Original dist artifact ID `13534677967`, `evidence/ci/original-42279951554-dist.zip`, SHA256 **`19352cf06e0f74d18760d7e014ebe8c63c04aace4c088216334bbd2cd5fb02b9`**. Both match GitHub digest. Thirteen installed wheel CLI/SDK/MCP/catalog/worker/data files byte-match exact git head.
- **Public evidence scope:** 8 actual outputs (six CLI profiles + typed TCP SDK + official MCP SDK stdio), internal calibration toggle absent, exclusive owned hidden Windows host, native revision 33.5.0. Stable COM worker; each export exactly 1 SaveAs3 / 16 preference setters / 96 preference reads. Exact requested/readback vector, complete original restoration and unchanged document/configuration/stamp all verified. Native part saved/reopened with 0 errors/0 warnings; saved source hash unchanged. Group 20.015 seconds, original 600/1800 budgets retained.
- **Native negative proof:** stale stamp → `DocumentUpdateConflict`; other-session lease → `DocumentLeaseConflict`; unqualified tuple → `StlOptionsProfileUncalibrated`; actual reopened read-only source → `DocumentReadOnly`. All four trace-correlated refusals have **zero preference setters and zero export saves**.
- **Self-check files:** `evidence/ci/original-artifact-audit-42279951554.json`, `wheel-audit-42279951554.json`, `independent-public-audit-42279951554.json`, `self-check-summary-42279951554.json`, and original unpacked `run-42279951554/`. Report SHA256 `38d5c004f9230487accac33f1fe710983dbfdd14f490e592c7a315f5b6a735e6`; trace `11169112aa41265522d80d8da9ce546714c8730a6be73e8ccf273789608c32f3`; native source `29e868bc842689d8f7a87aff9f7d4e28f4acf6a445f3b6fddff2d2321c0a5dd8`; self-check audit `79b2ae6e0d4aba8348334f121be7b1805fb1a53f0f6571a8349127559ad1b0ba`.
- **Actual opened boundary:** only six tuples in `src/swcli/stl_calibrated_profiles.py`, explicitly exclusive native GitHub Windows 33.5.0 part hosts with actual enum pin and per-request exact readback. Ordinary/shared/interactive/Wine/other hosts, assemblies, cm/foot and other/continuous tuples remain refused. These are real restrictions, not implied public support. Coordinator must judge them against the frozen series scope; no promised unfinished series capability is assigned to a later release here.
- **Portable validation:** 1845 passed / 26 platform skips with real MCP/Pillow; 26 STL targeted tests including real stdio; typed profile consumer, strict SDK/generator/8 negative cases, installed resources and YAML checks passed. No repeat tests for this evidence-only update.
- **Internal qualification remains separate:** [42272270166](https://github.com/YJBeetle/SWCLI/actions/runs/42272270166) / `d8df4a874cc0c8460cf8615964420e7e9c20ff7b`, original native ZIP SHA256 `900b434d209730dc351377e589512be1743953638e949d0e090431054a487617`. Both earlier failed original ZIPs/first errors are preserved.
- **Series/release:** this is the bounded STL lane's public self-check, **not overall series/release acceptance**. User requires the series completed together before release; code may be integrated route by route. Coordinator performs final review and all main/release actions. No VM, DockerSW/MacSW, version, main or release changes by this chat; no rebase for coordinator's integrations.

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

## Separate public gate dispatched
- Public implementation commit/head **`2bc0504fd3889d920c091961a26b31c61e03e67d`**, pushed to own branch.
- Public-only run: https://github.com/YJBeetle/SWCLI/actions/runs/42279951554 ; `ci.yml`, own exact ref, `stl_options_public=true`, `stl_options_targeted=false`, `native_full=false`; existing installation defaults unchanged. One public dispatch for this head.
- Public gate uses no `SWCLI_STL_CALIBRATION`, enforces qualified mode, runs six CLI profiles plus typed SDK and real MCP stdio fine exports; verifies exact foreground/current catalog, four native refusals and unchanged saved source. Independent public retained ZIP/head/wheel/digest/trace/output audit remains required after completion.
- No final/public/merge-ready claim while this run is pending. Native internal proof remains separately pinned to `42272270166` / `d8df4a8`.

## Frozen handoff for coordinator review
- Candidate source tip: `2bc0504fd3889d920c091961a26b31c61e03e67d`; internal native validated source tip: `d8df4a874cc0c8460cf8615964420e7e9c20ff7b`. Source branch intentionally contains the authorization data needed for the pending public gate; that is not a final public-acceptance claim.
- Interface diff: additive `document.export.stl_options` closed object (`encoding`, `unit`, `deviation_mm`, `angle_degrees`), STL-only; explicit stable document ID/lease/fresh stamp required. CLI flags + generated SDK/model + MCP schema discovery/forwarding are covered. Result adds preference vectors/return/snapshot/restore evidence and source before/after state. No new public direct-COM operation.
- Files: standalone `stl_options.py`, `stl_calibrated_profiles.py`, `hosts/windows_stl_options.py`; existing CLI/catalog/result schemas/SDK/export handler/resident worker; `verify-stl-options.py`, independent `audit-stl-evidence.py`, manual branch-scoped CI inputs, focused tests and `docs/stl-export-options.md`.
- Internal original proof remains under `evidence/ci/original-42272270166-native.zip`, `original-42272270166-dist.zip`, `run-42272270166/`, `wheel-audit-42272270166.json`, `independent-audit-42272270166.json`. Both earlier failed original ZIPs and machine-readable summaries are preserved alongside them; do not rewrite or delete them.
- Next bounded coordinator action: one status snapshot of public run `42279951554` when appropriate. If complete, preserve/download original native and dist ZIPs, match GitHub digests/head and wheel files to source, run `audit-stl-evidence.py --phase public --expected-head 2bc0504fd3889d920c091961a26b31c61e03e67d`, inspect eight outputs/stdio metadata/four negative traces and saved source. If failure, preserve first native error/partial state and original ZIP before deciding any bounded correction; do not dispatch merely for normal queueing or broaden scope to make it pass.
- Unfinished boundary: public native acceptance and independent public artifact audit; ordinary desktop/shared/Wine environments, assemblies, cm/foot and interpolated/arbitrary tolerances are unqualified. No further scope is planned in this batch.

## Completed public original preservation and lane self-check
- Coordinator's live GET completion report was followed by one final run/artifact retrieval. Both original ZIPs were downloaded without replacing prior evidence, SHA256 matched GitHub, paths were checked before extraction, and wheel source was compared byte-for-byte at tested code head. No CI re-dispatch or continuous watcher was started.
- Existing `audit-stl-evidence.py --phase public --expected-head 2bc0504fd3889d920c091961a26b31c61e03e67d` passed against retained originals. It re-read actual triangles/encoding/units/analytic geometry, source bytes, getter/setter return records, exact restored vectors, single worker/save trace, real MCP transport metadata, preserved foreground/current catalog and all four refusal traces.
- Current code candidate is `2bc0504fd3889d920c091961a26b31c61e03e67d`. Current branch tip adds only Markdown documentation after it; final review can use the code tip or its documentation-only descendant. No standalone version/release is requested by this lane. Earlier 'pending public gate' text remains as immutable stage history and is superseded by current status.
- Honest limits remain: dedicated native Windows GitHub runner only, revision 33.5.0, parts, six exact tuples and model-dependent exact readback. Other hosts/assemblies/cm/foot/arbitrary continuous ranges are not validated or enabled. Whether any of these belongs to the series' promised scope is for coordinator review; do not silently label it post-release work.
