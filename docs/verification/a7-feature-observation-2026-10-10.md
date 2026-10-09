# a7 feature observation: development verification

This records read-only development proof, **not an a7 release** or feature-edit
support. The public implementation is `cc1ba7e5295b92e50d5f57da8e443b9d91298975`,
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

- Hosted Windows verification of the later creation-handle and depth-guard
  candidates; the read-only candidate below passed independently.
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
