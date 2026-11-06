# Secure connections and workspace files

Available in SWCLI 0.2.3 or newer. Start the daemon explicitly on
its SOLIDWORKS host; connecting, transferring files and disconnecting never
start or stop SW. CAD and document ownership/session/lease/CAS rules still apply.

## TLS and authentication

The daemon's existing TCP endpoint can use TLS 1.2 or newer and a shared bearer
token. Configure a certificate and private key issued for the hostname clients
use. Clients verify the certificate chain and hostname; there is no insecure
verification switch or fallback to plaintext. Provision the token file on both
hosts through a trusted channel. It must contain 32–512 non-whitespace ASCII
characters; for example, generate a random token without printing it:

```powershell
python -c "import pathlib,secrets; pathlib.Path('token.txt').write_text(secrets.token_urlsafe(32))"
```

Restrict access to private keys and token files to the intended OS account. The
shared token grants that account access to all advertised daemon operations,
including CAD writes and explicit shutdown. Sessions and transfer IDs isolate
client state, not separate authenticated users. This is not multi-user RBAC or
an Internet-facing service with rate limiting. Use host firewall rules to limit
reachable clients. Rotate by replacing both token files and restarting the
daemon explicitly; the running server snapshots its token at startup.

On the Windows execution host, use its own paths:

```powershell
swcli daemon serve --host 0.0.0.0 --port 18495 --tray off `
  --tls-cert C:\Workspace\security\server.pem `
  --tls-key C:\Workspace\security\server-key.pem `
  --auth-token-file C:\Workspace\security\token.txt `
  --workspace C:\Workspace\exchange
```

The exchange directory must already exist. If sharing an already running user
SW is intended, explicitly add `--attach-existing`; preserve the user's documents.
The server also accepts `SWCLI_SERVER_TLS_CERT`, `SWCLI_SERVER_TLS_KEY`,
`SWCLI_SERVER_AUTH_TOKEN_FILE`, `SWCLI_WORKSPACE` and
`SWCLI_WORKSPACE_MAX_BYTES`. These are host configuration, not MCP tool arguments.
Native Windows startup tasks propagate these settings as paths/flags; token
contents do not enter command lines, RPC envelopes or request replay caches.
Wine/container/App adapters must configure their execution-side paths and
runtime separately, not reuse the client's Python or filesystem assumptions.

On the client / MCP server host:

```powershell
$env:SWCLI_ENDPOINT='cad.example.internal:18495'
$env:SWCLI_TLS_CA_FILE='C:\Workspace\security\ca.pem'
$env:SWCLI_AUTH_TOKEN_FILE='C:\Workspace\security\token.txt'
$env:SWCLI_CLIENT_WORKSPACE='C:\Workspace\client-files'
swcli capabilities --json
swcli mcp serve
```

Use `SWCLI_TLS=1` instead of a CA file for a certificate trusted by the system.
`SWCLI_TLS_SERVER_NAME` can specify the certificate hostname when connecting
through a tunnel or to a numeric address. It changes the expected hostname,
not certificate verification. A token or server-name setting without TLS is
rejected. TLS configuration, trust and authentication failures occur before the
CAD request is submitted; do not repeatedly launch SW to fix them.

Plain loopback connections keep their existing behavior. The legacy explicit
`--allow-remote` flag is still an unauthenticated opt-in for a separately trusted
network/tunnel; it does not add TLS. A fully configured TLS listener does not
need that flag. Remote lifecycle startup remains host-owned and explicit.
`capabilities` reports the live `transport` and `workspace` configuration.

## Bounded file transfers

The server exposes only its configured workspace. The client/MCP server exposes
only `SWCLI_CLIENT_WORKSPACE` or global `--client-workspace PATH`. Both roots
must exist; parent subdirectories for uploaded/downloaded files are created
inside them. Relative paths may contain spaces and Unicode. Absolute paths,
parent traversal, device names, alternate data streams, reserved staging names,
symlinks, junctions/reparse points and hard-linked input files are refused.
Do not point either root at a broad home or system directory.

```powershell
swcli transfer upload 'parts\body.SLDPRT' 'incoming\body.SLDPRT' --json
swcli transfer download 'exports\body.step' 'received\body.step' --json
```

The first path belongs to the source root and the second to the destination
root. On upload, the source is client-side; on download, it is daemon-side.
CAD `document.open`/`export` paths still belong to the daemon host; transfer does
not open, save, rebuild or re-export models. Export into the configured daemon
workspace first, then download that relative path. Check the export's CAD
success independently of file delivery.

Files travel in at most 1 MiB chunks, with streaming SHA256 verification. The
default per-file limit is 1 GiB; only the daemon administrator can change it
(`--workspace-max-bytes` / `SWCLI_WORKSPACE_MAX_BYTES`, at most 1 TiB). There are
at most four active uploads and eight active downloads. Temporary upload bytes
remain private until complete size/hash verification and atomic publication.
Default publication refuses an existing destination; use `--overwrite` only
with authority to replace it. Failed or interrupted transfers never publish an
incomplete destination; an existing destination remains intact.

An interrupted upload returns its `transfer_id` and `session_id`. Inspect its
status using the `workspace.upload-status` operation, then explicitly resume
with the same source, destination and session:

```powershell
swcli --session file-work transfer upload 'parts\body.SLDPRT' 'incoming\body.SLDPRT' --resume TRANSFER_ID --json
```

Use `--session file-work` for the initial upload too. `--request-id` identifies
one begin manifest; reusing it with a different manifest is rejected. Repeated
identical chunks and already committed upload IDs are safe to inspect/confirm;
there is no automatic network or CAD retry. Abort an unwanted upload with
`workspace.upload-abort`; it cannot remove a committed destination. Transfer
state expires after 30 minutes of inactivity, swept on subsequent transfer
requests or daemon shutdown. Restarting the daemon loses transfer state.
Completed receipts are bounded; this is not durable exactly-once storage across
restarts. Unexpected process termination can leave reserved staging files; the
API cannot read them and will not automatically delete untracked files.

A download pins and hashes an opened regular file, detects changes while
reading, and verifies the complete received hash before local publication.
A changing file or a failed connection is a transfer error, not evidence that
CAD failed; preserve the CAD result and inspect the transfer.

## MCP file tools

Configuring a client workspace adds `upload_file` and `download_file` to tool
discovery. Without that setting, the existing five tools remain. The optional
file tools accept `source`, `destination`, `overwrite` and `request_id`;
`upload_file` also accepts `resume_transfer`. All paths are relative to the
configured roots, which AI tool arguments cannot broaden. Progress reports
bytes when the MCP client requests notifications. The adapter streams chunks
internally instead of returning large base64 messages to the model.

```json
{"source":"exports/body.step","destination":"received/body.step"}
```

`download_file` saves the file into the **MCP server's client workspace**, which
may be different from the chat application's computer. Its small structured
result includes the destination path, size and SHA256. It does not claim every
MCP client can display or download a large attachment from that local path.
The existing render/export PNG/embedded-resource attachments retain their
8 MiB raw-byte limit and `artifact.content.status`; larger files use workspace
transfer instead. No arbitrary host-file read or public file server is added.
