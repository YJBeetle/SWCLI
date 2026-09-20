# SWCLI

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
- Resident service: `swclid` (managed through `sw-cli daemon`)
- Protocol: **SWCLI Protocol**

## Current status

SWCLI is in its initial host-discovery and protocol-design phase. Its read-only
doctor command discovers SOLIDWORKS through the registry, inspects an active
COM server when present, and reports the resident daemon state.

```bash
python -m swcli version --json
python -m swcli protocol show request
python -m swcli doctor --json
python -m swcli document open model.SLDPRT --read-only --json
python -m swcli document inspect --json
python -m swcli document inspect --detail structure --json
python -m swcli document save --json
python -m swcli document close --json
python -m swcli document diagnose --json
python -m swcli document rebuild --json
python -m swcli document render view.bmp --view isometric \
  --width 1024 --height 768 --json
python -m swcli document export model.step --json
python -m swcli part create-box box.SLDPRT \
  --width-mm 100 --height-mm 50 --depth-mm 20 --json
```

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
operation causes the worker and its SOLIDWORKS process tree to be replaced.

All typed `sw-cli` document and part commands use this service. The
default endpoint is `127.0.0.1:18495`; select another daemon with
`--endpoint HOST:PORT` or `SWCLI_ENDPOINT`. Failure to reach the daemon is an
error and never falls back to a second direct-COM execution mode. On native
Windows, a typed command automatically uses the same background-start logic as
`sw-cli daemon start` when its selected local endpoint is not running. Remote
endpoints are never started implicitly. `doctor` remains read-only.

`document open` supports native part, assembly, and drawing files and returns
the exact `OpenDoc6` error and warning bitmasks. `document inspect` reports the
active document's type, path, title, modified state, and rebuild status. JSON
output is always UTF-8 so paths and model names remain machine-readable across
remote runners.
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

`document save` saves the active native document in place with `Save3`. Its
response includes the raw SOLIDWORKS save error/warning bitmasks, stable names
for every set bit, and the document state before and after saving. Success
requires both a successful API result and a clean post-save document.

`document render` fits the active model in the current view and exports a BMP
at explicit pixel dimensions. It refuses to overwrite by default and verifies
the generated bitmap header and dimensions before returning an image artifact.
Use `--view` with `front`, `back`, `left`, `right`, `top`, `bottom`,
`isometric`, `trimetric`, or `dimetric` for locale-independent deterministic
orientation; the default `current` preserves the active UI orientation.

`document export` converts the active part or assembly to STEP, an active
assembly to GLB, or the active drawing to PDF or DWG. It clears selections so
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

See [Architecture](docs/architecture.md) for the project boundary and planned
execution model.

## Development

```bash
python -m unittest discover -s tests -v
```

CI runs the unit suite on Windows and builds distributions on Linux without
claiming either job proves Wine compatibility. Real SOLIDWORKS modeling is
verified on a disposable GitHub-hosted Windows runner using a versioned
installation cache; patched Wine integration remains the responsibility of
DockerSW and MacSW. A separate manual probe diagnoses disk cleanup and streamed
Google Drive ISO access without claiming that Windows Server is a supported
SOLIDWORKS client environment. See [Windows CI](docs/windows-ci.md).
