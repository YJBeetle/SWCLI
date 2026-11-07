---
name: swcli
description: Use SWCLI for SOLIDWORKS CAD automation through the CLI or MCP backed by swclid. Applies to reading or editing file summary and document/configuration custom properties, inspecting the active model, opening, modeling, rendering or exporting SLDPRT, SLDASM, SLDDRW and CAD STEP/STP files, and checking capabilities for assemblies, motion studies and other SOLIDWORKS features.
---

# SWCLI

The client command is `swcli`. The resident daemon is called `swclid` and is
managed through `swcli daemon`; it is not a separate installed command.

Use the typed CLI or MCP for operations the running daemon advertises. If the operation is missing
or its documented scope excludes the task, consult the
[official SOLIDWORKS API workflow](references/solidworks-api.md). A failure
of a supported operation follows the CLI's diagnostic and recovery path.

Read [the usage guide](references/usage.md) when preparing a metadata, modeling
or export workflow, or connecting to an unfamiliar host. The guide travels with this
skill; it does not depend on the developer's machine or repository checkout.

For MCP client configuration, explicit lifecycle, host launchers, sessions and protocol
response fields, read [the MCP guide](references/mcp.md). `swcli mcp serve`
uses stdio and reuses the existing daemon; it is not an HTTP listener.

For a Python automation script, use the [typed SDK guide](references/sdk.md).
The SDK reuses this daemon and the same operations; it does not own SW lifetime,
retry writes or refresh leases/CAS implicitly.

## Working rules

- With MCP, first call `status`; explicitly use `daemon_start` if a
  host is needed, then `capabilities`. Daemon and SW startup takes time;
  wait for readiness and inspect status after a timeout before another start. Request the
  selected operation schema before `execute`. For a new CLI connection, run
  `swcli version --json`, `swcli daemon status --details --json` and
  `swcli capabilities --json`. Read the capability summary, then
  request `capabilities --operation NAME --json` for the needed request/result
  schemas and context, instead of loading all schemas with `--full`.
  Older clients may have only the full default view: check local `--help`.
  The running daemon is authoritative; do not assume a newer README's operation
  exists. See the guide for current modeling limits and JSON field paths.
- Use `--json` and check the process exit code as well as the response. Successful
  daemon management and CAD results have different envelopes; a connection
  failure is not an empty document list.
- Choose a session and explicit document IDs for multi-document work. Omitting
  `--document` means the session's current document. Use `--document active` for the active
  SOLIDWORKS document.
- Read document state before modifying it. Use a lease and the observed update
  stamp for cooperating writers; zero is a valid stamp. These guards are not
  filesystem locks or protection from human edits.
- Use explicit units and object handles returned by the daemon. Do not guess
  localized feature/plane names or infer a handle from a filename or tree index.
- For file metadata, discover the needed `document.summary`, `document.properties`
  and setter operations individually. Read the guide's file-metadata workflow
  before writing. Document and configuration property scopes are independent;
  preserve raw expressions and use the observed raw value for `--if-value`.
  Keep the session, lease and fresh update stamp consistent, verify readback,
  then save only when the task authorizes persistence. Unit, font and drafting
  settings under SOLIDWORKS Options > Document Properties need their own
  advertised operations or the official API workflow.
- For document display units or annotation options, read the usage guide's
  document-options section and request `document.units`/`document.units-set` or
  `document.annotation-options`/`document.annotation-option-set` schemas. The
  supported fields and document types are bounded; do not infer font or
  overall drafting-standard support from these operations.
- Before modeling, editing features, observing entities or creating drawings,
  read the [modeling rules](references/modeling-rules.md) and only the relevant
  workflow section of the usage guide. These preserve native scope and stale-handle boundaries.
- For part display quality, discover `document.image-quality` separately from
  export operations. `document.image-quality-set` permits only its verified native Windows
  revision/runtime and bounded targets; other writes fail closed. A complete quality CAS snapshot, lease
  and update stamp are mandatory. Do not equate these settings with GLB export
  options or claim GLB subdivision control without decoded mesh evidence.
- For an advertised `document.annotation-font`, `document.display-options` or
  `document.drafting-standard` pair, request its own schema and read the guide's
  bounded preference contract. New setters require an explicit lease, fresh
  update stamp and exact field/full-snapshot CAS. Only overall annotation font
  and a finite standard observation profile are covered; unknown/custom
  standards, subtype fonts and unobserved page settings remain separate work.
- For MCP previews or file delivery, use `execute` with `document.render` or
  `document.export`. Check both CAD success and `artifact.content.status`;
  consume the returned image/resource block, not a client-side host path.
  See the [MCP artifact guide](references/mcp.md#rendered-images-and-exported-file-content)
  for size limits and metadata-only mode.
- For CI acceptance use `document export --strict`. Do not suppress source
  saving/rebuilding problems just to obtain a green pipeline.
- Treat CAD paths as paths on the execution host. For remote TLS/token setup or
  files larger than the inline limit, read the [workspace transfer guide](references/remote-files.md).
  Use configured client/daemon roots with `upload_file` / `download_file` or
  `swcli transfer`; downloading saves to the MCP server's client workspace,
  not automatically to the chat UI. Never redo a successful CAD export to retry delivery.
  `--allow-remote` does not provide authentication.
- At task completion, choose whether to keep the host ready or explicitly call
  `daemon_stop` using the user's stated preferences and expected follow-up
  work. MCP disconnect leaves the host running. Stopping affects all clients
  on that endpoint and does not authorize discarding or closing unrelated work.
- MCP and CLI CAD/status calls do not start SW implicitly. Explicit MCP
  lifecycle tools and CLI daemon commands share the host manager; Wine startup
  uses the configured daemon utilities, not the client Python. Starting/restarting/
  stopping a daemon changes the host lifecycle. Obtain the
  necessary user authority and never terminate another user's interactive host.
  Visible Windows tests use `daemon start --visible` or `daemon serve --visible`.

Keep actual design choices and acceptance criteria with the user's task. This
skill explains execution, not mechanical-design approval or permission to save,
overwrite, close, publish, or alter unrelated documents.
