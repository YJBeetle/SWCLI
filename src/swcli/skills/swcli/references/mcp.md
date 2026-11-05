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

The adapter does not start SOLIDWORKS during MCP initialization or `tools/list`.
At the first valid tool call, it probes a local daemon and explicitly starts
one if the endpoint is unreachable before a connection was established.
Local startup uses the same Windows runtime and authority as
`sw-cli daemon start`; the default is a hidden daemon-owned SOLIDWORKS instance.
It does not install SOLIDWORKS or discover a Wine runtime from a macOS/Linux
client. DockerSW normally already runs swclid; start its daemon through the
host's existing lifecycle command when needed.

For an existing daemon or a tunneled endpoint, use connection-only mode:

```json
{
  "mcpServers": {
    "swcli": {
      "command": "sw-cli",
      "args": ["--endpoint", "127.0.0.1:18495", "mcp", "serve", "--connect-only"]
    }
  }
}
```

Non-local endpoints are always connection-only. Endpoint configuration does
not provide authentication, encryption or file transfer; retain the existing
trusted boundary/tunnel and execution-host path rules. DockerSW's configured
path helper is reused; arbitrary remote files are not uploaded.

If a user already has a visible SOLIDWORKS instance, default startup currently
refuses to create another host. To explicitly share that instance, first run
`sw-cli daemon start --attach-existing --json` on its host, then connect MCP.
Attach preserves the visible host and does not take ownership. A repeated
`daemon start` at a running endpoint reuses it without changing visibility.
Independent visible/hidden process startup has not passed both-host acceptance;
do not bypass this guard with direct COM or a different endpoint.

Windows MCP clients may put subprocesses in a kill-on-close Job Object. For
that environment, lazy startup uses a demand-only current-user Windows task,
without elevation, passwords or boot/logon triggers, and removes its definition
after startup. If that startup path is unavailable, report the error; start the
daemon from the host terminal and use `--connect-only` instead of repeatedly
trying new hosts.

MCP EOF/disconnect/cancellation **does not stop swclid or SOLIDWORKS**. A new
MCP connection can reuse the host. Stop/restart remains an explicit, authorized
`sw-cli daemon` action. After an initial startup failure or a lost native
session, inspect the error and host state, recover explicitly, and reconnect;
the adapter does not repeatedly start hosts or retry failed native operations.

## Discover, execute and check results

The three stable MCP tools are:

| Tool | Arguments and result |
| --- | --- |
| `swcli_status` | `{}`; returns current daemon health and native host identity. |
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
`daemon.shutdown` is reserved for the explicit CLI lifecycle command.

MCP returns the **complete SWCLI protocol response** in `structuredContent`,
and the same JSON in a text content block. Check `isError` and
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
