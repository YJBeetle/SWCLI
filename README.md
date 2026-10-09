# SWCLI

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[English](README.md) | [简体中文](README.CN.md)

SWCLI is an independent, cross-platform automation protocol, command-line
client, and agent runtime for controlling SOLIDWORKS on native Windows and
Wine-based hosts.

The project is designed around a stable automation contract rather than raw
GUI interaction. Its primary consumers are AI agents, CI systems, and engineers
who need repeatable model creation, inspection, validation, rendering, and
export workflows.

> [!IMPORTANT]
> SWCLI is an independent open-source project. It is not affiliated with,
> endorsed by, or supported by Dassault Systèmes or SOLIDWORKS.

## Host targets

- Windows with a native SOLIDWORKS installation
- macOS with SOLIDWORKS running through Wine
- Linux with SOLIDWORKS running through Wine
- DockerSW, which installs and pins SWCLI as its default automation interface

## Naming

- Project: **SWCLI**
- Command: `sw-cli`
- Python package: `swcli`
- Resident service: `swclid`, managed through `sw-cli daemon`
- Protocol: **SWCLI Protocol**

## Current status

SWCLI is pre-alpha but already provides the versioned local protocol, resident
daemon lifecycle, native Windows discovery, document open/inspect/save/close,
rebuild diagnostics, deterministic BMP rendering, verified STEP/GLB/PDF/DWG
export, and a reusable native part-modeling loop. The public typed commands are
daemon-only; there is no direct-COM fallback mode.

The modeling vocabulary is intentionally still small. General sketch editing,
feature editing, stable entity references, transactions, SDK, and MCP remain future
work. The daemon now publishes the JSON Schema used to validate each supported
operation through capability discovery. Since `v0.1.0a4`, it also advertises
`operation_result_schemas` and validates worker results before returning them.
The a4 release added unsaved part creation, verified rectangle/circle sketches,
blind bosses/cuts, native volume/area observation and new-filename part save-as.
Since `v0.1.0a5`, single-circle driving diameters can be created/edited and
rediscovered after native save/reopen. `v0.1.0a6` adds explicit rectangle center
fixing, driving width/height creation/editing and saved-pair discovery. This is
not general dimension editing or a promise of fully defined sketches.

The **a7 development checkout** additionally exposes read-only `feature list`
and `feature inspect`, with exact short feature handles. Successful boss/cut
creation also returns `.feature.feature_id` from the exact native creation
object. This is not in the published a6 wheel; depth editing is not yet implemented. See the
[feature-depth plan](docs/design/feature-depth-editing.md) and
[read-layer verification](docs/verification/a7-feature-observation-2026-10-10.md).

## Installation

### Windows

Requirements:

- Python 3.9 or newer;
- a native SOLIDWORKS installation with working COM registration;
- pywin32, installed automatically on Windows by the package metadata.

Install the pinned `v0.1.0a6` pre-release wheel from GitHub Releases. This keeps the
installed command independent from a checkout and avoids silently following
later protocol changes:

```powershell
python -m pip install --upgrade "swcli @ https://github.com/YJBeetle/SWCLI/releases/download/v0.1.0a6/swcli-0.1.0a6-py3-none-any.whl"
```

The package installs pywin32 automatically when running on Windows. The
`[windows]` suffix shown in the `v0.1.0a1` notes is no longer needed.

`v0.1.0a6` is a pre-release: commands and the `swcli/v1` protocol may still
change before `v0.1.0`.

Stop the old daemon before upgrading, then explicitly start the matching version.
Temporary document/sketch/dimension/feature handles and leases expire on restart.
See the [a6 release notes](docs/releases/v0.1.0a6.md) for portable-client
installation, exact verification evidence and known limits.

The installation creates `sw-cli.exe` in Python's scripts directory. If a new
terminal cannot find `sw-cli`, add that directory to the user `PATH`, then
reopen the terminal:

```powershell
$scripts = python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($userPath -split ";") -notcontains $scripts) {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$scripts", "User")
}
```

Verify both package installation and host discovery:

```powershell
sw-cli version --json
sw-cli doctor --json
sw-cli daemon status --json
```

`daemon status` may report that no service is running; that is not an
installation failure. Before using `document` or `part`, start the daemon
explicitly with `sw-cli daemon start` (hidden by default) or
`sw-cli daemon start --visible`. These commands wait for SOLIDWORKS to become
ready. If SOLIDWORKS is already running, use
`sw-cli daemon start --attach-existing` instead.

`python -m swcli` is an equivalent fallback when the scripts directory is not
yet on `PATH`:

```powershell
python -m swcli version --json
```

### DockerSW

DockerSW images install and pin a tested SWCLI revision. Do not install a second
copy inside the container. Verify the bundled client with:

```bash
sw-cli version --json
sw-cli doctor --json
```

DockerSW runs the `sw-cli` client with Linux Python and the daemon/COM worker
with Windows Python under Wine. DockerSW owns that split runtime, Wine setup,
SOLIDWORKS registration, and process lifecycle.

### Development checkout

Contributors who intentionally want source edits to take effect immediately can
use an editable install:

```powershell
python -m pip install --editable .
```

An editable installation depends on the checkout remaining at the same path.
Do not use it for a VM or deployment whose shared source drive may be absent
after restart. On macOS or Linux, the same command installs only the portable
client and protocol tooling because the pywin32 dependency is platform-gated:

```bash
python3 -m pip install --editable .
```

Wine host installation is normally performed by DockerSW or another host
integration project; installing the portable client alone does not configure
Wine, Windows Python, pywin32, SOLIDWORKS, or COM registration.

## Quick start

The following is one read-only-source workflow after installation:

```bash
sw-cli version --json
sw-cli protocol show request
sw-cli doctor --json
sw-cli daemon start --visible --json
sw-cli document open model.SLDPRT --read-only --json
sw-cli document inspect --json
sw-cli document inspect --detail structure --json
sw-cli document diagnose --json
sw-cli document render view.bmp --view isometric \
  --width 1024 --height 768 --json
sw-cli document export model.step --strict --json
sw-cli document close --json
```

Create and verify a new part in a separate workflow:

```bash
sw-cli daemon start --json
sw-cli part create-box box.SLDPRT \
  --width-mm 100 --height-mm 50 --depth-mm 20 --json
sw-cli document inspect --detail structure --json
sw-cli document diagnose --json
sw-cli document close --json
```

Use `sw-cli document --help` for modifying operations such as `save` and
`rebuild`.

On Windows, `doctor` reports the Python architecture, registered
SOLIDWORKS version and executable, installed versions, pywin32 availability,
details from the active `SldWorks.Application` COM object, and `swclid` health.
It does not start, stop, or otherwise modify SOLIDWORKS or the daemon.

## Resident service

Run the resident service in the foreground when developing or inspecting its
logs:

```powershell
sw-cli daemon serve
```

The service binds to `127.0.0.1:18495` by default. Its supervisor accepts
versioned local JSON requests while one spawned COM worker owns the
`SldWorks.Application` instance and executes operations serially on a single
COM apartment. `sw-cli daemon start` launches the same `serve` implementation
in the background and is idempotent. `sw-cli daemon status` reports the worker
and host state, including the explicit `host_connected` flag; `sw-cli daemon
stop` requests a graceful shutdown and also succeeds when SOLIDWORKS has already
exited. While idle, the worker probes a lightweight COM property once per
second on its owning apartment. Explicit disconnect HRESULTs are acted on
immediately, temporary COM call rejection is retried, and unknown errors must
occur three times consecutively before the host is considered disconnected.
If SOLIDWORKS exits externally, the daemon clears the stale host, reports
`HostDisconnected`, and rejects typed operations instead of silently starting
a different session. Recover explicitly with:

```powershell
sw-cli daemon restart
```

A timed-out operation terminates the worker and any daemon-owned SOLIDWORKS
process tree; the following request may start a clean owned host. This timeout
recovery policy is separate from unexpected external host exit.
Exclusive ownership is the default. If a user-started SOLIDWORKS instance
already exists, `sw-cli daemon start` fails with
`ExistingHostRequiresAttach` instead of silently sharing it. Close that
instance, or explicitly opt into an interactive shared session:

```powershell
sw-cli daemon start --attach-existing
```

An explicitly attached instance preserves its visibility and is reported as
`owned_by_daemon: false` and `shared_interactive: true`. Daemon shutdown and
timeout recovery never close or force-terminate it. Because its state is unknown
after a timed-out COM call, swclid rejects further typed operations with
`SharedHostRecoveryRequired` until the user inspects SOLIDWORKS and restarts the
daemon. Typed commands never start or attach to a host implicitly.
`--attach-existing` requires an active COM host and fails with
`ExistingHostNotFound` when none exists; it never falls back
to creating a daemon-owned instance. After an attached host exits, start
SOLIDWORKS yourself and run `sw-cli daemon restart --attach-existing`.

TCP connection establishment has a separate three-second timeout so an absent
daemon can be reported promptly without reducing the operation budget.
Override it with `--connect-timeout`; `--request-timeout` controls the CAD
operation after a connection has been established.

Connection, request and startup timeouts must be positive, finite values within
the platform's timer limits. `daemon restart` validates local startup conditions
before stopping the running service; invalid parameters do not shut it down.
This is a preflight check, not a guarantee that a subsequent COM startup succeeds.

Every typed CLI request gets a random request ID. Automation that may retry an
uncertain request can provide a stable key explicitly:

```bash
sw-cli --request-id export-build-42 document export output.STEP --strict --json
```

Within one running daemon, swclid caches the most recent completed responses,
including failures and timeouts. Repeating the same semantic request with the
same ID returns that first terminal result without re-entering SOLIDWORKS and
reports `replayed: true`; execute again after a failure with a new request ID.
The CLI generates a fresh UUID for each invocation unless `--request-id` is
provided explicitly. Changing the operation, parameters, session, document,
update stamp, or lease while reusing that ID fails with `RequestIdConflict`.
The timeout is not part of the semantic request, so a retry may choose a
different waiting budget. Capability discovery reports the replay cache size
and scope. The cache is bounded and is lost when the daemon restarts, so it
protects immediate transport retries rather than providing durable exactly-once
execution across daemon failures.

All typed `sw-cli` document, sketch, feature and part commands use this service. The
default endpoint is `127.0.0.1:18495`; select another daemon with
`--endpoint HOST:PORT` or `SWCLI_ENDPOINT`. Failure to reach the daemon is an
error and never falls back to a second direct-COM execution mode. No endpoint,
local or remote, is started implicitly; an unavailable local endpoint produces
`DaemonUnavailable` with an explicit startup hint. The protocol currently has
no transport authentication. `daemon serve` therefore refuses non-loopback listeners unless
`--allow-remote` is explicitly supplied; that flag adds no authentication and
must only be used behind a trusted network boundary or authenticated tunnel.
`doctor` remains read-only.

Query the versioned capabilities of an already running daemon without starting
SOLIDWORKS implicitly:

```bash
sw-cli capabilities --json
```

On success, the JSON output directly conforms to the published capabilities
schema and includes protocol/server versions, the operation list, each
operation's parameter schema and supported request context, worker and recovery
state, request replay policy, and the current host description. The server
validates requests against the same operation catalog it publishes. In the
`v0.1.0a4` release, the catalog also declares handlers, document
selection, lease guards, temporary activation and result contracts. Result
schemas describe the protocol envelope's `result` field; typed CLI JSON flattens
that field and may add `request_id` and `replayed`. Adapter contract violations
return `OperationResultInvalid`, which may occur after the CAD operation has
already changed state. Inspect the document before attempting a new request.
A missing
or older daemon is reported as an error rather than being started or silently
accepted.

### Host path translation

Hosts that run the Linux client against a Windows Python worker (Wine, for
example) can point the client at a small helper so POSIX paths in typed
requests reach SOLIDWORKS as Windows paths. Set `SWCLI_PATH_TRANSLATE_CMD` to
an executable that accepts one path argument on `argv[1]` and prints the
translated path to stdout. The client applies it only to the parameters it
knows to be paths — `path`, `output`, and `template` — before sending the
request, so the mapping never depends on command-line argument positions. When
the variable is unset (native Windows, or a client that already passes Windows
paths) translation is skipped entirely. DockerSW ships a helper that calls
`winepath -w` for POSIX paths and passes drive-letter paths through untouched.

## Document operations

Since `v0.1.0a4`, `document create` creates an **unsaved
part** using a real `.PRTDOT` template. It does not build geometry, rebuild,
or save a file. The exact `NewDocument` handle becomes this session's current
document and receives a short-lived ID, including when it has no file path.
Only `--type part` (the default) is supported so far. Template resolution is
the same as `part create-box`: explicit path, configured default, then installed
template discovery; a missing template fails without opening a selection dialog.

```powershell
sw-cli document create --type part --json
# Alternatively: sw-cli document create --template C:\Templates\Part.PRTDOT --json
sw-cli document inspect --detail structure --json
sw-cli document close --discard
```

General sketch editing remains forthcoming; `document save-as` names a new
part, while `document save` saves an already named document. If creation succeeds but
a later check fails, the partial document is not rolled back or silently closed;
an acquired handle is registered when readable, allowing explicit inspection
and cleanup.

`document open` supports native part, assembly, and drawing files and returns
the exact `OpenDoc6` error and warning bitmasks. Every open or create returns a
short-lived ID such as `d-k7m2q9` and makes that document current for the
selected CLI session. IDs expire when the document closes or the worker
restarts. `document list` reports every open document plus its `active` and
`current` state; `document use ID` explicitly changes the session current.

Commands use the session current when `--document` is omitted. Pass
`--document ID` for a one-off exact target, or `--document active` to target the
SOLIDWORKS foreground document once; neither form changes the remembered
current. Use `--session NAME` or `SWCLI_SESSION_ID` to isolate current-document
state between concurrent clients. The unnamed default session keeps linear
shell scripts concise:

```powershell
sw-cli document open model.SLDPRT
sw-cli document rebuild
sw-cli document export output.STEP --strict
sw-cli document close
```

`document inspect` reports the selected document's type, path, title, modified
state, SOLIDWORKS `GetUpdateStamp` value, and rebuild status. The update stamp
tracks model-state and geometry changes, but is not a complete revision for
cosmetic or naming edits. JSON output is always UTF-8 so paths and model names
remain machine-readable across remote runners.

Callers that read a document and later act on it can add
`--if-update-stamp N` to any selected-document command. The daemon compares the
native stamp immediately before the operation and returns
`DocumentUpdateConflict` without entering the COM operation if the document has
changed. Omitting the option preserves the normal permissive behavior:

```powershell
sw-cli document inspect --json
sw-cli document rebuild --if-update-stamp 106 --json
```

Longer multi-step clients can acquire a short-lived document lease. While the
lease is active, modeling, close, save, save-as, rebuild, render, and export reject requests that
do not carry its token. Inspection and diagnosis remain available to other
sessions. The default TTL is 60 seconds and may be set from 1 to 3600 seconds:

```powershell
$lease = sw-cli --session agent-a document lease acquire --ttl-seconds 120 --json |
    ConvertFrom-Json
sw-cli --session agent-a document rebuild --lease $lease.lease.lease_id
sw-cli --session agent-a document lease release $lease.lease.lease_id
```

`lease status` reports ownership and remaining time; `lease renew` extends an
owned lease. Leases expire automatically, disappear when the document closes,
and coordinate clients rather than authenticate them.

Lease boundaries are deliberately narrow:

- A lease belongs to one daemon/worker process. Separate SWCLI daemon or
  container instances do not coordinate even if they mount and open the same
  file; this is not a distributed filesystem lock.
- If a holder exits without releasing, the document remains protected until
  its TTL expires. CI clients should choose a short practical TTL and renew it
  during longer operations.
- Leases guard mutations and view/artifact operations, not reads. Other
  sessions may still open the same path, inspect, and diagnose the document.
- `lease status` hides the token from other sessions but reports the owning
  `session_id` for coordination. It is not a multi-tenant privacy boundary.

`document close` refuses to close a modified document unless `--discard` is
explicitly supplied, matching the CLI's conservative lifecycle policy.

Structural inspection adds the active configuration and all configuration
names, explicit document units, a bounded top-level feature traversal in model
definition order, and part-body topology summaries. Feature names are reported
for humans but feature type is the machine-facing discriminator; callers must
not assume names or positions remain stable after edits.

`document diagnose` is read-only and reports `NeedsRebuild2` plus non-zero
per-feature `GetErrorCode2` results. `document rebuild` rebuilds only outdated
features by default; `--force` invokes a full rebuild. Both return the same
bounded diagnostic structure so agents can compare pre- and post-action state.

`document save` saves the selected native document in place with `Save3`. Its
response includes the raw SOLIDWORKS save error/warning bitmasks, stable names
for every set bit, and the document state before and after saving. Success
requires both a successful API result and a clean post-save document.

`document measure --json` (since v0.1.0a4) reads kernel-derived geometry for
all solid bodies in the selected part, including hidden bodies. It reports
volume in mm³, surface area in mm² and the volume-weighted centroid in part-model
millimeters, plus per-body evidence. It neither changes selection nor activates,
rebuilds or saves the document; another session's lease does not block this read.
`--max-bodies` defaults to 1000 and rejects larger sets rather than silently
measuring a subset. Totals are **sums of individual bodies**, not a geometric
union: overlapping volumes and contacting/internal faces are counted per body.
No material-derived mass is reported. Assembly/drawing measurement is not yet
supported, and these numeric kernel properties are not a proof of design intent.

Since `v0.1.0a4`, `document save-as new-part.SLDPRT` names the
selected part and saves it to a **new target only**. Existing targets (including
its current filename) are rejected; use `document save` for an in-place save.
Assembly/drawing save-as and copy-without-renaming are not implemented. The
same document ID, session current, lease and live sketch handles survive the
name change. The response checks native save status, adopted path, clean state
and minimum file size, not a proprietary file-format signature or complete
geometric validity. `save_warnings` is `null` because the scalar native call
does not expose that output. For stronger evidence, close, reopen and inspect
the saved part. Unlike neutral export, native save-as changes the COM document's
filename and cannot use export's temporary-file rename strategy. Failures may
leave a renamed live document; inspect its returned state and cleanup warnings.

`document render` fits the selected model in its view and exports a BMP
at explicit pixel dimensions. It refuses to overwrite by default and verifies
the generated bitmap header and dimensions before returning an image artifact.
Rendering always uses a temporary file in the destination directory and only
replaces the requested output after verification succeeds.
Use `--view` with `front`, `back`, `left`, `right`, `top`, `bottom`,
`isometric`, `trimetric`, or `dimetric` for locale-independent deterministic
orientation; the default `current` preserves the active UI orientation.

`document export` converts the selected part or assembly to STEP, a selected
assembly to GLB, or the selected drawing to PDF or DWG. It clears selections so
the whole document is exported, refuses overwrite by default, and verifies the
resulting file signature and non-empty content. The default mode is permissive:
it completes the export but reports structured warnings only when the source
needs saving, needs rebuilding, or its state changes during export. `--strict`
rejects a source that needs saving or rebuilding before invoking SOLIDWORKS and
fails if export changes the source state. Both modes write to a temporary file
in the destination directory and replace the requested output only after file
verification and any strict checks pass. This core operation selects format
only from the explicit output extension and does not interpret source naming
conventions.

## Sketch operations (since v0.1.0a4)

```powershell
sw-cli document create --json
sw-cli sketch rectangle --plane front --width-mm 100 --height-mm 50 --json
sw-cli document inspect --detail structure --json
sw-cli document close --discard
```

`sketch rectangle` creates a fresh 2D sketch on the `front`, `top` or `right`
origin plane of a part, without relying on translated plane names. Width,
height and the optional `--center-x-mm` / `--center-y-mm` (default zero) use
millimeters in **sketch-local coordinates**. The response includes the native
`model_to_sketch_transform` (translation components use meters), the verified
four-edge bounds, native constraint status and a short `s-ab12cd` sketch ID.
IDs identify exact sketch feature handles within their document and worker;
they expire on document close or worker restart and are not persistent
references across saving, reopening or topology changes.

Creation verifies a real center point attached to both construction diagonals.
If the native hidden-mode tool omits it, SWCLI explicitly creates that point and
its two relations in the fresh sketch; it does not weaken center-constraint
checks or repair imported sketches with extra origin relations.

The command exits sketch editing before verifying the final geometry. It does
not add driving dimensions or promise a fully defined sketch. An existing
sketch edit is rejected rather than taken over. `--document`, `--lease` and
`--if-update-stamp` use the same guards as document writes; temporarily
activating a background document does not change the session current. On
failure, cleanup attempts to exit only the edit started by this operation;
partial geometry is not rolled back, and cleanup failures produce warnings.

`sketch circle --plane front --radius-mm 8` creates a fresh full-circle sketch
using the same document guards and closed-edit lifecycle as rectangles.
Optional `--center-x-mm` and `--center-y-mm` default to zero in sketch-local
coordinates. The radius is not a diameter. Verification reads the final native
arc's complete-circle flag, radius and center, rejects partial arcs or extra
profile segments, and returns a document-scoped sketch ID for extrusion. It
does not add driving dimensions or guarantee full definition.
`sketch inspect SKETCH_ID --json` reads a registered 2D sketch without entering
edit mode, selecting geometry, rebuilding, saving or activating its document.
It works even if the sketch was subsequently absorbed by a boss/cut and reports
the current native `swConstrainedStatus_e` code, editing/absorption state and
owner name/type. Lines and arcs/full circles include native sketch-local
millimeter coordinates/radii; construction segments are included and flagged.
The native model-to-sketch transform still uses meters for translation.
Other segment types retain type metadata but have null geometry, with
`geometry_complete: false` and a warning. This is an observation, not a geometry
or full-definition certification. `--max-segments` (default 1000) rejects an
oversized inspection instead of silently returning a partial list. It accepts
document/stamp selectors but not a write lease, and leaves session current and
foreground unchanged. It only accepts live IDs registered by this worker, not
names, segment indices, or expired IDs from a reopened file.

Since `v0.1.0a5`,
`sw-cli sketch list --document DOCUMENT_ID --json` discovers live 2D profiles,
including absorbed sketches, after opening or reopening a part. It returns
fresh document/worker-local IDs and native constraint/owner metadata. Repeated
listing reuses the ID of the same live native sketch; it never resurrects an
expired ID or guesses by name. Use a returned ID with `sketch inspect`.
Listing is read-only, accepts a document/update-stamp context but no lease,
and preserves foreground and session current. `--max-sketches` defaults to
1000; a limit or traversal failure is an error, not a partial successful list.
Listing itself does not discover dimensions or cover 3D sketches.

## Driving diameter (since v0.1.0a5)

Check the running daemon's capabilities before using these commands; older
a4 hosts do not provide them:

```powershell
sw-cli document create --json
$circle = sw-cli sketch circle --plane front --radius-mm 5 --json | ConvertFrom-Json
$diameter = sw-cli sketch dimension-diameter $circle.sketch.sketch_id --diameter-mm 16 --json | ConvertFrom-Json
sw-cli dimension inspect $diameter.dimension.dimension_id --json
sw-cli feature extrude $circle.sketch.sketch_id --depth-mm 10 --json
sw-cli dimension set $diameter.dimension.dimension_id --value-mm 20 --json
```

Creation requires one unabsorbed complete circle without existing dimensions.
The returned `m-xxxxxx` identifies the exact native diameter and owning sketch
within the document/worker; close/reopen invalidates it. Inspect is read-only.
Set changes **only the current configuration**, including after absorption by
a feature. It refuses driven/read-only, equation-controlled or design-table
dimensions and existing sketch edits; it does not override their ownership.
Writes use the usual document/session/lease/stamp guards. Verification covers
native value, unchanged circle center, radius, rebuild diagnostics and downstream
body metrics, not arbitrary design intent or full definition. Failure may leave
partial mutation and a handle. Foreground restoration failure reports a failed
operation with preserved mutation evidence rather than claiming success.

For a saved/reopened part, discover a fresh sketch ID with `sketch list`, then
recover its observable single-circle diameter without editing:

```powershell
$found = sw-cli dimension discover-diameter SKETCH_ID --document DOCUMENT_ID --json | ConvertFrom-Json
sw-cli dimension inspect $found.dimension.dimension_id --document DOCUMENT_ID --json
```

This read-only discovery works with absorbed profiles and reuses the same live
dimension ID on repeated observations. It preserves foreground, session current,
configuration, edit state and update stamp; it neither creates dimensions nor
enables their display. An empty display chain means observation is unavailable,
not that the file has no dimensions. Ambiguous, incomplete or inconsistent native
observations fail without publishing a handle. Only the current configuration's
single full-circle diameter is supported, not arbitrary dimensions or persistent
IDs. Discovering a handle does not grant authority to edit or save the source;
`dimension set` retains all ownership and write guards.

Windows installed-wheel and fresh hosted visible/hidden verification, plus the
independent DockerSW hidden Wine delivery pass, are recorded in the
[a5 verification notes](docs/verification/a5-2026-10-07.md). The
[a5 release notes](docs/releases/v0.1.0a5.md) distinguish development proofs
from final-version verification. Neither claims MacSW runtime proof.

## Rectangle positioning and driving sizes (since v0.1.0a6)

These commands require a matching daemon advertising the a6 operations; the a5
wheel does not contain them. Formal-version Windows visible/hidden and DockerSW
hidden Wine gates passed. Host-specific evidence and limitations are tracked in
the [a6 release notes](docs/releases/v0.1.0a6.md).

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

Positioning is explicit: `fix-center` fixes the verified current native center
of a supported unabsorbed center rectangle. Size creation does **not** invoke it
implicitly. An exact existing fix is a verified no-op; extra/suppressed/origin
relations are refused rather than removed. Being centered at (0,0) alone does
not prove an origin relation. Verified width/height does not mean arbitrary
constraint support or mechanical-design approval.

The returned `.dimensions.width` and `.dimensions.height` are exact live axis
handles. Inspection is read-only; editing changes only the current configuration,
preserving the other size and center and checking native/rebuild/downstream
evidence. Driven/read-only/equation/design-table controls are not overridden.
Writes retain document/session/lease/update-stamp guards. Failure may leave
partial native dimensions without a public pair; it is not a rollback guarantee.

After authorized native save/close/reopen, use `sketch list` for a fresh profile:

```powershell
$found = sw-cli dimension discover-rectangle --document DOCUMENT_ID SKETCH_ID --json | ConvertFrom-Json
sw-cli dimension inspect --document DOCUMENT_ID $found.dimensions.width.dimension_id --json
sw-cli dimension inspect --document DOCUMENT_ID $found.dimensions.height.dimension_id --json
```

Replace the placeholders with returned IDs. Discovery requires one observable,
unambiguous native width/height pair agreeing with independent geometry and
unchanged configuration/edit/stamp state. It preserves foreground and session
current, does not select/activate or change display, and reuses IDs on repeated
live discovery. An empty display chain means unavailable observation, not absent
dimensions. Partial/ambiguous reads publish no IDs; closed-document IDs remain
expired. A discovered handle is not permission to modify or save the source.
Exact formal-version evidence is in the
[a6 verification record](docs/verification/a6-2026-10-10.md).

## Feature operations (since v0.1.0a4)

```powershell
sw-cli document create --json
$rectangle = sw-cli sketch rectangle --plane front --width-mm 100 --height-mm 50 --json | ConvertFrom-Json
sw-cli feature extrude $rectangle.sketch.sketch_id --depth-mm 20 --json
sw-cli document inspect --detail structure --json
sw-cli document save-as new-part.SLDPRT --json
sw-cli document close --json
sw-cli document open new-part.SLDPRT --read-only --json
sw-cli document diagnose --json
```

`feature extrude SKETCH_ID` creates a one-direction blind solid extrusion from
a registered, unabsorbed 2D sketch in the selected part. Depth uses millimeters;
`--reverse` reverses the sketch-normal direction and `--no-merge` keeps new
bodies separate. It resolves the exact native sketch, rejects missing/deleted/
absorbed sketches and existing sketch edits, then rebuilds and diagnoses the
model. The response verifies native depth, direction, merge and end conditions
and reports solid-body evidence, not just echoed inputs. It does not verify all
design dimensions or save the native document. Selection cleanup and foreground
restoration follow the document guards; partial feature creation is not rolled
back on failure.

### Read-only feature discovery (a7 development)

With a matching development client/daemon advertising these operations:

```powershell
$features = sw-cli feature list --document DOCUMENT_ID --json | ConvertFrom-Json
sw-cli feature inspect $features.features[0].feature_id --document DOCUMENT_ID --json
```

Replace `DOCUMENT_ID` with the selected part's ID. Listing covers supported
solid boss/cut extrusions, not the whole feature tree; `--max-features` limits
the complete list and fails instead of truncating it. IDs refer to exact native
features, survive rename/repeated live observations, and expire on close/reopen.
Reads do not activate, select, roll back or rebuild, and may observe leased or
read-only parts without a write token. `--if-update-stamp` remains available.
Inspection reports native definition flags and the forward depth parameter in
mm, not edit eligibility, actual material thickness or nonblind travel distance.
Native cut `reverse_direction` is not creation's normalized `--reverse`.

Development creation results can be inspected directly without a name lookup:

```powershell
$boss = sw-cli feature extrude SKETCH_ID --depth-mm 20 --json | ConvertFrom-Json
sw-cli feature inspect $boss.feature.feature_id --json
```

Use the same selected document/session and required write lease as for creation.
A failed post-creation rebuild/verification may still report the created handle;
this identifies a partial mutation, not a successful model or an automatic rollback.

## Part modeling

For a readable end-to-end Windows example, see
[`examples/model-plate.ps1`](examples/model-plate.ps1). With a running a4 daemon
and matching client, run it against a new, existing local output directory:

```powershell
sw-cli daemon start --visible --json
.\examples\model-plate.ps1 -OutputDirectory C:\Models\NewPlate
```

It builds a 100×60×8 mm plate with four radius-4 mm holes using only typed CLI
commands, checks analytic volume/surface area and rebuild diagnosis, saves a
new SLDPRT, strictly exports STEP, renders BMP and verifies geometry after
reopening. It refuses existing outputs. Failure stops the script and releases
its lease but does not silently discard/save partial geometry or restart the
daemon. The sketches are native and editable, but not dimension-driven or
guaranteed fully constrained. This example is for a local Windows execution
host, not a remote file-transfer or Docker launch script.

SWCLI JSON stdout is UTF-8. In Windows PowerShell 5.1, set the native-pipeline
decoder before piping CLI JSON into `ConvertFrom-Json`:

```powershell
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
sw-cli document inspect --json | ConvertFrom-Json
```

The example scopes that setting to each CLI call and restores the caller's
encoding, including on failure. PowerShell 7 normally already uses UTF-8.

`feature cut-extrude SKETCH_ID --depth-mm 20` (since v0.1.0a4) removes material
inside an unused 2D profile with a one-direction blind cut. Like `feature extrude`,
the CLI's default direction is **along the sketch normal**; `--reverse` means
against it. The adapter accounts for SOLIDWORKS's opposite native cut default.
The cut affects all intersected solid bodies; it does not infer a selected-body
scope or support through-all/draft/thin/sheet-metal-normal options. It rebuilds,
checks native depth/direction/end condition, and requires a measurable decrease
in summed solid volume (above `max(1e-6 mm³, prior volume × 1e-12)`). A part with
no measurable solids, or a cut leaving no measurable solids, cannot pass this
initial verification contract. It reports before/after geometry, not automatic
rollback or a proof of the intended hole shape. A failed cut may already exist.

```powershell
$hole = sw-cli sketch circle --plane front --radius-mm 4 --json | ConvertFrom-Json
sw-cli feature cut-extrude $hole.sketch.sketch_id --depth-mm 20 --json
sw-cli document measure --json
```

Run this against a part whose solid intersects that profile/depth, not an empty
document. All selected-document, lease and update-stamp guards apply.

`part create-box` is the first typed modeling operation. It creates a centered
rectangle sketch, extrudes it, rebuilds and diagnoses the result, saves a native
part, and returns body topology plus an axis-aligned approximate bounding box.
It creates the document with an explicit `.PRTDOT` path instead of invoking the
interactive `NewPart` command: `--template` takes precedence, followed by the
configured default and deterministic discovery below the installed SOLIDWORKS
roots. If no usable template exists, it returns a structured error without
waiting on a hidden template-selection dialog.
The requested dimensions are checked against that box with a small smoke-test
tolerance before the file is saved. CLI dimensions are explicit millimeters
and are converted to SOLIDWORKS system units internally. SOLIDWORKS documents
body boxes as approximate, so this evidence is not a precision measurement.

See [Architecture](docs/architecture.md) for the implemented boundary and
longer-term execution model.

## Use with AI agents

The project ships a portable [SWCLI skill](src/swcli/skills/swcli/SKILL.md) and
an [agent usage guide](src/swcli/skills/swcli/references/usage.md). They describe
capability discovery, document/session selection, concurrency guards, units,
export checks and failure recovery for agents **using** the product; they are
not repository-maintenance instructions. Load or install the complete `swcli`
skill folder using your agent tool's own skill mechanism. Installing the Python
package includes these files but does not alter your agent's configuration.
Installed resources are available through `importlib.resources.files("swcli")`
(Python 3.9+) beneath `skills/swcli`.

## Development

The source distribution includes both READMEs, architecture/roadmap/release
documents, executable examples and verification scripts. Wheels contain the
runtime, schemas and portable product skill, not the checkout's CI/examples.

See the [product roadmap](docs/roadmap.md) for completed development capabilities,
remaining modeling/protocol work and the release proof boundaries.

```bash
python -m unittest discover -s tests -v
```

Run directly from a checkout without installing by setting the source directory
on the module path:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

CI runs the unit suite on Windows 2025 with Python 3.9 and 3.14, and builds and
checks distributions on Linux without claiming either job proves Wine
compatibility. Real SOLIDWORKS modeling is
verified in visible and hidden host modes on a disposable GitHub-hosted Windows
runner using one fresh official installation; patched Wine integration remains the responsibility of DockerSW
and MacSW. This does not claim Windows Server is an officially supported
SOLIDWORKS workstation. See [Windows CI](docs/windows-ci.md) and
[shared runtime tests](docs/runtime-tests.md) for the common modeling/driving
scripts and the distinction between portable checks and real host evidence.

## License

SWCLI is available under the [MIT License](LICENSE).
