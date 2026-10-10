# Feature observation and depth editing

Status: **implemented in a7**. Exact creation/discovery handles, read-only
`feature.list/inspect` and guarded `feature.set-depth` passed portable contracts,
native Windows source proofs and formal installed Windows visible/hidden gates.
The fixed formal candidate `d5ab77c` also passed complete DockerSW Wine delivery:
six exports, modeling/depth/save-reopen, driving dimensions, localized image
smoke and image promotion. Development/source-overlay proof and distribution
publication remain distinct from these formal runtime results.
See the [depth runtime record](../verification/a7-depth-runtime-2026-10-10.md).
MacSW a7 runtime proof remains independent; arbitrary feature editing is not
claimed.

An internal, nonmutating preliminary depth guard is also implemented. It reads
strict writable/view-only, suppression/freeze/rollback, native command,
configuration and equation/design-table state, then requires stable repeated
definitions/controls and native snapshots. It is not a public command, a
complete eligibility promise or permission to call a native setter.

A further internal guard verifies one exact absorbed circle/axis-aligned
rectangle profile, its live parents and stable coordinate transform, and a
single final non-sheet-metal solid (including hidden bodies and refusing extra
surfaces). It passed portable and native Windows background checks without
selection access. Final body count/profile area still do not identify selected
contours, direction references or rollback-state feature-body scope.

An independent **internal access/release guard** now observes that scope and
verifies restoration on native Windows. It requires the exact part to be active,
owns one access/release attempt, retains the first failure, and only returns
fresh definition data after release/state/geometry checks. It is not attached
to public `feature.list/inspect`; the guarded depth writer owns it separately.

## First slice

Observe and edit exact solid blind bosses/cuts in part documents. Begin with
read-only feature enumeration and definition inspection, then add a depth-only
write with independent native and model checks. Thin, two-direction, draft,
nonblind, offset/reference-start and externally controlled cases must not be
silently normalized into this slice. An observed definition is not edit authority.

Available development vocabulary: `feature list [--max-features N]` and
`feature inspect FEATURE_ID`, with document selection and optional update-stamp
preconditions. Listing is explicitly scoped to `part-extrusions`, not all
features. The development command `feature set-depth FEATURE_ID --depth-mm VALUE`
uses the same daemon, selected-document, optional lease and update-stamp context.
It temporarily activates the exact target, restores the previous foreground and
preserves session current. This is not a generic COM bridge or published a6 API.

## Handles and ownership

- Short `f-xxxxxx` IDs refer to exact worker-held native objects in one document.
  Native `GetID` indexes identity checks, not name lookup or persistent-reference
  recovery. Repeated wrappers/renames reuse only a native-verified live handle.
- Duplicate IDs with different live objects, busy/unknown COM observations and
  unreadable IDs fail closed without discarding existing handles. A disconnected
  proxy can retire only its own binding. Retired feature tokens are never
  reissued within the registry's worker lifetime.
- Close/reopen yields new handles. Save-as may keep them while the exact
  document/objects remain live. A resolved handle does not bypass lease/session,
  update-stamp, document-membership or configuration guards.
- Register creation's exact returned feature, never a subsequent active/last
  feature or a localized name. Register discovered handles only after complete
  supported observations; partial reads publish no successful list.
- Successful boss/cut creation requires `.feature.feature_id`. If native
  creation succeeded but a later rebuild/verification failed, preserve the first
  error and any obtainable exact handle. A registry failure cannot replace the
  first mutation failure; a handle is not proof of rollback or a valid model.

## Read-only boundary

Read native metadata/definition without `AccessSelections`, activation,
selection, rollback, rebuilding or sketch edits. Exhaust the bounded native
traversal before choosing a target, preserving ID-conflict/cycle detection.
Verify complete native state before/after, including configuration, edit
identity, modified flag and update stamp. Unknown/changing observations fail
explicitly rather than returning an apparently verified definition.

`GetTypeName2` can return `ICE` for Instant3D. Resolve its documented underlying
type through `GetTypeName`, retaining both types as evidence; do not infer boss
or cut semantics from a display name. Definition length is translated to mm at
the product boundary, not assumed from document display units.

Inspection reports native `reverse_direction` and end/start/draft/thin flags,
plus native boss `merge` or cut `feature_scope`. The native cut direction is not
the creation CLI's normalized `--reverse`. `depth_mm` is the native forward
depth parameter, not the actual material thickness or a nonblind termination's
travel distance. Reads do not claim that observed features are eligible to edit.

## Depth-only write boundary

Only the current configuration and the selected exact supported feature are
in scope. Observe native depth, direction/end/start conditions, profile/body
scope and controls before mutation. Protected equations/design tables,
suppression/freeze/rollback or existing edits must not be overridden.

The first internal guard conservatively refuses **any** part containing equations
or a design table, rather than guessing which named dimension owns depth. It
also refuses multiple configurations until current-only modification scope has
separate native proof. These are deliberate unsupported-scope outcomes, not
claims that all parameters are externally controlled. Selection-scope and
access/release restoration now have separate internal proof. The internal writer
also has actual depth/post-write verification proof. Public contracts retain
mutation flags, bounded selection-check lifecycle evidence and independent
metrics; installed development-wheel Windows proof has passed, while formal
distribution and complete Wine delivery remain to be verified.

Exact simple-profile ownership and final-body classification now have a
nonmutating internal guard. Do not mistake these for complete feature-selection
scope. A native SW2025 probe returned `-1` for body-scope/direction counts without
selection access. Body-scope count became readable after access. A subsequent
direction binding calibration used `BYREF|VT_DISPATCH` object outputs and
sentinel-initialized `BYREF|VT_I4` types: default fixtures returned the complete
`(-1, [-1,-1], [null,null])` marker; a test-only staged explicit plane returned
`(1, [4,-1], [non-null,null])`, then fresh readback recovered the default marker
after release. `BYREF|VT_VARIANT` was rejected by this host. This is empirical
SW2025 binding proof, not documentation of a universally valid negative count
or proof of the explicit returned object's identity. The guard accepts only
the complete calibrated default marker and refuses explicit, unknown,
unwritten or inconsistent outputs.

The scope guard also refuses selected contours, extra/surface/sheet-metal
rollback bodies, nonmerged/thickness-linked bosses and normal/flipped-side
cuts. A scoped cut's selected body must be native-identical to its sole live
rollback solid; an all-body cut still requires exactly one such solid. It does
not infer that scope from final body count or a display name.

Entering/releasing selection access advanced update stamp
**146 → 148**, even though `modified` stayed false. This owned lifecycle cannot
be smuggled into the public read-only path or described as an unchanged-stamp
no-op. Restoration checks include configuration, modified/edit/foreground
identity, fresh exact definition/controls/profile, healthy complete diagnostics,
fresh direction readback and independent volume/area/centroid measurements.
The successful result reports the stamp change; it does not promise a pure
read, mutation rollback or Wine compatibility. A future write must distinguish
its own access stamp changes from intervening external edits.

The explicit write path may require native selection access, which rolls the
model back. Own and verify that lifecycle, modify the exact definition, then
verify restored state, unchanged non-depth parameters, native readback,
complete rebuild diagnostics and fresh body measurements. Use a simple known
profile in the gate for independent expected-volume assertions; arbitrary
downstream topology does not promise a proportional volume change.

Failures preserve the original error and available partial-mutation/cleanup
evidence. No setter retry, implicit restart or automatic transaction rollback.
No-op semantics must be independently proved, not implemented by skipping
required native observations.

The writer releases scope access before staging a fresh definition, verifies
the live model has not changed before committing, applies current-configuration
scope once, commits once, rebuilds and repeats the complete scope/profile/model
checks. `depth_changed: false` still runs preflight access/release but skips the
setter/configuration setter/commit/rebuild. It does not imply an unchanged
stamp. On failure, inspect `mutation` and `selection_checks` and refresh document
state; a native exception or false commit can leave partial changes. No implicit
save, retry, restart or rollback. Staging failures use `depth_changed: null` when
the final depth outcome cannot safely be promised.

The public result is a typed projection, not a dump of private feature-data or
native profile fingerprints. It validates exact target identity, mutation
order, native depth, selection stamp/restoration reports, equal-depth versus
write evidence and document/final-state consistency. Public `feature.inspect`
keeps its separate unchanged-stamp, no-selection-access contract.

A test-only SW2025 trial has proved `SetDepth` → current-configuration scope →
`ModifyDefinition` → rebuild/readback on a simple single-config boss/cut part
**without `AccessSelections`**. Feature-data staging left the model untouched;
the committed modification matched independent analytical volumes. This is
native feasibility for that fixture, not an implemented public setter or proof
of arbitrary reference/body scopes. Prefer a non-selection-access depth path
only after retaining the necessary scope, restoration and failure checks.

## Validation sequence

1. Registry identity/lifetime and strict, nonmutating internal observers.
2. Native Windows read-only feasibility, including background documents and
   native save/reopen. Portable fake tests are not COM proof.
3. Catalog/request/result/CLI contracts and retained guards.
4. Internal depth writes with failure/restoration tests and native Windows proof.
5. Extend the existing shared modeling/driving gates, then run Windows and the
   host projects' Wine gates. Keep DockerSW's six export outputs unchanged.

Read-layer evidence and its distinct verification boundaries are recorded in
[the a7 feature observation record](../verification/a7-feature-observation-2026-10-10.md).

## Official references

- [IFeature.GetID](https://help.solidworks.com/2022/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ifeature~getid.html):
  document-unique native IDs are not persistent-reference IDs or a lookup API.
- [IFeature.GetTypeName2](https://help.solidworks.com/2017/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature~GetTypeName2.html):
  Instant3D uses `ICE`; its underlying type requires `GetTypeName`.
- [IExtrudeFeatureData2.GetDepth](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IExtrudeFeatureData2~GetDepth.html)
  and [SetDepth](https://help.solidworks.com/2026/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IExtrudeFeatureData2~SetDepth.html).
- [AccessSelections](https://help.solidworks.com/2026/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IExtrudeFeatureData2~AccessSelections.html):
  selection access rolls the model back; modification or release must restore it.
- [ReleaseSelectionAccess](https://help.solidworks.com/2020/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IExtrudeFeatureData2~ReleaseSelectionAccess.html):
  release an accessed, uncommitted definition rather than leaving rollback state.
- [GetDirectionReference](https://help.solidworks.com/2022/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IExtrudeFeatureData2~GetDirectionReference.html):
  explicit references have object/type outputs; the native default marker above
  is a separate runtime observation, not a documented negative-count rule.
