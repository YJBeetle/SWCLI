# Architecture

## Product boundary

SWCLI currently owns the automation control plane:

- versioned protocol and JSON Schemas;
- the `sw-cli` client;
- the resident `swclid` service;
- typed modeling, inspection, validation, rendering, and export operations;
- the native Windows COM adapter used directly and under Wine;
- protocol, CLI, host-adapter, and mocked COM unit tests.

Planned control-plane work includes a public Python SDK, MCP and other
agent-facing adapters, richer modeling operations, stable entity references,
transactions, and a reusable mock backend.

DockerSW owns the execution environment:

- Wine, Wine-Mono, Windows Python, and pywin32;
- SOLIDWORKS installation and COM registration;
- X11, VNC, and container lifecycle;
- compatibility patches and real-container smoke tests;
- installation and pinning of a tested SWCLI release.

## Execution model

The target runtime separates supervision from COM execution:

```text
sw-cli (future: SDK / MCP)
        |
        v
supervisor and protocol gateway
        |
        v
single-threaded COM worker
        |
        v
SldWorks.Application
```

The supervisor remains responsive while a command is executing and can replace
the COM worker if SOLIDWORKS becomes blocked. All SOLIDWORKS COM calls execute
on the worker's owning STA thread.

`swclid` exposes the versioned request/response protocol over newline-delimited
JSON on a TCP endpoint. TCP is used instead of a Windows named pipe so the same
client and supervisor contract works on native Windows and Wine. It binds to
`127.0.0.1:18495` by default. The current protocol has no transport
authentication, so non-loopback binds are rejected unless the operator passes
`--allow-remote`. That opt-in adds no authentication; such a listener must still
be protected by a trusted network boundary or authenticated tunnel.

The COM worker is a spawned child process. By default it refuses to start when
an active SOLIDWORKS COM host already exists. Otherwise it creates one exclusive
`SldWorks.Application` through one `DispatchEx` call. Activation errors are
reported immediately: the worker neither reactivates nor attempts ROT recovery.
Repeated activation can launch additional SOLIDWORKS processes while the first
is still loading on a busy disk, and Wine does not reliably expose that server
in ROT. Wine hosts must provide sufficient COM class-factory registration wait
inside the original activation (DockerSW does this in its Wine runtime).
The worker then waits for
`StartupProcessCompleted`, and serializes every operation against that object.
The resident instance uses SOLIDWORKS' matching lifetime control for its mode:
`UserControl=True` for a visible foreground host, or
`UserControlBackground=True` for a hidden background host. The daemon remains
the explicit owner and shuts the instance down through `ExitApp`.
`--attach-existing` is the explicit interactive exception: the worker shares
the existing COM host, preserves its visibility, reports it as not owned by the
daemon, and never closes or force-terminates it. Typed commands never start a
daemon or attach to a host implicitly. Attach mode requires an active COM host
and never falls back to `DispatchEx`; absence is reported as
`ExistingHostNotFound`.

On daemon-owned hosts, each dispatched typed request is an out-of-process API
sequence: the worker reads `CommandInProgress`, temporarily sets it to `True`
when it was `False`, and restores the prior value before publishing a result.
SOLIDWORKS' [official API contract](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~CommandInProgress.html?format=P&value=)
reduces intermediate updates for such sequences. This does not disable rebuild,
diagnostics, geometry checks, or timeouts, and the flag is not held across idle
requests. An already-true flag is left unchanged. Shared `--attach-existing`
hosts do not opt in, so their interactive command state is not modified.
Original operation exceptions survive successful restoration. A failed
restoration returns `NativeCommandRestoreFailed`, terminates the owned host
even if the worker has already exited, and requires explicit daemon restart;
no later request is dispatched against unknown application state. The failure
retains the original operation error in its exception context where applicable.

While idle, the worker waits on its request queue with a one-second timeout and
probes `RevisionNumber` before waiting again. This probe stays on the worker's
owning STA thread. Known disconnect HRESULTs take effect immediately, temporary
call-rejected HRESULTs do not count as failures, and otherwise three
consecutive probe failures are required; a successful probe resets that count.
The pre-operation probe uses the same transient HRESULT classification: a
temporary call rejection returns `HostBusy` without dispatching the operation,
marking the host disconnected or discarding the live session. No automatic
retry is performed. If retrying later, use a new request ID because replay also
remembers terminal busy failures.
An external SOLIDWORKS exit emits a lifecycle event and ends the worker; the
supervisor then clears the cached host and reports
`worker_alive: false`, `host_connected: false`, and `HostDisconnected` recovery
state. Typed operations remain blocked so they cannot silently replace the lost
document session. `daemon stop` treats an already disconnected host as a
successful idempotent shutdown, while `daemon restart` is the explicit recovery
boundary.

If an operation exceeds its request timeout, the supervisor terminates the
worker and any daemon-owned SOLIDWORKS process tree rather than reusing unknown
COM state. The following request starts a fresh owned worker automatically. An
explicitly attached interactive host is left running, but its state is unknown;
the daemon rejects further typed operations with `SharedHostRecoveryRequired`
until the user inspects SOLIDWORKS and restarts swclid.

The supervisor also owns a bounded request replay cache. Completed COM-bound
requests are keyed by `request_id` plus a canonical fingerprint of their
operation, parameters, and document/session concurrency context. An identical
retry is served from the cache, while reuse of an ID for a different semantic
request returns `RequestIdConflict`. `timeout_ms` is deliberately excluded from
the fingerprint so a transport retry can change only its waiting budget. The
cache survives COM worker replacement but not supervisor restart, and old
entries can be evicted at the advertised capacity; it is therefore an
in-process retry safety mechanism rather than durable exactly-once storage.
Terminal failures and timeouts are cached as deliberately as successes: the
same request ID denotes the same attempted semantic request, not permission to
try the operation again.

Top-level request fields are maintained across three coordinated surfaces: the
server validation allowlist, the fingerprint inclusion/exclusion rules, and
`request.schema.json`. Any protocol-field change must review all three and keep
their contract tests aligned.

Typed public CLI commands are daemon-only. The COM adapter remains an internal
worker backend and a direct unit/integration-test seam, but it is not a second
public execution mode. Host discovery and activation probes remain explicit
local diagnostics so daemon startup failures can be investigated without
silently changing document or modeling semantics.

For host-call triage, `SWCLI_TRACE_NATIVE_CALLS=1` on the daemon opts into
request-correlated, immediately flushed JSON lines on stderr. Covered COM reads,
background activation/restoration and profile creation/edit/verification retain
their original call order and STA thread. Cut extrusion also brackets exact
profile selection, `FeatureCut4`, measurement/diagnostic groups, definition
reads and incomplete-command/selection cleanup; it adds no native calls.
The logger does not record arguments,
results or exception messages, and does not implement retry/recovery. It is off
by default and idle probes stay silent. A missing terminal event identifies an
entered covered call, not its root cause; an `end` event means returned, not
necessarily business success. See the
[MacSW background-rectangle investigation](verification/macsw-background-rectangle-2026-10-08.md).

## Modeling loop

The long-term modeling loop is:

```text
inspect -> plan -> apply -> rebuild -> diagnose -> measure -> render -> verify
```

Public raw Python, eval, and direct-COM escape hatches are intentionally outside
the typed CLI contract.

The first general-modeling foundation available since v0.1.0a4 is
`document.create`: an unsaved part from a resolved native template. It reuses
the worker's application and registers the exact returned document, not a
subsequent `ActiveDoc` lookup. Creation changes only the requesting session's
current handle; selectors and leases on other documents are not involved.
Missing templates and null COM returns fail without changing current. Once
`NewDocument` has produced a document, later failure does not imply rollback;
the acquired object remains available for registration and explicit cleanup.
`sketch.rectangle` adds a self-contained fresh 2D sketch to a selected part.
Origin-plane resolution uses reference-plane transforms rather than localized
names; dimensions are millimeters in sketch-local coordinates. The worker
registers the exact feature using native `IsSame` identity and returns a
document-scoped, worker-local `s-xxxxxx` handle. It is not a persistent reference
across reopening or topology changes. Closing the document clears these handles.
The operation checks update stamps and leases before COM mutation and restores
the former foreground document without changing session current. It rejects an
existing sketch edit and exits its own edit before verifying final native edge
geometry. Failure does not imply rollback; cleanup warnings report an edit that
could not be closed. Driving dimensions and full constraint solving are not yet
part of this command. Like circle creation, rectangle creation temporarily
enables and verifies `SketchManager.AddToDB` to avoid UI snapping changing the
requested coordinates. This alone is insufficient for `CreateCenterRectangle`:
it also temporarily disables and verifies the application `swSketchInference`
toggle. Both original settings are restored and checked before sketch close;
failed restoration is reported as `SketchStateRestoreFailed`, not success.
No grid/display or solver preferences are changed. Because the inference toggle
is application-scoped, an explicitly shared interactive host can observe this
brief change; document leases do not isolate the human UI.

The fresh rectangle has four shared native corner points, two construction
diagonals and one center point coincident with both diagonals. SW2025's hidden
creation tool can omit the last point and its relations. While still owning the
fresh edit, SWCLI verifies the exact four-corner topology and explicitly adds
the missing native point and both native relations; an existing valid center is
left untouched. Unexpected points, owners, IDs or relations fail closed. Native
topology is verified again after closing the edit. This is creation completion,
not a repair/fallback in `sketch.fix-center`: imported sketches with extra origin
relations remain rejected, and failures do not imply rollback or retry.

`sketch.circle` uses the same lifecycle to create a full circle with explicit
millimeter radius and sketch-local center. Post-edit verification reads native
`ISketchArc::IsCircle`, `GetRadius` and `GetCenterPoint2`, requiring exactly one
full-circle profile. It does not add driving dimensions or persistent entity
references. Creation temporarily enables and verifies `SketchManager.AddToDB`
to bypass UI inference/snapping, then restores and verifies its original value.
Unknown mode or failed restoration is an error, not guessed state or a reason
to relax final geometry checks. Global inference/display preferences are untouched.
See [native circle creation](https://help.solidworks.com/2018/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISketchManager~CreateCircleByRadius.html)
and [full-circle detection](https://help.solidworks.com/2022/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISketchArc~IsCircle.html).

`feature.extrude` resolves a document-scoped sketch handle, verifies native
identity and `GetOwnerFeature` before selecting it, and creates a single-ended
blind boss with explicit millimeter depth, reverse and merge options. Absorbed
sketches remain in SOLIDWORKS traversal and are deliberately rejected rather
than mistaken for unused profiles. Native extrusion data, rebuild diagnostics
and solid-body evidence are checked after creation. This is not a general
geometric proof or transaction rollback. Native API references:
[owner feature](https://help.solidworks.com/2022/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFeature~GetOwnerFeature.html),
[extrusion depth](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IExtrudeFeatureData2~GetDepth.html),
[reverse direction](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IExtrudeFeatureData2~ReverseDirection.html).

`document.save-as` completes the initial rectangle/extrusion/native-save loop
for parts. It reserves a new filename without replacing an existing target,
saves the selected live document, and checks the native result, adopted name,
modified flag and minimum file size. The registry rekeys that same COM object
even after a post-save failure, preserving document ID, session, lease and
sketch handles. Native save-as changes the live filename, so it cannot use the
temporary-file rename strategy of neutral exports. No proprietary container
header is assumed; Windows CI closes and reopens the saved part and verifies
body count and rebuild diagnostics. This is not transactional rollback or a
general file-integrity validator. Assembly/drawing save-as, native-copy mode,
general sketch editing and feature editing remain pending.

`document.measure` is a part-only, selection-independent read. It enumerates
all solid bodies, including hidden bodies, and reads `IBody2::GetMassProperties`
with a unit calculation density; synthetic mass/inertia are discarded, not
reported as material evidence. Native m³/m²/m values become mm³/mm²/mm outputs.
Totals sum individual bodies (not their union), and the centroid is weighted
by their volumes in part-model coordinates. Missing/invalid geometry and
body-limit overflow fail instead of silently falling back to approximate boxes
or reporting partial totals. Existing write leases do not block observation.
The adapter was verified against the installed SOLIDWORKS 2025 API help's array
layout and unit/coordinate semantics. See
[body mass properties](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IBody2~GetMassProperties.html).

`feature.cut-extrude` adds a one-ended blind cut through a registered,
unabsorbed profile. It explicitly affects all intersected part solids, without
an implicit selected-body scope. The public normal/reverse convention matches
boss extrusion; `FeatureCut4`'s native default is opposite the sketch normal, so
its direction flag and reported native `ReverseDirection` are mapped explicitly.
The adapter checks native depth/end condition and rebuild diagnostics, and
uses before/after `document.measure` evidence to require a positive volume
reduction above an absolute/relative numerical floor. It does not infer hole
design intent, allow an unmeasurable/empty result, or undo partial mutations.
The scalar signature, body scope and direction were verified from the installed
SOLIDWORKS 2025 official API help. See
[native cut extrusion](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~FeatureCut4.html).

Since v0.1.0a5, `sketch.dimension-diameter` adds a real driving
diameter to one exact unabsorbed full-circle sketch. It registers an `m-xxxxxx`
dimension handle alongside its owning sketch, including a partial native
creation when verification fails. `dimension.inspect` rechecks native ownership
and reads value, geometry and equation/design-table control without activation.
`dimension.set` supports absorbed profiles, targets only the current configuration
and refuses externally controlled, driven or read-only dimensions. It verifies
circle/native value, rebuild diagnostics and before/after solid-body measurements;
there is no arbitrary feature-edit or automatic rollback guarantee.
Dimension handles expire on close/reopen or worker replacement. Filename reuse
does not preserve identity; native `IsSame` distinguishes external same-path
reopening from another COM wrapper for the existing document.
Writes retain common lease/stamp/session semantics. Failure to restore the prior
foreground is reported without discarding completed native mutation evidence.

`sketch.list` discovers live 2D profile features, including absorbed subfeatures,
without activation, selection, editing or rebuilding. It publishes short
document/worker-local handles, reuses the same live sketch ID on repeat listing,
and enables inspection after opening/reopening a native part. Expired handles
stay invalid; saved dimensions and 3D sketches are not part of this discovery.
Traversal must complete within its bounds before publishing a successful list.
The private traversal index uses document-unique
[IFeature.GetID](https://help.solidworks.com/2022/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ifeature~getid.html),
with exact native identity checks for repeated IDs. It is not a new public
persistent-reference contract or a name-based lookup mechanism.

On hosts advertising `dimension.discover-diameter`, an exact registered 2D
single-circle profile can yield a fresh native diameter handle after reopen,
including absorbed profiles. The adapter exhausts the observable display chain,
checks exact ownership, uniqueness, strict metadata, geometry and unchanged
configuration/edit/update stamp before registering the handle. Reads do not
require a lease or temporary activation. Repeat observations reuse the same
live dimension ID; failed/incomplete observations never publish one. An empty
display chain is `DimensionObservationUnavailable`, not absence proof, because
native display APIs can omit hidden/unloaded dimensions. This operation does
not modify display preferences, create dimensions or provide arbitrary dimension
discovery. Editing the recovered handle still uses `dimension.set` and its guards.
These operations are not present in the older a4 wheel. The a5 release notes
record the exact Windows/Wine verification and installation boundaries.

The rectangle slice available since v0.1.0a6 keeps placement and size independent.
`sketch.fix-center` explicitly fixes only a supported verified native center;
`sketch.dimension-rectangle` never invokes it implicitly. Size creation verifies
both exact driving handles and per-step width/height/center geometry before
publishing a pair of IDs. The existing `dimension.inspect/set` operations use
registered profile/axis roles rather than native names: reads preserve state,
and single-axis writes verify the other axis, center, configuration, complete
rebuild diagnostics and applicable downstream measures. Protected controls are
reported/refused rather than removed. Partial native failures retain evidence,
not an automatic rollback or unverified public pair.

`dimension.discover-rectangle` is a read-only exact axis-pair discovery operation,
including absorbed profiles after native reopen. It deduplicates observable
displays by live native identity, requires a distinct width/height pair and
cross-checks independent geometry and unchanged native snapshots. Incomplete,
ambiguous or changing reads return no handles; an empty display chain remains
unavailable evidence. It never activates, selects, forces display or overrides
controls. The [rectangle design](design/rectangle-driving-dimensions.md) and
[a6 verification record](verification/a6-2026-10-10.md) distinguish
implemented contracts, development native gates and formal release proof.

The a7 development catalog adds `feature.list/inspect` for exact part boss/cut
extrusions. A complete bounded traversal returns short document-local `f-` IDs;
native `GetID` indexes `IsSame` verification, never a feature-name lookup or a
persistent reference. Rename/repeated wrappers reuse live IDs, while retired
IDs are not reissued during the worker's lifetime. Close/reopen requires new
handles. Boss/cut creation results register the exact native creation return,
not a subsequent active/last feature. Successful responses require a feature ID;
post-creation failures preserve the first error and any available exact handle.
Such a handle identifies partial mutation, not edit authority or a rollback.

Reads preserve foreground, session current, configuration, edit identity,
modified flag and update stamp. They do not activate/select/rebuild or call
`AccessSelections` (which would roll the model back). Native and wire contracts
are checked before registering discovered handles; failed observations publish
no usable partial list/definition. These reads can observe a leased or read-only
document, but handles do not grant edit authority. Development `feature.set-depth`
uses an independent guarded write path, including lease/stamp checks before
activation, owned selection access/release, staged current-config modification
and independent post-write verification. Equal depth skips modification but
does not promise an unchanged update stamp. Partial failures retain mutation
and cleanup evidence; no implicit save/retry/rollback is performed. Public
runtime/Wine delivery is still being verified. See [feature-depth design](design/feature-depth-editing.md)
and [read-layer evidence](verification/a7-feature-observation-2026-10-10.md).

## Compatibility policy

Protocol and host implementation versions are independent. `sw-cli
capabilities` exposes the running daemon's server version, supported protocol
versions, operations, per-operation parameter schemas and request context,
request replay policy, worker/recovery state, and host details without starting
a missing local service. Its successful JSON output conforms directly to the
published capabilities schema. The schemas advertised by the daemon are the
same definitions used for request validation, so capability discovery cannot
drift from runtime parameter handling.

Starting with `v0.1.0a4`, each operation declaration also
owns its handler name, selected-document policy, lease guard, temporary
activation policy and result schema. Worker handlers are registered and checked
against that catalog at import time. Dispatch validates the request, resolves
the document, checks the update stamp and lease, then invokes the handler; view
activation is restored before describing the final document state.

`operation_result_schemas` describes the transport envelope's `result` field,
including partial adapter failures. Pre-dispatch and transport errors can omit
`result` and use the common error envelope instead. Worker results are validated
against the same contracts advertised by capabilities. A mismatch produces
`OperationResultInvalid`; validation happens after execution and does not roll
back a completed mutation or artifact write. Typed CLI JSON flattens `result`
and can add request/replay metadata. Known nested structures are described;
warning and native error details remain extensible. The validator is imported
only when validation is requested, leaving help/version startup lightweight.

Requests must encode as finite UTF-8 JSON before dispatch. Invalid text in a
request ID is not echoed; errors use the safe `invalid-request` fallback instead.
Wire `timeout_ms` rejects booleans and platform-timer overflow before a request
can enter the COM queue, so an invalid wait cannot dispatch a mutation first.

Adapter results must also serialize as finite UTF-8 JSON. NaN/Infinity,
unsupported objects, cycles and unencodable native strings fail with
`OperationResultInvalid` before socket delivery; Python's extended numeric
values are not valid wire JSON even if a Schema validator accepts them.

Native exception text preserves valid Unicode and visibly backslash-escapes
unpaired UTF-16 surrogates. The final socket encoder also guards health/control
metadata and other non-adapter responses: invalid values return a correlated
`InvalidResponse` error rather than breaking the connection during encoding.
This wire fallback does not roll back an already completed operation.

The pre-stable capabilities contract has gained a required field. Upgrade
client and daemon together when moving from `v0.1.0a3` to `v0.1.0a4`.
The published a3 wheel remains unchanged.
Length and angle units are explicit at typed modeling boundaries; host adapters
convert them to the units expected by the SOLIDWORKS API.

## Host discovery

Native Windows discovery follows the operating system's registration rather
than assuming a fixed installation directory or SOLIDWORKS release:

1. resolve the version-independent `SldWorks.Application` ProgID;
2. follow its `CLSID` and `LocalServer32` registration, using `CurVer` when
   present and the CLSID's versioned ProgID as a fallback;
3. enumerate installed SOLIDWORKS release keys for diagnostics;
4. detect an active COM object so exclusive daemon startup can reject it, or
   attach only when the caller explicitly selected `--attach-existing`.

Starting, stopping, and replacing a SOLIDWORKS process belong to the resident
daemon lifecycle. The top-level `sw-cli doctor` command only inspects host and
daemon state.

Host startup is not complete merely because the COM object can be attached.
The daemon worker waits for the official `StartupProcessCompleted` state before
reporting success. This contract applies equally to native Windows and Wine
hosts. As soon as COM activation returns, the worker reports whether it owns the
host and its exact process ID to the supervisor. Background startup records this
phase before waiting for readiness, so timeout cleanup can terminate an owned
SOLIDWORKS process by PID even when DCOM did not place it below the Python
process tree. An explicitly attached host is never selected for that cleanup.

`sw-cli daemon serve` owns the SOLIDWORKS instance and waits for
`StartupProcessCompleted`; `sw-cli daemon start` launches that same service in
the background, while `sw-cli daemon stop` requests an orderly daemon and COM
worker shutdown. `sw-cli daemon restart` first validates the local platform,
endpoint and startup wait, then stops a reachable daemon, waits
for its local endpoint to close, and then applies the requested owned or
explicit-attach startup policy. Native Windows and portable typed commands
require a reachable daemon; an absent local endpoint returns `DaemonUnavailable`
without changing the SOLIDWORKS process state.

`host_connected` describes COM availability, while `worker_alive` describes the
Python process. A confirmed disconnect clears `host` and sets recovery state
immediately; `worker_alive` may briefly remain true during native-handle release
and process teardown. This is disconnected, not a healthy execution host.

Client connection/request waits and supervisor startup waits reject booleans,
non-positive/non-finite values and waits exceeding the platform timer limit
before network or host-lifecycle side effects. Invalid restart parameters must
not shut down an existing host. This preflight does not reserve resources or
guarantee that a later COM activation succeeds.

Document operations preserve the SOLIDWORKS API's error and warning bitmasks
instead of reducing them to a boolean. The Windows adapter owns pywin32 details
such as typed `VT_BYREF | VT_I4` arguments required by `OpenDoc6`; these details
must not leak into the public protocol.

The worker owns a short-lived document registry. Opaque eight-character IDs
such as `d-k7m2q9` identify an open COM document only until it closes or the
worker restarts. Each protocol `session_id` has an independent remembered
current document; an omitted session uses `default`. Open and create update the
session current, while an explicit ID or the reserved `active` selector applies
to one request only. `document.use` is the only standalone operation that
changes current. No public command exposes SOLIDWORKS activation as persistent
state. Operations that require an active document temporarily use
`ActivateDoc3` with no rebuild and restore the previous foreground document.

Structural inspection distinguishes stable semantics from display details.
Feature traversal reports `GetTypeName2` and explicitly labels its order as
model-definition order; names and indices are observational and must not be
used as persistent identifiers. Traversals are bounded so malformed or very
large models cannot produce unbounded agent context.

Inspection reports both the document's modified flag and `NeedsRebuild2` state.
Document descriptors also expose the native `IModelDoc2::GetUpdateStamp` value.
It is useful for detecting model-state and geometry changes, including changes
made outside SWCLI, but it deliberately is not described as a complete document
revision because SOLIDWORKS does not increment it for every cosmetic or naming
edit.
The request-level `expected_update_stamp` field provides optional optimistic
concurrency for every selected-document operation. The worker resolves the
document and compares its native stamp immediately before dispatching the COM
operation. A mismatch returns `DocumentUpdateConflict` without invoking the
operation; an unavailable native stamp returns
`DocumentUpdateStampUnavailable`. This remains opt-in because the update stamp
does not cover every possible document change.
Document leases provide the complementary pessimistic mechanism. They are
worker-local, document-scoped tokens with a bounded TTL. Once active, close,
modeling, save, save-as, rebuild, render, and export require the owning session and token; read-only
inspection and diagnosis remain available. Acquisition is idempotent for the
same session, expiration is automatic, and closing a document removes its
lease. Lease state coordinates cooperating clients and is not an authentication
or network-authorization boundary.

The lease registry exists only inside one daemon's COM worker. It does not
coordinate separate daemon or container instances that happen to mount the same
workspace, so callers must not treat it as a distributed filesystem lock. A
client crash intentionally leaves the lease active until its TTL expires;
automation should use a short practical TTL and renew longer work. Opening the
same path, inspection, and diagnosis remain available because leases guard
mutating and view/artifact operations rather than reads. Status responses hide
the token from a non-owning session but expose the owner `session_id` for local
coordination, which also means leases are not a multi-tenant privacy boundary.
Rebuild and diagnosis remain distinct operations. Diagnosis reads rebuild state
and feature error codes without changing the model. Rebuild is explicit, never
saves implicitly, and always returns post-rebuild diagnostics so a true COM
call result is not mistaken for a valid model. Saving is a separate typed
operation that preserves native `Save3` error and warning bitmasks and succeeds
only when the document is no longer modified.

Rendering is an artifact-producing operation rather than a model save. The
Windows adapter fits the active view, requests an explicit pixel size, and
verifies the resulting bitmap signature and dimensions before exposing it to
an agent. Standard orientations use numeric SOLIDWORKS view IDs rather than
localized names, so rendered comparisons remain stable across host languages.
Overwrite remains opt-in. Every render is verified in a same-directory
temporary file before it atomically replaces the requested output.

Neutral and drawing exports are explicit artifact operations. Format choices
are constrained by the selected document type, selection is cleared before export,
and success requires a native zero error code, a non-empty output, and a
matching file signature. Default export is permissive and reports structured
warnings only when the source needs saving, needs rebuilding, or changes during
export. Strict export rejects those conditions. Both modes write through a
temporary file in the destination directory so the requested output is
replaced only after file verification and all applicable checks pass.

The core export primitive selects STEP, GLB, PDF, or DWG solely from the
explicit output extension and selected document type. Source-file naming and
batch policy belong to the consuming CI job, which composes explicit typed
open, export, and close operations. SWCLI does not ship a policy-specific
manifest exporter.

Typed modeling operations own their declared verification boundary. The
`part.create-box` convenience operation succeeds only after creation, rebuild,
diagnosis, body/geometry checks and native save; `document.create`, sketch and
feature primitives do not implicitly save. Approximate body boxes may reject obviously wrong geometry
but are not precision metrology. Public dimensions carry explicit units; the
Windows adapter alone converts them to API meters.

`sketch.inspect` is a selected-document read without activation or a write lease.
It validates the registered feature's exact native identity and permits absorbed
profiles, unlike feature creation. It reports native constraint/edit/owner state
and local line/arc geometry including construction segments. Unsupported types
are explicitly incomplete, not guessed. Native read failures and segment limits
fail rather than disguising missing evidence as complete geometry. Segment
indices are observation ordering, not persistent entity references.

The late-bound Windows adapter may choose a simpler compatible API overload
when pywin32 cannot marshal optional COM interface parameters. Such fallbacks
must preserve native error codes and require runtime evidence, not merely a
successful dispatch call.

An attempted `FeatureCut4` that returns no feature or raises can retain its
native ExtrudedCut command even when no sketch edit/UI is active. The cut
adapter finishes that incomplete command with the documented `SetPickMode`
before selection cleanup. It retains the original cut failure and reports any
command/selection cleanup failures independently; it neither retries the cut,
restarts the host nor treats cleanup as geometric rollback. Successful native
cuts and rejections before the native call do not take this cleanup path.
