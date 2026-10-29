# a12 through-all native Windows development proof — 2026-10-30

Scope: generated fixtures through direct native adapters in the user-authorized
Windows VM, SOLIDWORKS 2025 SP5 (`33.5.0`), Python 3.14.7. This is native
feasibility, not an installed public CLI, daemon/network, DockerSW or MacSW
acceptance receipt. No a12 release is claimed.

## Preserved host boundary

The existing visible host PID was 10672 with one saved foreground part. An
attempt to create an isolated COM instance returned that same PID and was
refused before configuring/exiting it or executing fixture CAD. The existing
COM wrapper needed a fresh read-only connection afterward; that failed wrapper
read is retained separately and is not a CAD result.

Subsequent explicitly scoped controls used only their own newly created parts,
never saved/closed the existing part, never exited/restarted the host, and
verified the exact retained native document catalog after each own close.
Final native foreground, visibility, retained count 1, save flag `false` and
update stamp 102 matched the original snapshot. No MacSW App/container or
repository files were used for execution.

## First failures and minimal corrections

1. Hosted [40852812777](https://github.com/YJBeetle/SWCLI/actions/runs/40852812777)
   created a cut but failed the combined native settings assertion. Its report
   lacked rejected values; `bbddf65` retained them before validation without
   changing the request or assertions. Downloaded hosted run
   [40919115429](https://github.com/YJBeetle/SWCLI/actions/runs/40919115429)
   at `bbddf65` independently confirmed exactly `FeatureScope=true` with all
   other expected native settings matching and no cleanup errors. It stopped
   at that assertion; no growth/reopen or public full gate ran.
2. The Windows VM's 40×30×10 mm front-plane circle control proved the specific
   mismatch: `FeatureScope=true` for creation flags `UseFeatScope=false`,
   `UseAutoSelect=true`. All other read settings and analytic hole geometry
   matched. A new fixture changing only `UseAutoSelect=false` returned
   `FeatureScope=false`; all original checks passed. The calibration now disables
   both flags. It does not silently accept scoped-body creation as all-body scope.
3. The first thickness-growth control retained through-all and the expected
   definition but failed the empty-selection assertion after native
   `ModifyDefinition`. The fixture editor now records and clears its own edit's
   selection, while refusing any pre-existing selection before staging. It
   still requires zero selected objects before continuing. No failed setter is
   retried and no partial feature is rolled back.

## Six-case proof

One unrestarted existing host ran front/top/right planes, each normal and reverse.
Each independent 40×30 mm rectangular boss starts at 10 mm depth with a centered
radius-3 mm full-circle profile. The native through-all request deliberately
uses a 1 mm unused depth argument; an ordinary 1 mm blind cut cannot satisfy the
analytic volume/area checks. After changing the exact generated boss to 25 mm,
the cut must retain native end condition 1 and still remove the entire cylinder.

All six cases passed creation, strict definition/scope/direction readback,
complete healthy diagnostics and native `NeedsRebuild2=0`, independent one-solid
volume/area measurements, native save, close, exact retained catalog, read-only
reopen and fresh unique-cut discovery. No native call failure was retried.
Cleanup errors were empty, `success=true`, `original_unchanged=true` and
`full_acceptance_eligible=false`.

| Geometry | Expected volume mm³ | Expected surface area mm² |
| --- | ---: | ---: |
| 10 mm through-hole | `12000 - 90π` | `3800 + 42π` |
| 25 mm through-hole, also after reopen | `30000 - 225π` | `5900 + 132π` |

Observed volume was 11717.256661176916 mm³ initially and approximately
29293.141652942297 mm³ after growth and reopen (all within the retained analytic
tolerance). Reopen did not set the save flag or change fixture bytes.

| Plane/direction | Saved/reopened fixture SHA-256 |
| --- | --- |
| front/normal | `042308bacf26b208c350ed32855013850f4054cde66181cef9c2edf0c737be96` |
| front/reverse | `5d7b1ae2797b3138cbd0ce82cdbaae9dea390971ccb4a30bcca8f466fb5435d2` |
| top/normal | `5bb56923587f558d074a6f9ab7f674c0b0543debc86fea0760ebd880353c9103` |
| top/reverse | `ef70b1e811cbcb8c85cb8a4f8a34468e6239b2a950bc38ad7e97e9870af41dd4` |
| right/normal | `016e8a89b395df945b06d8f97f78ebcc35f20de1bd43f62ec53ddd53d4bf06fe` |
| right/reverse | `ba6141db84a94e24f320e39697a6603ca9aa355ab05d220d327bf85594479cca` |

Raw local evidence: `/private/tmp/swcli-a12-vm-scope-20261030` (initial scope
failure), `/private/tmp/swcli-a12-vm-scope-autoselect-false-20261030` (single-
variable success), `/private/tmp/swcli-a12-vm-six-20261030` (growth-selection
failure), `/private/tmp/swcli-a12-vm-six-cleanup-20261030` (six-case success,
including report, trace and private native files). These are local evidence
locations, not durable CI artifacts or release assets. Generated VM fixtures
remain under the user-authorized Desktop/TestModel directory for inspection.

## Additional rectangular-slot proof

Six further new fixtures ran the same front/top/right normal/reverse matrix
with centered 6×4 mm rectangular profiles, using the corrected scope flags and
the same fixture-edit cleanup. All passed definition/scope/direction readback,
analytic one-solid volume/area, thickness growth, native save/close/read-only
reopen and byte-hash preservation. Original host/document snapshots matched
again; `cleanup_errors=[]`, `original_unchanged=true`, and the local control
remained `full_acceptance_eligible=false`.

| Geometry | Expected volume mm³ | Expected surface area mm² |
| --- | ---: | ---: |
| 10 mm rectangular through-slot | 11760 | 3952 |
| 25 mm rectangular through-slot, also after reopen | 29400 | 6352 |

| Plane/direction | Saved/reopened fixture SHA-256 |
| --- | --- |
| front/normal | `1f52bd49be6a2aaed5a38a11c7b1a7d73e7c5a534b6a94e4c161454b17bb403b` |
| front/reverse | `ff884b74a2488e61df8862d460c5b1c6bc548680bef23f53bb02fddb2f77f581` |
| top/normal | `a9b8bf464a1fb7f1d161bd7877bed074aa7d5e8cf55828b5819508c98c6d70d4` |
| top/reverse | `be244357520a4acd61e2ec6926d616e5d3f844655e705a5fe82acbd6d09d6300` |
| right/normal | `fe71da4ddef87c2f2748c88da6b87fa7a247f8d3751beaeedf89ab5f068ffae4` |
| right/reverse | `d33d2d4789fe79650296a16a939233a6cba7880959b34e870bb53981972b508e` |

Raw rectangular evidence is `/private/tmp/swcli-a12-vm-slots-20261030`, including
report, trace and private native fixtures. The standard owned-host CI calibration
now runs all twelve circle/rectangle cases instead of only the circular six;
its original empty-catalog requirement is retained.

## Next boundary

The twelve native cases establish circular holes and rectangular slots. Typed request/
result/CLI and daemon guards, profile/body refusal, partial failures and installed
public save/reopen/export acceptance remain required. Existing blind
creation and blind-only depth editing must stay compatible. Neither this proof
nor a green calibration replaces complete Windows and DockerSW public gates.
