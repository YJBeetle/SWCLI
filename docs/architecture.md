# Architecture

## Product boundary

SWCLI owns the automation control plane:

- versioned protocol and JSON Schemas;
- `sw-cli` and Python SDK;
- the resident `swclid` service;
- typed modeling, inspection, validation, rendering, and export operations;
- native Windows and Wine host adapters;
- MCP and other agent-facing adapters;
- mock and contract-test backends.

DockerSW owns the execution environment:

- Wine, Wine-Mono, Windows Python, and pywin32;
- SOLIDWORKS installation and COM registration;
- X11, VNC, and container lifecycle;
- compatibility patches and real-container smoke tests;
- installation and pinning of a tested SWCLI release.

## Execution model

The target runtime separates supervision from COM execution:

```text
sw-cli / SDK / MCP
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

## Modeling loop

The first stable vertical slice will implement:

```text
inspect -> plan -> apply -> rebuild -> diagnose -> measure -> render -> verify
```

Raw Python execution may remain available as an explicitly unsafe escape hatch,
but it is not the primary modeling protocol.

## Compatibility policy

Protocol and host implementation versions are independent. Clients discover
server capabilities before submitting operations. Length and angle units are
explicit at the protocol boundary; host adapters convert them to the units
expected by the SOLIDWORKS API.

## Host discovery

Native Windows discovery follows the operating system's registration rather
than assuming a fixed installation directory or SOLIDWORKS release:

1. resolve the version-independent `SldWorks.Application` ProgID;
2. follow its `CurVer`, `CLSID`, and `LocalServer32` registration;
3. enumerate installed SOLIDWORKS release keys for diagnostics;
4. attach to the active COM object only when one already exists.

Starting, stopping, and replacing a SOLIDWORKS process are explicit lifecycle
operations and remain separate from the read-only host probe.
