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
- Resident service: `swclid`
- Protocol: **SWCLI Protocol**

## Current status

SWCLI is in its initial host-discovery and protocol-design phase. The first
native Windows probe discovers SOLIDWORKS through the registry and attaches to
an already-running COM server without starting or stopping the application.

```bash
python -m swcli version --json
python -m swcli protocol show request
python -m swcli host probe --json
python -m swcli host start --json
python -m swcli host stop --json
python -m swcli document open model.SLDPRT --read-only --json
python -m swcli document inspect --json
python -m swcli document inspect --detail structure --json
python -m swcli document close --json
python -m swcli document diagnose --json
python -m swcli document rebuild --json
python -m swcli part create-box box.SLDPRT \
  --width-mm 100 --height-mm 50 --depth-mm 20 --json
```

On Windows, `host probe` reports the Python architecture, registered
SOLIDWORKS version and executable, installed versions, pywin32 availability,
and details from the active `SldWorks.Application` COM object. The command is
read-only and does not open a SOLIDWORKS instance.

`host start` uses the registered `LocalServer32` executable and makes the
session visible by default; pass `--hidden` for an automation-only session.
`host stop` uses the SOLIDWORKS `ExitApp` API and refuses to exit while a
document is open. `host stop --force` is an explicit, potentially destructive
escape hatch that terminates the SOLIDWORKS process tree.

`document open` supports native part, assembly, and drawing files and returns
the exact `OpenDoc6` error and warning bitmasks. `document inspect` reports the
active document's type, path, title, and modified state. JSON output is always
UTF-8 so paths and model names remain machine-readable across remote runners.
`document close` refuses to close a modified document unless `--discard` is
explicitly supplied, matching the CLI's conservative lifecycle policy.

Structural inspection adds the active configuration and all configuration
names, explicit document units, a bounded top-level feature traversal in model
definition order, and part-body topology summaries. Feature names are reported
for humans but feature type is the machine-facing discriminator; callers must
not assume names or positions remain stable after edits.

`document diagnose` is read-only and reports `NeedsRebuild2` plus non-zero
per-feature `GetErrorCode2` results. `document rebuild` rebuilds only dirty
features by default; `--force` invokes a full rebuild. Both return the same
bounded diagnostic structure so agents can compare pre- and post-action state.

`part create-box` is the first typed modeling operation. It creates a centered
rectangle sketch, extrudes it, rebuilds and diagnoses the result, saves a native
part, and returns body topology evidence. CLI dimensions are explicit
millimeters and are converted to SOLIDWORKS system units internally.

See [Architecture](docs/architecture.md) for the project boundary and planned
execution model.

## Development

```bash
python -m unittest discover -s tests -v
```
