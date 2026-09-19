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
python -m swcli document close --json
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

See [Architecture](docs/architecture.md) for the project boundary and planned
execution model.

## Development

```bash
python -m unittest discover -s tests -v
```
