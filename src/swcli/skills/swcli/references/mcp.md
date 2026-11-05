# MCP connection and lifecycle

Use this guide when an AI client needs SWCLI tools through MCP. The adapter
uses the official Python MCP SDK over **stdio**. All CAD requests still go
through the existing swclid TCP protocol and its single STA COM worker.

## Install and connect

MCP requires Python 3.10 or newer. Install the matching SWCLI version with its
optional `mcp` extra (`python -m pip install "swcli[mcp]"` for a published
version, or `python -m pip install ".[mcp]"` from its source checkout).
The base CLI still supports Python 3.9. Use an absolute path to the installed
`sw-cli` when the AI client's PATH differs from your terminal.

A client supporting the common `mcpServers` JSON format can use:

```json
{
  "mcpServers": {
    "swcli": {
      "command": "sw-cli",
      "args": ["mcp", "serve"]
    }
  }
}
```

This is a stdio subprocess configuration, **not an HTTP URL**. The AI client
starts the adapter and manages its stdin/stdout. Do not pipe interactive logs
or shell banners into it. SWCLI protocol output stays on stdout; diagnostics
use stderr.

Initialization, tool discovery, status, capability queries and CAD calls never
start SOLIDWORKS implicitly. Call `swcli_status`, explicitly call
`swcli_daemon_start` if the task needs a host, then discover and execute CAD
operations. There is no lazy startup or `--auto-start` option.

Starting **both swclid and SOLIDWORKS** can take tens of seconds to several
minutes. The start tool waits for readiness (default 120 seconds, configurable
up to 600) and provides progress when the client requests it. Set the client's
tool timeout to cover that startup budget plus transport overhead. Do not
submit another start while one is pending. After a timeout, inspect status;
the host may have started even if its reply was lost.

### Daemon utilities selection

The shared manager uses an explicit global `--daemon-utils PATH` first, then
`SWCLI_DAEMON_UTILS`, then the built-in native Windows launcher. A configured
utility must be an existing absolute executable path; it is process
configuration, never an AI-supplied tool argument. A configured utility failure
is reported without falling back to a different runtime. On Linux/macOS,
missing utilities configuration is an error: the MCP client's Python is not the Wine
Windows Python that runs swclid. SWCLI does not search PATH for Wine, prefixes,
SOLIDWORKS or a different Python.

The DockerSW and MacSW `sw-cli` entry scripts only set the native client
environment and forward **all** public arguments unchanged. They provide
`SWCLI_DAEMON_UTILS` pointing to a separate shell script:

- DockerSW: `/usr/local/bin/swcli-daemon-utils` inside the container.
- MacSW: the actual App's `Contents/Resources/SWCLI/bin/swcli-daemon-utils`.

The utilities execute the real Windows daemon with the host-selected Wine,
prefix and Windows Python. They do not open another service, maintain daemon
state or parse the public CLI. The manager invokes literal `[utils, "start",
"--endpoint", ..., "--startup-timeout", ..., "--json"]` arguments. Host-only
CLI `serve`, `restart` and `doctor` are likewise parsed in Python and forwarded
as explicit utility actions. Status and stop use the existing native TCP client
without launching Wine. A delegation marker prevents recursive dispatch in the
Windows backend. POSIX startup runs in a separate OS session so closing MCP
does not kill the resident host.

For example, with an App installed in `/Applications`:

```json
{
  "mcpServers": {
    "swcli": {
      "command": "/Applications/MacSW.app/Contents/MacOS/sw-cli",
      "args": ["mcp", "serve"]
    }
  }
}
```

Adjust the App path to its actual location. To override its utilities, set
`SWCLI_DAEMON_UTILS` to an absolute executable script path in the MCP process
environment, or pass the global `--daemon-utils PATH` option before `mcp serve`.
It is a path, not a shell command string. The App/container native client must
contain this SWCLI version and its optional MCP dependencies; installing the
extra in an unrelated terminal Python does not update the packaged runtime.

An already-ready daemon is reused without changing visibility. Remote endpoints
are connection-only for startup: start the daemon on its host. A loopback
address may be a tunnel; configure the intended local launcher only when it
really manages that endpoint. Endpoint configuration does not add authentication,
encryption or file transfer. Keep the trusted boundary/tunnel and host path rules.

If the user has a visible SOLIDWORKS instance, default startup currently refuses
to create another host. `attach_existing:true` explicitly shares that instance
and preserves its window and ownership. Independent visible/hidden startup has
not passed both-host acceptance; do not bypass this guard with direct COM or
a different endpoint.

Native Windows MCP clients may put subprocesses in a kill-on-close Job Object.
The built-in launcher uses a demand-only, non-elevated current-user interactive
task to keep a requested resident daemon outside that job, removing its task
definition after startup. No password, boot/logon trigger or service is added.
If this path is unavailable, report the error and start explicitly from the
host terminal instead of repeatedly creating hosts.

At task completion, the agent can choose to keep the host ready or explicitly
stop it, based on the user's stated preferences, resource needs and expected
follow-up work. There is no rule requiring the agent to leave it running.
MCP disconnect **does not stop swclid or SOLIDWORKS**. `swcli_daemon_stop` and `sw-cli daemon stop` send the same
`daemon.shutdown` request and use the same protections. The tool returns its
structured result while keeping the MCP connection open; the CLI returns
text/JSON plus an exit code and finishes. Shutdown is explicit, affects all clients on the endpoint, and keeps MCP connected. It
uses the existing shutdown guard: an owned host with any open document refuses
shutdown; save/close only as authorized. An attached user's SW is preserved.
No native-operation retry, implicit restart or rollback is added.

### Runtime observations

`swcli_status` and `sw-cli daemon status --details --json` use the same read-only
snapshot. It reports daemon running/reachable/state, SW running, known ownership,
SW PID and window visibility, other processes, observation scope and probe errors.
`user_sw_running:null` means process origin cannot be established; a visible
unmanaged process is not automatically claimed as user-owned. Missing process
or window access stays unknown, not an empty list or hidden=false observation.
`visibility_current:false` labels startup-cached information. Remote process
observations come from the daemon host, never the client's PID namespace.
Older daemons fall back to health with that limitation stated. Basic
`daemon status --json` keeps its existing health response. This observes SW
windows; a tray controller is a separate planned feature.

## Discover, execute and check results

The five stable MCP tools are:

| Tool | Arguments and result |
| --- | --- |
| `swcli_status` | `{}`; read-only runtime snapshot, including unknown/stale fields. |
| `swcli_daemon_start` | Optional `visible`, `attach_existing`, `startup_timeout_seconds`; explicit start or reuse of the configured local host. |
| `swcli_daemon_stop` | Optional stable `request_id`; explicit shared-endpoint shutdown with existing document/ownership guards. |
| `swcli_capabilities` | `{}` for the small live operation/export summary; `{"operation":"document.properties"}` for that operation's exact input/result schemas and `x-swcli-context`. |
| `swcli_execute` | `operation`, `parameters`, plus the existing optional `session_id`, `document_id`, `expected_update_stamp`, `lease_id`, `request_id` context. |

Read the live operation schema before executing. Do not load all schemas by
default or infer support from this client's version. For example, after
obtaining the actual document ID:

```json
{
  "operation": "document.properties",
  "parameters": {},
  "document_id": "d-ab12cd"
}
```

`parameters` must match the selected operation schema. Context fields stay
outside `parameters`. Zero is a valid update stamp. IDs shown here are examples;
use fresh IDs returned by the daemon. There is no arbitrary COM/Python tool.
`daemon.shutdown` is reserved for the explicit lifecycle tool or CLI command.

Forwarded CAD tools return the **complete SWCLI protocol response** in `structuredContent`,
and the same JSON in a text content block. Manager lifecycle/status tools use
the same `success` and `result`/`error` fields with a request ID, without claiming
a daemon protocol envelope when no daemon is available. Check `isError` and
`structuredContent.success`; the operation payload is under `.result`, and
native refusal details are under `.error`. This differs from the CLI's flattened
`.ok` envelope. Invalid MCP arguments are rejected before forwarding.
Adapter/transport failures also return `success:false`, an error and request ID;
`outcome_unknown:true` means the operation may have executed. Preserve that ID,
inspect native state, and do not blindly retry or assume rollback.

Each MCP process generates a separate stable default session. Multiple MCP
processes can share a daemon, but this does **not** create independent models
or SW instances. Use explicit document IDs plus leases and fresh CAS stamps for
writes. `session_id` or `SWCLI_SESSION_ID` can deliberately select a shared
session when coordinating clients. One adapter's disconnection does not close
another's documents. Concurrent daemon startup is arbitrated by the existing
endpoint binding before a COM worker is acquired.

After modeling, verify native state/geometry and inspect an authorized render
or export through the usage guide. The initial adapter returns artifact paths
and metadata; it does not embed images or download remote artifacts through MCP.
