# Agent usage guide

This guide is for AI systems **using** SWCLI, rather than maintaining its source.
It is distributed with the skill and Python package. Use the running daemon's
capabilities to resolve version differences; pre-release interfaces can change.

## Connect and discover

```bash
sw-cli version --json
sw-cli daemon status --json
sw-cli capabilities --json
```

The client runs on Windows, macOS or Linux. Only swclid's STA worker performs
SOLIDWORKS COM operations. Typed commands never start a daemon implicitly or
fall back to direct COM. For an authorized local Windows test:

```powershell
sw-cli daemon start --visible --json
```

The default start requires an exclusive host; explicitly use `--attach-existing`
only when sharing an existing interactive instance is intended. Attach mode
does not create a host if none exists and does not take ownership of it.

JSON stdout is UTF-8. When capturing native CLI output in Windows PowerShell
5.1, set `[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)` before
`ConvertFrom-Json`; its legacy decoder can corrupt Unicode or JSON delimiters.
The public plate example scopes and restores this setting for its CLI calls.
DockerSW starts its own service; do not launch a second Windows worker there.

Use `--endpoint HOST:PORT` or `SWCLI_ENDPOINT` for another endpoint. The current
transport has no authentication. Do not expose it to untrusted networks. Use
an authenticated tunnel or a trusted boundary. Native save/open/output paths
belong to the server. DockerSW's Linux entry point translates mounted Linux
paths for Wine; this is not a general remote file-transfer facility.

Capabilities publishes `operations`, `operation_schemas` and (on supported
versions) `operation_result_schemas`. Check the requested operation and its
`x-swcli-context` before assembling a request. `--help` is available locally.
If the host lacks a requested operation, report that limitation rather than
inventing a command or silently choosing a mesh/GUI workaround.

## Select documents and coordinate writers

```bash
sw-cli --session bracket document open model.SLDPRT --json
sw-cli --session bracket document list --json
sw-cli --session bracket document inspect --document d-ab12cd --json
```

Replace example IDs with real returned handles. Open/create sets the requesting
session's current document. `document use ID` changes that current handle.
`--document ID` and `--document active` select a document for one call without
changing current. Temporary foreground activation restores the previous tab.
Different session names isolate current-document state, not SOLIDWORKS itself.

Document IDs are worker-local and expire on close or worker replacement. Sketch,
feature and dimension IDs are additionally scoped to their document; they are
not persistent native references or names. Reopening a file does not promise
the same IDs.

```bash
sw-cli --session bracket document lease acquire --document d-ab12cd --ttl-seconds 60 --json
# Use the returned token, and the stamp from a recent document observation.
sw-cli --session bracket document rebuild --document d-ab12cd --lease l-ab12cd34ef56 --if-update-stamp 0 --json
sw-cli --session bracket document lease release l-ab12cd34ef56 --json
```

Reuse the same session with the token. Renew if work approaches expiry and
release after the guarded work; a crashed holder blocks cooperating writers
until TTL expiry. Leases are per daemon, not distributed/file locks. Reads and
human GUI actions are not prevented. A stamp conflict means re-inspect and
re-plan; do not blindly replace the stamp to force the original action.

## Model and verify

On hosts advertising these operations:

```bash
sw-cli --session bracket document create --type part --json
sw-cli --session bracket sketch rectangle --plane front --width-mm 100 --height-mm 50 --json
sw-cli --session bracket document inspect --detail structure --json
sw-cli --session bracket document diagnose --json
```

The rectangle is a fresh sketch using millimeters in sketch-local coordinates.
Its result verifies native edges after leaving edit mode, but does not add
driving dimensions or guarantee full definition. Preserve its sketch ID for
later supported feature commands; do not substitute a feature name. Hosts
advertising `feature.extrude` accept `sw-cli feature extrude SKETCH_ID
--depth-mm 20 --json`; it requires an unabsorbed 2D sketch in the selected part.
`--reverse` and `--no-merge` are explicit optional choices. Hosts advertising
`sketch.circle` accept `sw-cli sketch circle --plane front --radius-mm 8 --json`
with optional local center coordinates. Radius means radius, not diameter;
the closed sketch result verifies a single complete native circle. Its handle
can also be passed to `feature extrude`. A new
document is unsaved: do not assume `document save` names it or that export saves
the native source. Hosts advertising `document.save-as` accept:

```bash
sw-cli --session bracket document save-as new-part.SLDPRT --json
sw-cli --session bracket document close --json
sw-cli --session bracket document open new-part.SLDPRT --read-only --json
sw-cli --session bracket document inspect --detail structure --json
sw-cli --session bracket document diagnose --json
```

Save-as supports parts (`.SLDPRT`), assemblies (`.SLDASM`) and drawings (`.SLDDRW`) in the current
source and rejects existing targets; use the host's advertised schemas, not an
older package's assumed support. There is no overwrite or copy mode. Assembly
and drawing references are not copied or requested to be saved; this is not Pack and Go.
Renaming preserves the live document/lease/sketch IDs,
but close/reopen creates a new document handle and drops the old handles. Its
file-size/native-state checks are not a full integrity proof; reopen and verify
the geometry. Saving is allowed only when the task authorizes source changes.
Use only the save-as/feature operations the host advertises.

If `sketch.inspect` is advertised, use `sw-cli sketch inspect SKETCH_ID --json`
to re-observe current native geometry, constraint code and absorption/owner
state, even after the sketch becomes a feature's profile. This is read-only and
does not activate or edit the document. Coordinates/radii are sketch-local mm;
transform translation remains native meters. Lines/arcs are decoded, other
types have null geometry and an explicit incomplete warning. Respect the
segment limit and never use these array indices as stable entity references.
The constraint code is `swConstrainedStatus_e`, not a promise that the sketch
is dimensioned or design intent has been verified.

If `sketch.list` is advertised, `sw-cli sketch list --document DOCUMENT_ID --json`
discovers 2D profiles in an opened/reopened part, including absorbed profiles.
Use the returned IDs with `sketch inspect`; listing preserves foreground,
session current and native document state. Repeated listing retains IDs for
the same live native sketch, but close/reopen requires fresh discovery.
Respect `--max-sketches` (default 1000); traversal/limit errors are not a partial
successful list. It does not discover 3D sketches or saved dimension handles.

If `dimension.discover-diameter` is advertised, use
`sw-cli dimension discover-diameter SKETCH_ID --document DOCUMENT_ID --json`
to recover the observable unique diameter of an exact single-circle profile,
including an absorbed sketch in a reopened part. Use its returned fresh
`m-xxxxxx` with `dimension inspect/set`; never reuse the old closed-document ID.
Discovery is read-only and preserves foreground, session current and native
state. It does not enable display or create a missing dimension. An empty chain
means observation is unavailable, not proof of absence; ambiguity/incomplete
observations fail without a handle. Report the limitation instead of guessing
by name or forcing display changes. A discovered equation/design-table-controlled
dimension is observable but remains protected from typed value editing.

If capabilities advertises the a5 driving-diameter operations, an exact registered
single circle can become a parameterized profile:

```bash
sw-cli sketch dimension-diameter SKETCH_ID --diameter-mm 16 --json
sw-cli dimension inspect DIMENSION_ID --json
sw-cli feature extrude SKETCH_ID --depth-mm 10 --json
sw-cli dimension set DIMENSION_ID --value-mm 20 --json
```

Replace placeholders with returned `s-xxxxxx`/`m-xxxxxx` handles, and use the
document/session/lease/stamp context for the task. Creation requires an unabsorbed
complete circle with no dimensions. Inspect is read-only; set works after
absorption and changes only the reported current configuration. It refuses
equation/design-table control, driven/read-only dimensions and existing edits,
rather than overriding parameter ownership. Verify circle radius/center, native
value, rebuild health and actual downstream body metrics against the task.
Neither adding a diameter nor changing its value fully constrains the center.
Failure may leave a partial dimension with a usable handle. Foreground recovery
failure is an error with retained native evidence, not permission to repeat the
mutation. These commands are available since a5, not in the older a4 package.

### Parameterized rectangle

On a matching host advertising `sketch.fix-center`, `sketch.dimension-rectangle`
and `dimension.discover-rectangle`, a supported axis-aligned center rectangle
can have separate native width/height driving dimensions. These operations are
not in the a5 wheel; use capabilities rather than assuming a version upgrade.

```powershell
sw-cli document create --json
$rectangle = sw-cli sketch rectangle --plane front --width-mm 40 --height-mm 30 --center-x-mm 3 --center-y-mm 4 --json | ConvertFrom-Json
sw-cli sketch fix-center $rectangle.sketch.sketch_id --json
$size = sw-cli sketch dimension-rectangle $rectangle.sketch.sketch_id --width-mm 40 --height-mm 30 --json | ConvertFrom-Json
sw-cli feature extrude $rectangle.sketch.sketch_id --depth-mm 10 --json
sw-cli dimension inspect $size.dimensions.width.dimension_id --json
sw-cli dimension set $size.dimensions.width.dimension_id --value-mm 50 --json
sw-cli dimension set $size.dimensions.height.dimension_id --value-mm 35 --json
sw-cli document measure --json
```

Center fixing is an explicit design choice, not a hidden step in dimension
creation. It fixes the verified current center of a supported unabsorbed native
center rectangle; an exact existing fix is a verified no-op. Extra, suppressed
or origin relations are refused, not removed. Coordinates at (0,0) alone do
not prove an origin constraint. Do not move a profile or discard relations to
make a refusal disappear.

Size creation verifies both native driving dimensions and each solver step's
geometry/placement before returning width/height IDs. Failure can leave partial
dimensions without a public pair; observe state before a new attempt. `dimension
inspect` is read-only and reports native controls; `dimension set` changes only
the current configuration, preserving the other size and center and checking
rebuild diagnostics and applicable downstream body measures. Equation/design-
table, driven and read-only controls are not overridden. Verified width/height
does not imply general constraint solving or engineering approval.

After authorized native save/close/reopen, obtain a fresh profile with `sketch
list`, then use `sw-cli dimension discover-rectangle --document DOCUMENT_ID
SKETCH_ID --json`. It returns `.dimensions.width` and `.dimensions.height`, each
with a fresh live dimension ID for `dimension inspect/set`. Repeated discovery
of the same live native pair reuses those IDs; closed-document IDs stay expired.
Discovery observes without activation, selection or display changes and requires
one unambiguous exact native axis pair agreeing with independent geometry and
unchanged state. Missing/partial/ambiguous observations publish no IDs; an empty
display chain is not proof of absent dimensions. Do not create replacements or
guess names. Reads may observe a leased background document, but discovered
handles do not grant modification authority or bypass lease/stamp guards.

`document inspect` defaults to a summary with `.document.modified` and top-level
`needs_rebuild`; there is no separate `document status` command or invented
`export_ready` flag. Structure inspection and diagnosis add feature evidence.
`modified` means the native save flag is set; `needs_rebuild` is a separate native
state. Neither should be
silently resolved by saving/rebuilding if the task is only to validate committed
CI sources. Rebuild diagnostics, requested dimensions and geometry checks form
the acceptance loop; an API returning success alone is insufficient.

Hosts advertising `document.measure` support `sw-cli document measure --json`
for all solid bodies of a part. It reports kernel-derived mm³ volume, mm² area
and the volume-weighted center in part-model millimeters without selection or
rebuild changes. It is a read, available even while another session holds a
lease. Totals sum bodies rather than unioning overlapping geometry, and area
includes each body's contact/internal faces. It does not report real material
mass; approximate boxes remain a different kind of evidence.

Hosts advertising `feature.cut-extrude` accept a live sketch ID and positive
`--depth-mm`, with the same normal/default and `--reverse` convention as bosses.
It cuts all intersected solids and requires native-definition/rebuild checks
plus measured volume reduction; this is blind depth, not through-all. It does
not choose a body from GUI selection or roll back a failed partial feature.
Create a profile that intersects existing solid material and verify the actual
removed volume/shape against the task, not merely `ok: true`.

### Observe features and edit depth

Use this only when the running daemon advertises `feature.list`,
`feature.inspect` and, for editing, `feature.set-depth`. These require a matching
a7 daemon; the older a6 wheel does not implement them.

```bash
sw-cli feature list --document DOCUMENT_ID --json
sw-cli feature inspect FEATURE_ID --document DOCUMENT_ID --json
sw-cli --request-timeout 600 feature set-depth FEATURE_ID --depth-mm 25 \
  --document DOCUMENT_ID --lease LEASE_ID --if-update-stamp STAMP --json
sw-cli document measure --document DOCUMENT_ID --json
```

Replace placeholders with returned IDs/token and a freshly observed stamp.
Creation returns `.feature.feature_id` for a supported boss/cut; listing recovers
fresh exact live handles after reopen. The list covers part extrusions, not the
whole feature tree. Read-only inspection does not activate, enter selection
access or rebuild, and does not promise that the feature is editable. Native
`depth_mm` is the forward parameter, not actual material thickness or through-all
travel. A cut's native direction flag is not the creation CLI's normalized flag.

The first setter supports only writable, single-configuration parts with one
solid, an exact absorbed full-circle/axis-aligned rectangle profile and a simple
one-direction solid blind boss/cut. Equations/design tables, ongoing edits,
suppression/freeze/rollback, thin/draft/nonblind/reference-start features,
explicit direction/contour references and unsupported body scopes are refused,
not removed or silently normalized. A supported depth read is not permission
to override these controls. Do not change the model merely to evade a refusal.

Editing preserves non-depth parameters, verifies current-configuration scope,
native depth, complete rebuild health and independent body metrics. Temporary
activation restores the previous foreground and does not change session current.
The request budget is explicit; a larger budget does not authorize retries or
host restarts. Compare geometry with the task's expected result: depth alone
does not predict arbitrary downstream topology or removed material.

Equal depth is a verified mutation no-op, not a pure read: preflight native
selection access/release may advance the update stamp even when depth/geometry
and the modified flag stay unchanged. Refresh the stamp after the call; never
reuse the preflight stamp for a subsequent write.

Failures retain `mutation` and `selection_checks` evidence, including possible
staging/commit and access/release failures. `depth_changed: null` means the final
outcome is not verified. Inspect native state before another mutation; no
automatic rollback, setter retry, source save or host restart is provided.
Successful in-memory editing does not save the native part. Save only with task
authority, then close/reopen and use fresh handles to verify persistence.

### Observe exact faces and edges (since a8)

Only use this when both `entity.list` and `entity.inspect` are advertised. They
are available since a8, **not** in the older a7 wheel. Check the
running parameter/result schemas for explicit edge support as well.

```bash
sw-cli entity list --document DOCUMENT_ID --json
sw-cli entity inspect FACE_ID --document DOCUMENT_ID --json
sw-cli entity list --kind edge --document DOCUMENT_ID --json
sw-cli entity inspect EDGE_ID --kind edge --document DOCUMENT_ID --json
```

Take `ENTITY_ID` from `.entities[].entity_id`, not a face index/name or a geometric
signature. List requires a complete single-solid part (including hidden solids),
no surface bodies and 1–64 objects of the selected kind. Face results have
`face_count`, edge results `edge_count`; one list never mixes kinds. `--max-faces`
and `--max-edges` can lower their respective bounds; supplying the other kind's
limit is invalid. Both commands default to faces, even when given an edge ID.
The opaque `e-` ID does not encode its kind. Unsupported
document/body/count cases fail without a partial list. Inspect returns `.entity`
and verifies the complete bounded set, so it is not a constant-time lookup.
These reads preserve foreground/session current and configuration/edit/stamp/
modified state. They can observe another holder's leased document but do not
accept a write token or grant edit authority.

Planar `surface_geometry.plane` contains a native point in part-model mm,
surface normal and independently verified outward face normal. Cylinders expose
`axis_point_mm`, unit `axis_direction` and `radius_mm`, not a constant outward
normal. Geometry is labelled `untrimmed-surface`; it is not the face's boundary,
center or a guaranteed point on its trimmed region. Area is explicitly
approximate mm². Unclassified surfaces have unavailable analytic geometry, not
a guessed plane/cylinder.

Edge `parameter_data` reports native start/end points in part-model mm, raw
`u_min_native`/`u_max_native`, curve type and `curve_and_edge_same_direction`.
These are native parameter-space evidence, not normalized traversal, length,
vertices, closed/seam status or adjacency. Opposite sense is valid; do not
reverse/normalize the data or assume equal endpoints prove a closed edge.
The separate `curve_geometry` is labelled `untrimmed-curve`: a line has a native
root point and unit direction; a circle has center, unit axis and radius in mm.
Unsupported curves explicitly report unavailable analytic geometry. A complete
observation is not permission to fillet, chamfer or otherwise modify a target.

The short `e-xxxxxx` handles are local to the worker and document. Close/reopen
requires fresh discovery. Face and edge discovery share scope but preserve
each other's same-scope handles; neither replaces the other kind's list.
An observed configuration/stamp change permanently retires both kinds even
when geometry may be unchanged; rebuild or equal-depth
selection access can advance that stamp. A verified scope change also retires
IDs when geometry observation fails; that failure never publishes partial IDs.
An unchanged-scope geometry failure alone does not retire them.
`EntityReferenceStale` means explicitly
rediscover and re-evaluate the intended target. `EntityNotFound` means unknown,
wrong-kind, cross-document or closed handle. Verify the document and explicit
kind before rediscovering; never revive an old token or automatically select
the nearest geometric match. Entity-targeted mutations are not implemented
by these read commands.

## Export and recover

```bash
sw-cli --session bracket document export output.STEP --document d-ab12cd --strict --json
```

Normal export is permissive and reports warnings when the source needs saving,
needs rebuilding or changes during export. Strict export rejects those source
states and post-export changes. Both modes verify a temporary artifact before
replacing the final path; overwrite requires explicit `--overwrite` authority.
Filename routing (which sources/formats CI wants) is the caller's policy, not
an SWCLI export rule. Surface the failing source and structured reason.

Observe exit codes and `error.type`/`error.code`; JSON alone is not proof of
success. If an operation fails, inspect native state before another mutation:
there is no general transaction rollback. After external host death, stale
document handles cannot be used and business commands do not silently restart
SOLIDWORKS. Report `HostDisconnected` and recover with an authorized daemon
restart. Shared-host timeouts require inspection and explicit recovery as well.

Distinguish failures by their execution boundary, not just their error text:

| Failure | Meaning and next action |
| --- | --- |
| `HostBusy` | The pre-operation COM probe was temporarily rejected; the operation was not dispatched and the worker/session remains intact. Wait for the host to become available and use a new request ID for a new attempt; do not restart it automatically. |
| `DocumentUpdateConflict` / `DocumentLeaseConflict` | A concurrency guard rejected execution. Re-observe/re-plan or coordinate with the holder; do not silently bypass the stamp/token. |
| `OperationResultInvalid` / `InvalidResponse` | Execution or state observation may already have occurred before response validation/encoding failed. Inspect native state and artifacts before deciding whether another mutation is safe. |
| `HostDisconnected` | The document session was lost. Report the loss; an authorized explicit restart creates a new session with new handles. |
| `SharedHostRecoveryRequired` | A shared-host request timed out; the human's instance remains running but its state is unknown. Inspect it and obtain explicit recovery authority. |

Other operation-specific failures may also leave partial geometry. Do not
generalize `HostBusy`'s no-dispatch guarantee to every COM error, especially one
returned after a modeling handler started. Saving, closing or restarting to
"clean up" can destroy evidence or unsaved work and needs task authority.

Request IDs protect nearby transport retries: reuse the same explicit
`--request-id` only for the same semantic request. The daemon replays the first
terminal result, including failure; a genuinely new retry needs a new ID.
This bounded in-memory cache is lost on daemon restart, not a durable
exactly-once log. Unknown outcomes require inspection, not blind retries.
