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
```

On Windows, `host probe` reports the Python architecture, registered
SOLIDWORKS version and executable, installed versions, pywin32 availability,
and details from the active `SldWorks.Application` COM object. The command is
read-only and does not open a SOLIDWORKS instance.

See [Architecture](docs/architecture.md) for the project boundary and planned
execution model.

## Development

```bash
python -m unittest discover -s tests -v
```
