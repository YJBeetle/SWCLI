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
`SldWorks.Application` through `DispatchEx`, waits for
`StartupProcessCompleted`, and serializes every operation against that object.
The resident instance uses SOLIDWORKS' matching lifetime control for its mode:
`UserControl=True` for a visible foreground host, or
`UserControlBackground=True` for a hidden background host. The daemon remains
the explicit owner and shuts the instance down through `ExitApp`.
`--attach-existing` is the explicit interactive exception: the worker shares
the existing COM host, preserves its visibility, reports it as not owned by the
daemon, and never closes or force-terminates it. Typed-command auto-start never
enables this option.
If an operation exceeds its request timeout, the supervisor terminates the
worker and any daemon-owned SOLIDWORKS process tree rather than reusing unknown
COM state. The following request starts a fresh owned worker automatically. An
explicitly attached interactive host is left running, but its state is unknown;
the daemon rejects further typed operations with `SharedHostRecoveryRequired`
until the user inspects SOLIDWORKS and restarts swclid.

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

## Compatibility policy

Protocol and host implementation versions are independent. `sw-cli
capabilities` exposes the running daemon's server version, supported protocol
versions, operations, worker/recovery state, and host details without starting
a missing local service. Its successful JSON output conforms directly to the
published capabilities schema; richer per-operation schema negotiation remains
future work.
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
worker shutdown. Native Windows typed commands reuse the `start` path when the
local endpoint is absent.

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

Typed modeling operations own their complete verification boundary. A create
operation is successful only after feature creation, rebuild, feature-level
diagnosis, body inspection and geometry smoke verification, and native save all
succeed. Approximate SOLIDWORKS body boxes may reject obviously wrong geometry
but are not precision metrology. Public dimensions carry explicit units; the
Windows adapter alone converts them to API meters.

The late-bound Windows adapter may choose a simpler compatible API overload
when pywin32 cannot marshal optional COM interface parameters. Such fallbacks
must preserve native error codes and require runtime evidence, not merely a
successful dispatch call.
