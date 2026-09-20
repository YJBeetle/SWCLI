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
export, and a first typed part-modeling operation. The public typed commands are
daemon-only; there is no direct-COM fallback mode.

The modeling vocabulary is intentionally still small. General sketches,
features, stable entity references, transactions, SDK, MCP, and formal
capability negotiation remain future work.

## Installation

### Windows

Requirements:

- Python 3.9 or newer;
- a native SOLIDWORKS installation with working COM registration;
- pywin32, installed automatically by the Windows dependency extra below.

Until packaged releases are published, install a non-editable copy from a
checkout. This keeps the installed command independent from the checkout after
installation:

```powershell
git clone https://github.com/YJBeetle/SWCLI.git
Set-Location SWCLI
python -m pip install ".[windows]"
```

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
installation failure. On native Windows, the first typed `document` or `part`
command automatically starts the local daemon. Use `sw-cli daemon start`
explicitly when startup timing or visibility must be controlled.

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
python -m pip install --editable ".[windows]"
```

An editable installation depends on the checkout remaining at the same path.
Do not use it for a VM or deployment whose shared source drive may be absent
after restart. On macOS or Linux, omit the Windows extra when installing only
the portable client and protocol tooling:

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
and host state; `sw-cli daemon stop` requests a graceful shutdown. A timed-out
operation causes the worker and any daemon-owned SOLIDWORKS process tree to be
replaced.
Exclusive ownership is the default. If a user-started SOLIDWORKS instance
already exists, `sw-cli daemon start` fails with
`ExistingHostRequiresAttach` instead of silently sharing it. Close that
instance, or explicitly opt into an interactive shared session:

```powershell
sw-cli daemon start --attach-existing
```

An explicitly attached instance preserves its visibility and is reported as
`owned_by_daemon: false` and `shared_interactive: true`. Daemon shutdown and
timeout recovery never close or force-terminate it. Native Windows typed-command
auto-start always uses exclusive mode and never opts into sharing implicitly.

TCP connection establishment has a separate three-second timeout so an absent
local daemon can be started promptly without reducing the operation budget.
Override it with `--connect-timeout`; `--request-timeout` controls the CAD
operation after a connection has been established.

All typed `sw-cli` document and part commands use this service. The
default endpoint is `127.0.0.1:18495`; select another daemon with
`--endpoint HOST:PORT` or `SWCLI_ENDPOINT`. Failure to reach the daemon is an
error and never falls back to a second direct-COM execution mode. On native
Windows, a typed command automatically uses the same background-start logic as
`sw-cli daemon start` when its selected local endpoint is not running. Remote
endpoints are never started implicitly. The protocol currently has no transport
authentication, so do not expose the daemon directly to an untrusted network.
`doctor` remains read-only.

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
state, and rebuild status. JSON output is always UTF-8 so paths and model names
remain machine-readable across remote runners.
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

`document render` fits the selected model in its view and exports a BMP
at explicit pixel dimensions. It refuses to overwrite by default and verifies
the generated bitmap header and dimensions before returning an image artifact.
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
fails if export changes the source state. Strict mode writes to a temporary file
in the destination directory and replaces the requested output only after all
checks pass. This core operation selects format only from the explicit output
extension and does not interpret source naming conventions.

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

## Development

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
verified on a disposable GitHub-hosted Windows runner using a versioned
installation cache; patched Wine integration remains the responsibility of
DockerSW and MacSW. A separate manual probe diagnoses disk cleanup and streamed
Google Drive ISO access without claiming that Windows Server is a supported
SOLIDWORKS client environment. See [Windows CI](docs/windows-ci.md).

## License

SWCLI is available under the [MIT License](LICENSE).
