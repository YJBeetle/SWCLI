# Through-all cut — a12 first slice

Status: twelve circle/rectangle native Windows development cases passed; public
Schema/CLI/guarded adapter integration is in development. See the [VM proof and preserved failure chain](../verification/a12-native-windows-2026-10-30.md).
The released a11 wheel remains unchanged. This increment is authorized as the
next native modeling slice, not a generic COM or feature-editing framework.

## Intended public scope

Extend the existing cut operation with an explicit one-direction through-all
termination on a single-solid part, using the existing exact unabsorbed
rectangle/full-circle sketch. Blind depth remains the compatible default;
through-all must reject a supplied travel depth. CLI spelling and public result
fields are finalized only after native proof. The native unused depth argument
is not the material thickness or a reported through-all travel distance.

Keep document/session/lease/CAS guards, direction normalization, foreground
restoration and native feature identity. Existing blind-only depth editing
must continue to reject through-all features. No selected body/face scope,
two-sided through-all, thin/draft cut, reference start or arbitrary profile is
added. Do not retry native failures, roll back partial geometry or implicitly
save a user's document.

## Native calibration before implementation

`verify-through-all-calibration.py` owns one new hidden SOLIDWORKS host on the
existing CI calibration execution path. It refuses attachment and runs twelve
generated fixtures (front/top/right, each normal and reverse, for circle and
rectangle profiles) without replacing the host. Each 40×30×10 mm boss receives
a centered radius-3 mm through-hole or a 6×4 mm rectangular through-slot.
The cut's unused forward-depth argument is deliberately only 1 mm, so passing
analytic volume/area checks cannot be explained by a sufficiently deep blind
cut. End condition/direction/single-sided/non-thin/non-draft/start/scope readback,
complete diagnostics and one-solid metrics are required.

The exact generated boss is then changed to 25 mm through an internal native
definition edit. The cut must remain through-all and match independently
calculated volume and surface area. Native save, close, an empty host document
catalog, read-only reopen and fresh unique-cut discovery must retain the
definition and geometry; read-only observations must preserve file hashes and
the saved state. This test-only boss edit does not expand public depth-edit
eligibility. Failure stops the plan and preserves the first error, traces and
owned-host cleanup evidence.

The opt-in workflow input `calibrate_through_all=true` runs this diagnostic
before the mandatory full modeling suite. It retains a 10-minute calibration-step
budget, read-only repository permissions and the existing isolated CI runtime.
The diagnostic result explicitly sets `full_acceptance_eligible=false`; it is
native feasibility only, not installed public-operation acceptance. If calibration
succeeds, the unchanged installed a11 public full gate runs and keeps its own
independent receipt. Failure stops further CAD work. Normal push/manual workflows
and the default 19-set plan are unchanged.

## Subsequent gates

After native feasibility: strict request/result/CLI contracts, adapter and
daemon guards, invalid/conflicting inputs, cross-document/stale/leased targets,
partial failures and restoration; then shared public-CLI through-all cases and
full installed Windows/DockerSW gates. Keep the six Docker delivery outputs and
the original assertion/timeout policy. MacSW is excluded by the current owner instruction; do not run its host/CI or
repeat the known complex-drawing control.
Freeze host pins and original CI distribution hashes before release preparation.

## Official references

- [FeatureCut4](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ifeaturemanager~featurecut4.html)
- [swEndConditions_e](https://help.solidworks.com/2024/english/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swEndConditions_e.html)

Read the official installed `swconst.tlb` in calibration; documentation or enum
constants alone do not prove the host's late-bound COM behavior.

## First native checkpoint — 2026-10-30

[40852812777](https://github.com/YJBeetle/SWCLI/actions/runs/40852812777) at
`d8dcfe7` passed both Windows unit versions and packaging, then failed the first
front/forward calibration after creating `Cut-Extrude1` (native ID 55).
Through-all end-condition readback passed, but the combined direction/start/
solid/scope assertion failed. No later case, thickness edit or reopen ran;
cleanup errors were empty. The initial report dropped the rejected definition
values, so it does not yet identify which setting differed. The next probe
retains partial and complete readback before validation, without changing the
native arguments, geometry assertions or expected settings. This was a calibration failure; later controls and integration are recorded below.

## Public termination contract

`cut_termination.py` supplies the same conditional fields to published discovery
schemas and strict request validation. `end_condition` accepts `blind` or
`through-all`; omission retains legacy blind behavior and requires a positive
finite representable `depth_mm`. Through-all rejects any presence of `depth_mm`,
including null/zero. The CLI requires either `--depth-mm VALUE` or `--through-all`.
Existing blind routing and native creation flags remain compatible.

The through-all adapter preflights an empty selection, exactly one solid/no
other bodies and an exact supported planar profile before selection or creation.
It uses native end 1 with both scope/auto-selection flags false. It reads back
one-sided/direction/solid/from-plane/all-body/non-draft settings, requires complete
healthy diagnostics and no pending rebuild, and verifies actual volume removal
with one remaining solid. Creation does not depend on `GetDepth`: response
`depth_mm`, verified actual depth and depth tolerance are null. The top-level
`end_condition: through-all` is distinct from the native integer end-condition
readback. Success schemas require those settings and reject invented travel.
A created native feature remains bound to its exact public handle even when a
later check fails; there is no rollback or retry. The existing selected-document,
lease/CAS and foreground restoration path is reused.

Read-boundary regressions additionally cover exact observed through-all native
codes with stored depths of 0, 1 and 25 mm, including background reads under
another session's write lease. Those reads preserve foreground/current, handles,
stamp and configuration without selection access; raw stored depth does not
invent travel, material thickness or permission to edit. This is portable
contract evidence, not an actual native through-all acceptance receipt.

## Windows VM scope control — 2026-10-30

The owner authorized the Windows VM and excluded MacSW for this stage. The VM
already had a saved foreground part; `DispatchEx` returned that same PID, so
the isolated-host attempt refused it without configuring/exiting the host or
executing CAD. A separate temporary-part control preserved the original native
document identity, path, save flag, stamp, visibility and foreground.

That control located the failed setting: `FeatureScope=true`, while through-all
end condition, direction, one-sided/solid/non-draft/start settings and analytic
hole volume/area all matched. Changing only `UseAutoSelect` from true to false
(retaining `UseFeatScope=false`) made `FeatureScope=false`, with the full original
definition and geometry assertions passing. The calibration creation arguments
now explicitly disable both flags; it does not accept a broader scope as success.

The subsequent fixture-growth control found that native `ModifyDefinition` can
leave an owned selection. Growth now records and clears that selection after its
own edit, then still requires an empty selection. An existing selection is
refused before staging. No setter retry or partial rollback is introduced.

For local controls only, `calibrate_case` can retain an exact baseline catalog:
both count and one-to-one native document identity must match after each close.
The normal owned-host CI path retains the empty baseline and initial zero-count
requirement. This avoids claiming that a local host with a user document is
empty, and does not introduce a public attach/raw-COM operation.


## Installed public gate integration

The full plan retains 19 host sets and core retains 11. The existing
`reverse-cut` full set now requires both its original blind reverse-cut case and
`through-all-cut` before its empty-catalog/host-continuity checks pass. Twelve
new public-CLI fixtures cover circle/rectangle × front/top/right × normal/reverse.
They check background restoration, null travel, independent volume/area,
through-all set-depth refusal, public blind-boss growth to 25 mm, unchanged cut
termination, native save/readonly reopen/fresh exact handles, diagnostics and
hashes. There is no restart between the blind and through-all cases or among
these twelve fixtures. `verify-through-all.py` selects just this functional case
for focused testing; that subset cannot substitute for the installed full plan.
