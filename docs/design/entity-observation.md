# Exact face/edge observation — next modeling slice

Status: **a8 development**, not an a7 capability. The a7 fixed-version
gates and publication are complete. An internal persistent-reference binding
now rejects malformed/oversized arrays, non-OK or unwritten status, null objects
and non-exact native identity; its 13 portable cases and native Windows 8-face
round trip pass, including strict pywin32 memoryview support. See the
[binding verification](../verification/a8-entity-references-2026-10-10.md).
The next internal complete single-solid observer has 12 portable cases and two
native Windows reads proving face/body membership, count, duplicate identity and
unchanged state. Its 64-face cap bounds pairwise comparisons; scalable enumeration
and Wine gates remain pending.
An internal per-document registry now allocates short `e-` IDs, reuses only
exact native identities and permanently retires IDs after an observed scope
change. Its lifecycle wiring to DocumentRegistry is implemented, with **19**
portable registry/lifecycle cases and independent native close/reopen checks.
Two additional trace cases cover private, paired native identity diagnostics.
The geometry adapter now validates plane points and outward normals against
native surface sense, and cylinder axes/radii, with **36** related portable
binding/geometry/observer cases and two unchanged native background reads with
matching geometric readback and short IDs. These remain internal Windows proofs.
The development CLI/catalog now advertises `entity.list` and `entity.inspect`,
with strict kind-aware parameters/results, default faces and explicit edges.
Edge contract/operation tests cover complete-kind counts, disjoint curve shapes,
raw parameters, wrong-kind refusal, mixed handle preservation and failed-read
scope retirement. The parameter schema uses a conditional kind/limit rule;
capabilities and its client checker accept and validate that schema too.
The actual typed handlers passed leased-background reads, CAS/unknown/cross-doc
refusals, real rebuild stamp invalidation and native close/reopen on Windows.
The explicit edge typed handlers now also pass current-source Windows CLI
mapping, background/mixed-kind reads, CAS/wrong-kind/cross-document refusal and
native close/reopen; a multi-face semantic regression discovered during this
run was fixed rather than bypassed. See the
[edge operations receipt](../verification/a8-edge-operations-2026-10-10.md).
This is not installed-client/TCP or Wine proof. The shared modeling gate now
reuses its existing depth fixture for both face and explicit edge checks:
8 faces, 12 box lines, 2 blind-hole circles, mixed exact-ID preservation,
wrong-kind/CAS/cross-document refusal, real depth-write retirement and native
close/reopen with fresh IDs. Analytical fixture checks do not infer public
edge length, closure or normalized trim. Installed cross-host gates remain
pending. The purpose is to give AI enough
native topology evidence to choose explicit future fillet/chamfer or
face-based sketch targets. This is not a complete topology kernel or a promise
that arbitrary references survive every model edit.

## Start with a read-only part boundary

The first increment should observe exact faces of one complete solid part, then
extend to edges. Use bounded native body/face traversal and prove membership in
the selected document/body. Do not derive identity from display names, a tree
position, array order, a rounded geometric signature or GUI selection.

The initial vocabulary is `entity.list` and `entity.inspect`, available only in
the matching a8 development daemon/client, not the published a7 wheel. Keep the
initial scope explicit instead of quietly dropping
unsupported bodies or surface geometry from a supposedly complete list.
Malformed/incomplete/cyclic/over-limit traversal fails without publishing a
successful partial list. Unsupported analytic geometry may be explicitly
unavailable, never an invented plane/line or a null object treated as absence.

Reads stay on the owning STA without activation, selection, rollback, rebuild,
solver/display changes or source saves. Verify configuration, edit identity,
modified flag, update stamp and foreground before/after. A lease does not prevent
another session from reading; unchanged state still has to be proved.

## Development commands

```sh
sw-cli entity list --document DOCUMENT_ID --max-faces 64 --json
sw-cli entity inspect ENTITY_ID --document DOCUMENT_ID --json
sw-cli entity list --kind edge --document DOCUMENT_ID --max-edges 64 --json
sw-cli entity inspect EDGE_ID --kind edge --document DOCUMENT_ID --json
```

`list` returns `.entities` with short `e-xxxxxx` IDs, `body_count: 1` and exactly
one kind's count/scope: `face_count`/`single-solid-part-faces` by default or
`edge_count`/`single-solid-part-edges` with `--kind edge`. `inspect` returns
`.entity`, but verifies the entire bounded set of that kind to avoid assuming an
old object remains valid. It uses the same explicit kind (default `face`), not a
guess from the opaque ID. A face ID cannot be inspected as an edge or vice versa.
`--max-faces` applies only to faces, `--max-edges` only to edges; the wrong limit
or both together fail rather than being ignored. Limits bound complete reads,
not pagination or truncation.
Both accept document/session/CAS context, not a lease token; they do not grant
write authority or change session current. The initial limit is 1–64 per kind,
including hidden solids; empty, multibody, surface-body or over-limit parts fail
instead of returning a supposedly complete subset. Other surfaces are explicitly
unclassified with unavailable analytic geometry. Edge descriptors carry raw
`parameter_data` and separate `curve_geometry` for untrimmed lines/circles.
Other curves are explicitly unavailable. No length, normalized trim, closure,
seam, adjacency, feature-owner or editing contract is exposed.

IDs expire on close/worker replacement and are permanently stale after an
observed configuration/stamp change, including a verified scope read in an
otherwise failed geometry observation. A failed read does not issue new IDs;
a failure in the same scope does not by itself retire exact live handles.
`EntityReferenceStale` requires explicit
rediscovery and reconsideration of the target, never automatic nearest-face
matching. `EntityNotFound` covers unknown/cross-document/closed IDs. A stamp
change may be caused by selection access or rebuild, not a topology change;
this first policy is deliberately conservative. Private persistent-reference
bytes are not serialized and geometry is not an identity key.

## Identity before geometry heuristics

SOLIDWORKS provides persistent-reference creation and resolution for selectable
model objects, including cross-session use. The internal adapter should first
calibrate `GetPersistReference3` and `GetObjectByPersistReference3` on exact
enumerated objects, with strict byte-array and BYREF status bindings. This is
an implementation choice to be proved per host, not a claim that COM wrapping
or serialization alone establishes identity. See the official
[persistent-reference guide](https://help.solidworks.com/2025/English/api/sldworksapiprogguide/overview/Persistent_Reference_IDs.htm)
and [native round-trip example](https://help.solidworks.com/2025/english/api/sldworksapi/use_persistent_reference_example_vb.htm).

Resolution must return an explicit OK state, a non-null object of the expected
kind and independently verified document/body/native identity. Deleted,
suppressed, invalid, unknown or unwritten statuses must fail closed. The status
is a bitmask, not a truthy success boolean; the official
[state enumeration](https://help.solidworks.com/2026/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swPersistReferencedObjectStates_e.html?id=2.10.1.596)
defines OK as zero. Do not fall back to the nearest-looking face when resolution
fails.

Keep public IDs short, opaque and worker/document-local initially. Store native
references privately; do not hash their bytes into a supposedly eternal public
identity. Close/worker replacement expires handles. Registration/reuse needs a
verified live object, not byte equality alone. Cross-session serialized reference
import and file-revision identity are later product work, not implicit support
from a local worker token.

For the first topology-sensitive handle, bind the observed configuration/stamp
and conservatively reject use after a change. A stamp change does not necessarily
mean topology changed (a7 selection access can advance it), but it is not proof
that the old face remains the intended target either. Rediscovery is explicit;
retired IDs are not silently rebound. More permissive revalidation requires
separate proof for surviving, split, merged and deleted entities.

## Geometry is evidence, not an identity key

Return part-model coordinates in explicit mm, direction vectors without units,
native kind and evidence/availability fields. Initial planar observations need
native plane location and outward face normal; cylindrical observations need
axis/radius only when their native arrays and normalization are proved.
An underlying infinite plane/cylinder is not its trimmed face boundary.
Do not invent a constant outward normal for a curved face or mistake an axis
orientation for material-side evidence.

`IFace2.GetArea` is documented as approximate square meters, so a converted
`approximate_area_mm2` must retain that qualifier and cannot inherit
`document.measure`'s solid-body measurement contract.
[Official face-area semantics](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFace2~GetArea.html).
Surface-normal versus face-normal orientation also matters:
[FaceInSurfaceSense](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFace2~FaceInSurfaceSense.html)
reports true when they point in opposite directions. Native probes must establish
which normal each public field actually represents.

The internal parser labels analytic geometry as `part-model` coordinates and
`untrimmed-surface`, converts native locations/radius from meters to mm and
requires finite numeric arrays of exactly 6 (plane), 3 (face normal) or 7
(cylinder) elements. Unit directions and plane face/surface sense must agree;
invalid directions are not silently normalized. An unclassified surface is
explicitly unavailable; malformed supported geometry fails the complete read.
Cylinder axes do not imply a constant outward normal or material-side label.
See [PlaneParams](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISurface~PlaneParams.html?format=P&value=)
and [CylinderParams](https://help.solidworks.com/2022/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISurface~CylinderParams.html).

Edge work follows face identity proof: an edge's underlying curve is not its
trimmed interval, closed seam or unique endpoint pair. Boundaries/units and
length accuracy need their own contract. Adjacency and owner feature evidence
must be verified rather than inferred from traversal order.

### Internal edge parameter increment

`windows_edge_geometry.observe_edge_geometry` is an internal reader, not a
new public capability or a complete edge observation. It obtains the curve
before `GetCurveParams3`, strictly checks classification/type agreement, native
booleans, finite ordered U parameters and coordinate arrays. Line root points,
circle centers and radii are converted to mm; directions must already be unit
vectors. Other curves remain explicitly unavailable rather than guessed.

`parameter_data` retains raw U values, native start/end coordinates and Sense;
`curve_geometry` describes only the **untrimmed** curve. Opposite sense is not
normalized into a validated length interval. Equal endpoint coordinates, a
full-period-looking interval or absent vertices do not grant closed-edge, seam,
arc-length, adjacency or feature-owner claims. The owning observer must still
prove complete membership, persistent-reference identity and unchanged state.
This slice has 11 portable cases; portable cases alone are not runtime proof.

`windows_edge_observation.observe_part_edges_with_handles` additionally verifies
one solid/no surface bodies, a complete 1–64-edge array, exact body ownership,
pairwise native uniqueness and private persistent-reference round trips. A
second complete enumeration must contain exactly the same native set; harmless
array reordering is accepted, but same-count replacements and duplicates fail.
Configuration, stamp, modified flag, edit identity and foreground must remain
unchanged. Any native, geometry, membership or state failure discards all edge
records and bindings while retaining the first error. Thirteen portable cases
cover this owning observer. The a8 development catalog, schema and CLI now wire
this reader through explicit `--kind edge`; installed cross-host gates remain
pending.
Two actual current-source Windows background observations now pass on the same
host, with all 14 exact bindings and analytic arrays matching native readback.
See the [edge receipt](../verification/a8-edge-observer-2026-10-10.md) for source
hashes, unchanged state, traces and the unproved false-sense/Wine boundaries.

### Internal face/edge registry increment

The document's EntityRegistry now accepts separate complete FaceBinding and
EdgeBinding batches, issues disjoint short `e-` IDs from the same worker-wide
issued set, and verifies native identity only within the selected kind. Native
body ownership is shared, and ambiguous reference bytes across kinds are
rejected. Geometry or reference-byte equality alone never rebinds an ID.

Both kinds share one observed configuration/stamp scope. A change observed
through either group or `observe_scope` permanently retires **both** groups,
even if a later read returns to the previous scope. Same-scope registration
atomically replaces only that kind's verified complete set and preserves the
other group. Failed registration publishes no partial batch or issued tokens;
a verified new scope remains retired even when registration fails.

Internal resolution explicitly requests an entity kind; its unchanged default
is `face`. An edge ID cannot be used as a face ID or in another document.
DocumentRegistry's existing close/external-close/reopen ownership expires both
kinds together; no second per-document lifetime or independent scope was added.
Kind-aware development operation/result schemas and CLI now wire both groups;
portable mixed-kind tests are not proof of installed edge commands or topology
survival.
Actual current-source Windows mixed-kind registration now passes: two reads per
opening preserve 8 face/14 edge IDs, external close expires both and reopening
issues fresh disjoint IDs. The user's original documents/foreground/SW host and
the copied file remain unchanged. See the
[mixed registry receipt](../verification/a8-edge-registry-2026-10-10.md).

Official semantics:
[GetCurveParams3 ordering](https://help.solidworks.com/2012/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.iedge~getcurveparams3.html),
[Sense](https://help.solidworks.com/2020/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.icurveparamdata~sense.html),
[UMaxValue](https://help.solidworks.com/2021/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.icurveparamdata~umaxvalue.html),
[line arrays](https://help.solidworks.com/2017/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ICurve~ILineParams.html),
[circle arrays](https://help.solidworks.com/2021/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ICurve~CircleParams.html),
[curve types](https://help.solidworks.com/2022/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swCurveTypes_e.html).

## Proof sequence

1. Native Windows read-only face traversal/reference round-trip and unchanged
   state on a disposable saved part. Probe binding failures before product wiring.
2. Registry lifetime/membership/stamp invalidation and observer failure tests;
   no public handles on incomplete observation.
3. Catalog/request/result schemas, CLI and repeated/background/session checks.
4. Shared installed Windows and host-owned Wine gates, including native
   close/reopen with fresh handles and stale-reference rejection.
5. Only then add a narrow modifying consumer (for example constant-radius edge
   fillet), with lease/CAS, exact target ownership, native readback, geometry and
   partial-failure evidence. Observation itself grants no edit authority.

Keep native feasibility, implementation, runtime CI and published capability
claims separate. A COM round-trip success is not complete topology/reopen proof,
and a box fixture is not coverage of arbitrary CAD surfaces.

## First native feasibility — 2026-10-10

A test-only direct-COM Windows probe opened a new read-only copy of the existing
100×50×20 mm boss/radius-3/depth-5 cut fixture. In the user's shared SW2025
`33.5.0` instance (PID **1096**), all **8** enumerated faces produced nonempty
persistent-reference arrays of 497–547 bytes. The calibrated input binding is
`VT_ARRAY | VT_UI1`; the output status uses sentinel-initialized
`VT_BYREF | VT_I4`. Every resolution wrote **0** and `ISldWorks.IsSame` verified
the exact original face, not a guessed geometric match. Byte lengths are evidence
for this fixture, not fixed-size assumptions for future models.

Surface observation identified seven planes and one cylinder. Converted area
was recorded explicitly as approximate. Configuration, edit identity, modified
flag and stamp **146 → 146** were unchanged; no selection/rebuild/save ran.
The probe closed only its copy, restored the original foreground, preserved the
original document set and reported no cleanup errors. The user SW was not stopped.

Probe workspace: `C:\Workspace\SWCLI-tests\a8-entity-native-BiQz5q`.
Local evidence: `/private/tmp/swcli-a7-depth-edit.BiQz5q/entity-native.json`.

| Test-only artifact | SHA-256 |
| --- | --- |
| `entity-native.json` | `e5fe402e26f855067f5a1092da9d1c9e36050cf1169eb55b4b05e7b07cdf3e20` |
| `entity-native-probe.py` | `fa91117b3a3a56664a58ec2b74737568e37f882007ac2206c27a05cdde911be1` |

This is native binding feasibility, not public registry/schema/CLI implementation,
saved-reference import, topology-edit survival, edge coverage, installed-wheel
CI or Wine support. No public `entity.*` capability is advertised yet.
