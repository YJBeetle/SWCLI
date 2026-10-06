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

While idle, the worker waits on its request queue with a one-second timeout and
probes `RevisionNumber` before waiting again. This probe stays on the worker's
owning STA thread. Known disconnect HRESULTs take effect immediately, temporary
call-rejected HRESULTs do not count as failures, and otherwise three
consecutive probe failures are required; a successful probe resets that count.
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

## Modeling loop

The long-term modeling loop is:

```text
inspect -> plan -> apply -> rebuild -> diagnose -> measure -> render -> verify
```

Public raw Python, eval, and direct-COM escape hatches are intentionally outside
the typed CLI contract.

The first general-modeling foundation on the a4 development branch is
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
part of this command.

`sketch.circle` uses the same lifecycle to create a full circle with explicit
millimeter radius and sketch-local center. Post-edit verification reads native
`ISketchArc::IsCircle`, `GetRadius` and `GetCenterPoint2`, requiring exactly one
full-circle profile. It does not add driving dimensions or persistent entity
references. See [native circle creation](https://help.solidworks.com/2018/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISketchManager~CreateCircleByRadius.html)
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

## Compatibility policy

Protocol and host implementation versions are independent. `sw-cli
capabilities` exposes the running daemon's server version, supported protocol
versions, operations, per-operation parameter schemas and request context,
request replay policy, worker/recovery state, and host details without starting
a missing local service. Its successful JSON output conforms directly to the
published capabilities schema. The schemas advertised by the daemon are the
same definitions used for request validation, so capability discovery cannot
drift from runtime parameter handling.

Starting with the `0.1.0a4` development branch, each operation declaration also
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

The pre-stable capabilities contract has gained a required field. Upgrade
client and daemon together when moving from `v0.1.0a3` to this development
version. The published a3 wheel remains unchanged.
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
