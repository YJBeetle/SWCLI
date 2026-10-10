# a7 feature observation: development verification

This is a chronological development record, **not an a7 release**. Later sections
add guarded editing proof; pending statements in earlier sections describe their
own candidates, not the latest implementation. The initial public read implementation is
`cc1ba7e5295b92e50d5f57da8e443b9d91298975`,
following registry `a13c470` and native observer `259cf34`. Package version is
`0.1.0a7.dev0`; the public a6 assets remain unchanged.

## Portable contracts

886 tests passed, with eight Windows-only tests skipped on macOS. New coverage
includes exact native feature identity/lifetime, bounded/cycle-safe traversal,
strict native flags, nonmutating state snapshots, request/result/CLI contracts,
background leased reads, update-stamp refusal and no partial wire handles.
Shared-gate tests additionally reject wrong native depth and observation drift,
and preserve holder leases during simulated slow observation groups.

## Native Windows read-only proof

SOLIDWORKS 2025 revision `33.5.0`, Windows ARM64 with AMD64 Python 3.14.7 and
pywin32 312. Explicitly shared existing SW PID **1096**; the probe did not stop
it or replace it. Test documents/files were limited to
`C:\Workspace\SWCLI-tests\a7-feature-read-FFzBLq`.

The internal probe created a 100×50×20 mm boss and a radius-3 mm, depth-5 mm
cut, then observed them with another part in the foreground. The public probe
opened only that saved test file read-only and exercised the actual CLI over TCP
against a disposable shared COM worker. Both probes passed and cleaned up their
test documents; original documents/foreground and the same SW PID were preserved.

- Native boss depth **20 mm**, type `Extrusion`; native cut depth **5 mm**,
  displayed type `ICE` with underlying type `Cut`.
- Complete unchanged configuration/edit/modified/stamp/foreground observations.
  Test part stamp **146** remained 146; reopened reads kept `modified: false`.
- Rename and repeated observations reused live handles. Close/reopen allocated
  fresh IDs; public inspection of a retired ID returned `FeatureNotFound`.
- Public capability Schema matched; stale-stamp reads returned
  `DocumentUpdateConflict`. Depth-write capability was absent.

Local raw evidence was retained under the test workspace and copied to
`/private/tmp/swcli-a7-feature-read.FFzBLq/`:

| Evidence | SHA256 |
| --- | --- |
| `feature-read.json` | `25157e1363a306c07e00aea74af22c6faadaadadb75d7485d98f4590456bb618` |
| `feature-public.json` | `1b9a6b064b28d0dda4d24ec849459c2ec6d192a664b94120dd86d00a72252ac6` |

These are local, non-hosted artifacts, not public CI attestations. The public
probe read without a write token on a leased test document; the distinct
non-holder session path is covered by portable contracts and the new shared gate.

## Still pending

- Hosted Windows execution of a future public depth setter; current public
  read/creation candidates passed independently as recorded below. Internal
  guards are not exercised merely by installing them in that candidate.
- Linux/Wine and macOS/Wine runtime proof for these new operations; older a6
  host passes do not establish a7 feature support.
- Guarded blind depth edits,
  including protected-control checks and rollback/restoration ownership.
- Formal a7 candidate, release assets and distribution verification.

No setter, automatic retry, source save, transaction rollback or host restart is
part of the feature read path.

## Hosted Windows read-only gate

[Run 37993834203](https://github.com/YJBeetle/SWCLI/actions/runs/37993834203)
passed for source `fab41582fb49d150982be63bf47fbc5209717c1b`. Unit/package jobs
and the real SOLIDWORKS modeling/export job succeeded. Its installed-wheel gate
ran SW2025 `33.5.0` with Python 3.12.10, first visible (PID **3088**), then hidden
(PID **2812**). Each mode retained its own SW process throughout modeling and
driving-dimension verification; both records completed with no cleanup errors.

The shared modeling gate verified leased background feature reads from a
distinct non-holder session, exact boss/cut depth and flags, unchanged native
state, repeated IDs, bounded-list refusal without partial results, native
save/reopen and rejection of retired feature IDs. Existing modeling, dimension,
export and host-disconnection gates also passed; assertions were not relaxed.

Artifact: `swcli-windows-hosted-37993834203-1` (ID `11647535169`).

| Generated evidence | SHA256 |
| --- | --- |
| `swcli-native-smoke/modeling/modeling.json` | `d65bd43ebb6cdb8b71d0ee418911c18be2e6ffad7671c8a80aa7be519cbbca09` |
| `swcli-native-smoke/hidden/modeling/modeling.json` | `ab8f5e7474c1e2327ca6360672818fc8331cd0c027172897c0c74f1144efa825` |

This source predates creation-result handles and preliminary depth controls.
Its pass proves neither those later candidates nor a public depth setter, Wine
delivery or an a7 release.

## Independent creation-handle proof

Native-return refactor `9da7c80` and public wiring
`5d7137320410753e6a7613cbb86e7635d2bd4839` add exact boss/cut creation handles.
The portable suite passed **898 tests**, with eight Windows-only tests skipped.
Contracts require handles on success, retain original post-creation failures,
reject invented/missing objects and verify discovery reuses creation IDs.

On the same Windows host/revision and shared SW PID **1096**, a separate probe
used actual CLI/TCP/STA-worker calls to create only two new unsaved test parts.
It created a background 100×50×20 mm boss and radius-3/depth-5 mm cut with
lease and explicit update-stamp guards. Creation IDs `f-z9p6k0`/`f-d7cd9m`
were immediately inspectable, reused by repeated lists, and rejected on the
other document with `FeatureNotFound`. Foreground/session identity was retained.
Both test documents were closed; original documents, initial foreground and SW
PID remained unchanged, with no cleanup errors.

Raw evidence: `C:\Workspace\SWCLI-tests\a7-feature-create-sisGJ3\feature-create.json`,
copied to `/private/tmp/swcli-a7-feature-create.sisGJ3/feature-create.json`.
SHA256: `607bd5a9babdd45e6d06c21b944cef3b5c3c32f37677c44cb0451db4e454530e`.
An earlier probe-harness attempt called the nonexistent `document status`; it
failed before creating any sketch/feature and cleaned up its two empty parts.
The corrected probe used `document inspect` on fresh parts, not a CAD mutation retry.

This separately proves local native creation IDs, not hosted Windows/Wine gates
or depth editing. The read-layer probes above predate these creation changes.

## Preliminary depth controls (no mutation)

The internal `prepare_extrusion_depth_edit_windows_with_definition` reuses exact
definition observation and refuses unreadable/changing controls, readonly or
view-only parts, existing sketches/commands, suppressed/frozen/rolled-back
features, nonblind/thin/draft/two-direction/reference-start definitions. Its
initial scope conservatively rejects any equations/design tables and multiple
configurations. These checks are not a complete public edit-eligibility contract.

The portable suite passed **920 tests**, with eight Windows-only skips, including
22 new preflight/binding tests. Negative protected/control/shape cases here are
fake evidence, not real suppression/freeze/design-table modification tests.

On native SW2025 `33.5.0`/shared PID **1096**, both exact saved boss/cut definitions
passed writable background preflight; reopening the test copy readonly refused
both with `DocumentNotWritable`. Configuration, update stamp **146**, modified
flag **false**, foreground, original documents and SW PID were retained. The
test copy's SHA256 was unchanged, and cleanup reported no errors. No
`SetDepth`, `AccessSelections`, `ModifyDefinition`, rebuild or source save ran.

The first binding attempt failed closed because idle native
`GetRunningCommandInfo` left PMTitle unwritten. A separate readonly BYREF probe
proved SW2025 writes `command_id: -3` and **boolean** `ui_active: false` while
leaving the title untouched. The guard reports that absent title as `null`; it
initializes activity to **true**, so untouched activity can never prove idle.
Partial/invalid active-command outputs still fail, with dedicated fake coverage.

Raw evidence: `C:\Workspace\SWCLI-tests\a7-depth-preflight-PT5JW4\depth-preflight.json`,
copied to `/private/tmp/swcli-a7-depth-preflight.PT5JW4/depth-preflight.json`.
SHA256: `0faa1a83e5ddf258d71961dce30849c69ed756c6318591dd18f3673410bf77f1`.
This is an internal Windows control-read proof, not setter, rollback-lifecycle,
hosted CI or Wine verification.

## Test-only native depth feasibility

A separate, unexposed native probe used the preliminary guard from `05ff006`
on an unsaved copy of the same simple single-configuration test part. It changed
the exact boss from **20 → 25 mm**, then the exact cut from **5 → 8 mm**, using
`SetDepth(True, meters)`, `SetChangeToConfigurations(1, empty)` and
`ModifyDefinition(data, exact part, null component)`. It never called
`AccessSelections`, selected a feature, saved a source or restarted the host.

Both native changes passed rebuild, complete feature diagnostics, fresh depth
and non-depth flag/control readback. Independent kernel volume matched
`100 × 50 × boss_depth − π × 3² × cut_depth`. Before `ModifyDefinition`, staged
feature-data setters left model stamp, modified flag and measured geometry
unchanged. This is evidence for avoiding unnecessary selection-access rollback
in this fixture, not a guarantee for arbitrary native references or feature data.

The original documents/foreground/shared PID **1096** were preserved, with no
cleanup errors. The unsaved test copy was closed, and its on-disk SHA256 remained
unchanged. Raw evidence lives at
`C:\Workspace\SWCLI-tests\a7-depth-native-WIzuJH\depth-native.json` and
`/private/tmp/swcli-a7-depth-native.WIzuJH/depth-native.json`.
SHA256: `f0f0874dc5694d109a20eb3142c49cef676d4f1791bf0c16bb1aa57d328a203d`.

This probe is not a shipped adapter, typed protocol call, public editing
capability, no-op/failure/restoration test or Windows/Wine CI gate. Production
setter implementation and those contracts/evidence remain pending.

## Exact simple-profile and final-body guard

Internal guard `ee0d01645eb92430d32c18f09aa527d5b8ad70aa` verifies the live,
exact absorbed profile's parent/owner identities, a closed circle or connected
axis-aligned rectangle, stable geometry/coordinate transform and exactly one
final solid (no extra hidden/surface bodies or sheet metal). It retains the
preliminary control/definition guards and repeats observations before returning
a definition. This remains internal, with no public setter or selection access.

**933 portable tests** passed, eight Windows-only tests skipped. Thirteen new
cases cover profile identity, missing/duplicate/foreign/multiple parents,
malformed/nonclosed geometry, body/flag scope, changed controls/geometry and
failure without a usable definition. Negative geometry/sheet-metal cases are
portable proof, not real protected-model mutation tests.

On SW2025 `33.5.0`/shared PID **1096**, both background boss/cut guards passed
on a new disposable copy. The rectangle was **100×50 mm**, area **5000 mm²**;
the circle radius was **3 mm**, area **28.274333882308156 mm²**. Native profile
IDs **73/82** were exactly absorbed by their target features. Configuration,
stamp **146**, modified flag **false**, foreground and test-file SHA256 stayed
unchanged. Original documents/PID were preserved, no cleanup errors occurred.

Raw local evidence is in `C:\Workspace\SWCLI-tests\a7-depth-scope-oYkrDx\` and
`/private/tmp/swcli-a7-depth-scope.oYkrDx/`:

| Generated evidence | SHA256 |
| --- | --- |
| `depth-profile-guard.json` | `bd386fae21edfbbb249d97fc07bcf6ff4cfaccdf9e1e7e81a4f4f99935d1a535` |
| `without-access.json` | `1c37b8987a5c73f41a1e32ea228b5c8216ea5e91fe643aff24038235d5706fb9` |
| `depth-scope.json` | `6b5fa2d911b653aebdbf9fafd02d2c65020e84b7493286b489678710a1e0d90d` |

The latter two are separate scope-binding experiments, not passing setter
evidence. Without `AccessSelections`, native scope-body count and direction
count returned **-1**; these are not verified zero/empty selections. With
selection access on the test boss, scope-body count became **0**, but direction
still returned **-1** in the tested binding. Releasing access left `modified`
false but advanced stamp **146 → 148**: the experiment's unchanged-state
assertion correctly failed, and that first failure is retained. The test copy
was closed unsaved; original documents/PID and on-disk SHA256 were preserved.
No depth modification, retry of a failed CAD mutation or relaxed shared-gate
assertion was involved.

These findings do not establish feature-selection scope, complete restoration,
an arbitrary expected-volume formula, hosted/Wine proof or a public depth setter.

## Hosted Windows read/creation candidate

[Run 37998293756](https://github.com/YJBeetle/SWCLI/actions/runs/37998293756)
passed for source `ea9b3b077da5ff2139f1b6ccbd0384ae6815d178`: Python 3.9/3.14,
wheel and actual SOLIDWORKS installation/runtime jobs all succeeded. The
installed-wheel shared gate passed visible (SW PID **3832**) and hidden
(PID **8516**) modeling, driving-dimension and export paths on revision `33.5.0`.
Modeling retained each mode's own process, completed normally and reported no
cleanup errors.

The gate required exact creation handles, checked that the first boss/cut IDs
were reused by list/inspect (`f-3t6a2b`/`f-v13r6x` visible,
`f-fwf035`/`f-s7ffd3` hidden), preserved background read state, and verified
bounded-list and retired-handle refusals. It did not call the unexposed depth
guards or any public depth setter. The earlier creation-handle candidate
`109f61fbc9e85cfe83c7732786c198d2a275bd2e` also passed run `37995263468`;
this latest source/artifact is the checked evidence used here.

Artifact: `swcli-windows-hosted-37998293756-1` (ID `11649001477`).

| Generated evidence | SHA256 |
| --- | --- |
| `swcli-native-smoke/modeling/modeling.json` | `8639a26e04454efe374ea8d3e34fc6995aba07b4199b4dde0e98a49c78e429f1` |
| `swcli-native-smoke/hidden/modeling/modeling.json` | `5427fb0181a244c59e95ed5b7c6937464f07265a5740efe2050cb5eb78f79fa4` |

This is hosted Windows development proof, not Wine delivery, a7 publication or
depth-edit support. DockerSW remains on its independently verified a6 pin.

## Internal selection scope and access/release ownership

Implementation `60934a16fed0f7ac329950bb146bc6bb99b50c9e` adds an internal
selection-scope guard, not a public operation or depth setter. The portable
suite ran **965 tests: 957 passed, eight Windows-only tests skipped**. Its 32 new
cases cover typed/sentinel BYREF outputs, explicit/unknown directions, contour
and body-scope refusals, exact cut-body identity, partial/false/throwing access,
single release attempt, first-error preservation, missing fresh data,
foreground/modified drift, incomplete diagnostics and geometric restoration.
Portable refusals do not prove real protected-model mutation behavior.

On Windows/SW2025 `33.5.0`, a calibration on disposable copies distinguished
the default direction's complete native marker from a test-only staged plane
reference using `BYREF|VT_DISPATCH`. The staged output had count **1**, types
**[4,-1]** and **[non-null,null]**; after release, a fresh definition returned
**-1**, **[-1,-1]**, **[null,null]**. `BYREF|VT_VARIANT` was rejected with a type
mismatch. This proves the calibrated output binding/default readback, not a
universal interpretation of `-1` or exact identity of an explicit reference.
Earlier `IsSame` assertions against a plane feature/specific object failed;
the failure remains in `plane-feature-identity-unproved.json`. Explicit
direction references are rejected by the guard, not supported on weaker proof.
No staged direction was committed with `ModifyDefinition` or saved.

The actual guard then passed on another disposable part, using shared SW PID
**1096** without replacing it. The merged 20 mm rectangle boss had no selected
contours/scope bodies and **zero rollback solids**; the 5 mm circle cut had no
selected contours and one selected body native-identical to its **one live
rollback solid**. Both observed the calibrated default direction marker.
Fresh directions, definitions/controls/profiles, configuration/edit/foreground,
`modified: false`, one final solid and complete healthy 22-feature diagnostics
were verified after release. Independent volume **99858.62833058844 mm³**, area
**16094.247779607693 mm²** and centroid were unchanged. Stamps advanced
**146 → 148 → 150**, so the result explicitly reports stamp changes rather than
claiming a read-only/no-op lifecycle. Original documents, foreground and PID
were preserved; the test copy was closed unsaved and its on-disk hash unchanged.

Raw local evidence (not hosted artifacts):

| Workspace | Generated evidence | SHA256 |
| --- | --- | --- |
| `/private/tmp/swcli-a7-binding.adkfKK/` | `direction-binding.json` | `d4640ae1fd41f8048fa2b12b220b0bd60c8b72db368c5d790ceaef0863c8f3e4` |
| same | `plane-feature-identity-unproved.json` | `329903a00165af3b407a9a64334a196ca79a2cb3c48d1a0b0f75d2be0435923c` |
| `/private/tmp/swcli-a7-selection.1iFNYp/` | `selection-scope.json` | `8ab3b92383f8bb5ed576fb6ac487f8c5b8f2c530c2d19d08df576b2d2e664be2` |
| same | `logging-interrupted.json` | `92799b28015ad66d02d042178c0e246fb3aa22220e1c6567e5c346d518329ed9` |

The Windows mirrors are under `C:\Workspace\SWCLI-tests\a7-depth-binding-adkfKK`
and `C:\Workspace\SWCLI-tests\a7-selection-1iFNYp`. An earlier instrumented
probe stalled with an empty trace log; its disposable part was still unmodified
at stamp 146 on cleanup. A non-COM output control independently showed Windows
PowerShell treating stderr trace text as `NativeCommandError`. The interrupted
test Python/starter and exact test copy were cleaned up without stopping SW.
The completed probe used direct file redirection via `Start-Process` and
asserted its own results/cleanup. Its empty native trace is not call-boundary
evidence; do not claim a traced COM diagnosis from it.

This proves only the internal observer's Windows access/release lifecycle on
these fixtures. No depth write, source save, setter retry, automatic rollback,
public no-op contract, installed-wheel runtime gate, Wine support or a7 release
is established by it.

## Actual internal guarded depth writer

Implementation `f431a77` follows the released selection-scope observer with
fresh feature-data staging, explicit current-configuration scope and an exact
`ModifyDefinition` call. Its 30 portable tests cover equal-depth requests,
staging/readback failures, precommit model/foreground/stamp drift, partial
commit failures, strict native boolean outputs, rebuild failures and independent
postflight/final-state checks. Together with the additional selection drift
tests in `4df42df`, the internal candidate ran **997 tests: 989 passed, eight
Windows-only tests skipped**. It does not save, retry or undo a failed mutation.

The actual writer (not just a test-only setter sequence) passed in one shared
Windows/SW2025 `33.5.0` process, PID **1096**. A disposable saved fixture had a
100 × 50 × 20 mm boss and a radius-3, depth-5 mm cut. Boss depth **20 → 25 mm**
produced **124858.62833058843 mm³**; cut depth **5 → 8 mm** produced
**124773.80532894151 mm³**, matching independent analytical volume assertions.
Both complete scope lifecycles released access and verified the exact profile,
non-depth definition/controls/body scope, healthy diagnostics and state.

Each following equal-depth call passed with all four mutation flags false:
no setter, current-configuration setter, commit or rebuild. Independent geometry
was unchanged, but access/release advanced stamps **155 → 157** and **165 → 167**.
This is a verified unchanged-depth result, not an unchanged-stamp pure read.
The modified test copy was closed without saving. Its disk hash, original
documents, foreground and original SW PID were preserved; cleanup errors were
empty.

Raw local evidence under `/private/tmp/swcli-a7-depth-edit.BiQz5q/`:

| Generated evidence | SHA256 |
| --- | --- |
| `depth-edit.json` | `02a8578671eea49d195c6122d588756c043f893e819d0aac452decb843e7451b` |
| `native-trace.log` | `3c05cf2e290e1b2a7cae141743d741829ef23955ad693ba066ca25d03a8ddb95` |

Windows mirror: `C:\Workspace\SWCLI-tests\a7-depth-edit-BiQz5q`. This probe
actually entered `trace_native_request`; merely setting the toggle outside a
request context cannot generate native call boundaries. The earlier empty
trace therefore does not establish a stalled COM call. Flushed trace records
now cover each guarded write/equal-depth operation. Observed durations were
**134.35 / 112.50 / 117.39 / 42.46 seconds**, respectively, on this ARM64 Windows
VM with x64 SW/Python. These are one-run instrumented timings, not a benchmark
or a promise about uninstrumented/hosted/Wine speed; the first write exceeds
the old 120-second modeling-gate budget.

This establishes internal Windows adapter proof only. Public CLI/TCP/lease/CAS,
native save/reopen, installed-wheel runtime, protected-model real refusals,
Wine delivery and a7 publication still require separate evidence.

## Public CLI/TCP depth writes and protected read-only refusal

The public wiring in `d4dbe27` passed an independent source-checkout Windows
CLI → TCP → resident STA worker trial on SW2025 `33.5.0`, retaining shared
interactive PID **1096**. It used freshly created disposable A/B parts, not
native feature edits in a test setup. The exact created boss/cut handles
**`f-p6z9qh` / `f-5ddtrs`** were reused through background writes and repeated
live discovery. Missing lease, stale stamp and cross-document depth targets
failed with `DocumentLeaseConflict`, `DocumentUpdateConflict` and
`FeatureNotFound`, respectively.

Boss **20 → 25 mm** and cut **5 → 8 mm** passed the public result Schema and
semantic checks, native postflight and the analytical volume assertions above.
Both equal-depth calls had `depth_changed: false`, no mutation flags and no
rebuild. Every successful background result preserved foreground and session
current. Native save-as to a new test filename, close/reopen, fresh feature
handles, typed depth inspection and independent measured volume all passed.
The worker/server were stopped without stopping the attached SW process;
original documents/PID were preserved and initial foreground restoration
succeeded. Cleanup errors were empty.

A separate public trial reopened that saved test part read-only. A depth write
returned `DocumentNotWritable` with all mutation and selection-access flags
false. Public before/after document observations were identical. No selection
rollback, setter or commit was attempted. Cleanup again preserved the original
SW PID/documents. This is real proof for read-only refusal, not for every
protected/suppressed/equation/reference model variant.

Raw source-checkout evidence in `/private/tmp/swcli-a7-depth-edit.BiQz5q/`:

| Generated evidence | SHA256 |
| --- | --- |
| `depth-public.json` | `8cb2fad413fa6b52722303f4e3d81cafbe43c330499b8545609c28edbc463af5` |
| `depth-readonly.json` | `1e9db1670b0326d6681bd10d7a269b67a364868847a31d24978303d9644d0465` |

Windows mirrors are `C:\Workspace\SWCLI-tests\a7-depth-public-BiQz5q` and
`C:\Workspace\SWCLI-tests\a7-depth-readonly-BiQz5q`. This is public source
CLI/transport/native proof, not installed-wheel or Wine evidence. The shared
gate now requires a corresponding depth case, including read-only refusal and
an independent 600-second depth request budget. Hosted Windows dual-mode and
Wine runs still have to pass that exact candidate before a7 publication.

Earlier source `026c746ff82632d825411e131d9d0534d178c9b4` completed hosted
[Windows CI 38031331403](https://github.com/YJBeetle/SWCLI/actions/runs/38031331403)
successfully. That workflow did not contain the new depth gate and must not be
used as evidence that the new public writer passed hosted runtime tests.
