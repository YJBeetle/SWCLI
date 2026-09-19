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
2. follow its `CLSID` and `LocalServer32` registration, using `CurVer` when
   present and the CLSID's versioned ProgID as a fallback;
3. enumerate installed SOLIDWORKS release keys for diagnostics;
4. attach to the active COM object only when one already exists.

Starting, stopping, and replacing a SOLIDWORKS process are explicit lifecycle
operations and remain separate from the read-only host probe.

The default lifecycle policy is conservative: `start` creates a visible,
user-controlled session, while `stop` refuses to exit if a document is open.
Forced termination must be explicitly requested and may discard unsaved work.

Document operations preserve the SOLIDWORKS API's error and warning bitmasks
instead of reducing them to a boolean. The Windows adapter owns pywin32 details
such as typed `VT_BYREF | VT_I4` arguments required by `OpenDoc6`; these details
must not leak into the public protocol.

Structural inspection distinguishes stable semantics from display details.
Feature traversal reports `GetTypeName2` and explicitly labels its order as
model-definition order; names and indices are observational and must not be
used as persistent identifiers. Traversals are bounded so malformed or very
large models cannot produce unbounded agent context.

Rebuild and diagnosis remain distinct operations. Diagnosis reads rebuild
state and feature error codes without changing the model. Rebuild is explicit,
never saves implicitly, and always returns post-rebuild diagnostics so a true
COM call result is not mistaken for a valid model.

Rendering is an artifact-producing operation rather than a model save. The
Windows adapter fits the active view, requests an explicit pixel size, and
verifies the resulting bitmap signature and dimensions before exposing it to
an agent. Standard orientations use numeric SOLIDWORKS view IDs rather than
localized names, so rendered comparisons remain stable across host languages.
Overwrite remains opt-in.

Neutral and drawing exports are explicit artifact operations. Format choices
are constrained by active document type, selection is cleared before export,
and success requires a native zero error code, a non-empty output, a matching
file signature, and unchanged active-document state.

Batch export composes the typed document lifecycle instead of executing an
arbitrary user script. It performs a complete preflight before opening any
document, including input existence, supported conversion rules, and output
collision detection. A close failure aborts the remaining batch so automation
does not accumulate unknown active-document state.

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
