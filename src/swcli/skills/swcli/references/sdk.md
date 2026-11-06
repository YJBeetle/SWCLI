# Typed Python SDK

SWCLI 0.2.4 provides `swcli.sdk` in the ordinary SWCLI package,
without the optional MCP dependencies. It supports Python 3.9+. Start swclid
explicitly on its execution host before using the SDK, for example with
`swcli daemon start`. Constructing `Client` and discovering its Python methods
never connect, launch SW, select a document or change window visibility.

## Typed methods and results

```python
from swcli.sdk import Client

client = Client(endpoint="127.0.0.1:18495", session_id="my-design-script")
# Small live discovery first; request one operation's schemas when needed.
client.daemon.capabilities(include_schemas=False).require_result()
client.daemon.capabilities(operation="document.inspect").require_result()

opened = client.document.open(
    path=r"C:\Workspace\parts\body.SLDPRT", read_only=True
).require_result()
document_id = opened["document"]["document_id"]
observed = client.document.inspect(document_id=document_id)
state = observed.require_result()["document"]
print(state["title"], state["update_stamp"])
```

All 63 operations in this SDK's catalog have typed, keyword-only methods and
request/result `TypedDict` models generated from the public schemas. For example:

| Protocol operation | Python method |
| --- | --- |
| `document.open` | `client.document.open(path=...)` |
| `document.units-set` | `client.document.units_set(...)` |
| `document.annotation-option-set` | `client.document.annotation_option_set(...)` |
| `document.property-set` | `client.document.property_set(...)` |
| `document.lease.acquire` | `client.document.lease.acquire(...)` |
| `feature.cut-extrude` | `client.feature.cut_extrude(...)` |
| `workspace.download-begin` | `client.workspace.download_begin(path=...)` |

The installed `py.typed` marker makes editor/type-checker information available.
`Response[DocumentInspectResult]` and models such as `DocumentState` are public
under `swcli.sdk` / `swcli.sdk.models`. Models are normal JSON dictionaries at
runtime, not a second set of CAD objects. Conditional fields remain optional:
only read a field when the successful operation contract or observed payload
provides it. Types describe data shapes; shared runtime validation still enforces
ranges, geometry constraints, conditional parameters and context eligibility.

`client.execute(operation, parameters, ...)` is the dynamic dictionary route for
operations known to this SDK. Prefer namespace methods for static checking.
The running daemon may support a smaller catalog or different version; inspect
its live capabilities. Unsupported operations return their actual refusal,
not a fallback to direct COM. An incompatible response raises `ProtocolError`
with the received raw payload; update/check client and host contracts rather
than silently discarding fields.

## Sessions, writes and lifecycle

Each new `Client` gets its own stable default session unless `session_id` or
`SWCLI_SESSION_ID` explicitly selects one. Reuse that Client for a workflow.
A new client/session does not create a new SW instance or independent model.
Paths in CAD parameters belong to the daemon host; the SDK does not reinterpret
Windows/Wine paths as paths on the Python client's machine.

Document IDs, lease IDs and CAS stamps are explicit keyword arguments whenever
the operation supports them. Zero, false, an empty string and an omitted
optional parameter remain distinct. `UNSET` explicitly omits an optional
parameter; `None` is not converted into an empty native value. For an authorized
unit change, use the lease and stamp already observed in the same workflow:

```python
reply = client.document.units_set(
    length_unit="mm", decimal_places=3,
    document_id=document_id,
    expected_update_stamp=observed_stamp,
    lease_id=held_lease_id,
    request_id=stable_write_request_id,
)
```

The SDK does not automatically acquire/renew/release leases, refresh a stamp,
choose a new entity handle, save or close a document. It does not retry native
operations or perform rollback. IDs can become stale after rebuild, close or
configuration changes; follow the same native discovery rules as the CLI.

There is no automatic daemon startup or shutdown, context-manager teardown,
destructor shutdown or ownership transfer. Explicit `client.daemon.shutdown()`
sends the existing global shutdown operation and retains its document/user-host
protections. It affects all clients sharing that endpoint. Start/restart and
Wine/runtime selection remain the existing CLI/MCP host-manager responsibility.

## Inspecting refusals and unknown outcomes

Every namespace call returns a `Response[T]`. `.success` is the protocol status;
`.ok` additionally checks a native result's `ok`. The reply is not turned into
an exception until the caller explicitly calls `.require_result()`.

```python
from swcli.sdk import ProtocolError, RemoteError, TransportError

try:
    reply = client.document.inspect(document_id=document_id,
                                    request_id="inspect-current-state")
    if not reply.ok:
        print(reply.request_id, reply.error, reply.raw)
    else:
        print(reply.require_result()["document"])
except TransportError as error:
    # Before-connect, TLS or authentication failures are known not submitted.
    # A missing/unusable reply after submission may have changed native state.
    print(error.request_id, error.phase, error.outcome_unknown)
except ProtocolError as error:
    print(error.request_id, error.raw, error.outcome_unknown)
```

`.result`, `.raw`, `.error`, `.duration_ms` and `.replayed` retain the daemon's
receipt, including partial-state details. `.require_result()` raises
`RemoteError` on a received protocol/native refusal and retains that same
`response`. An SDK transport exception preserves the original exception as
`__cause__`; no automatic retry or second SW launch occurs. Keep the request ID,
inspect native state before retrying a write, and distinguish delivery failure
from CAD failure. Request replay remains bounded by the daemon's advertised
cache and does not survive daemon restart.

## TLS and workspace files

The SDK uses the same environment configuration as the CLI by default. Optional
`TLSConfig` supplies certificate-verified settings for just one Client, without
changing process environment or affecting another Client:

```python
from swcli.sdk import Client, TLSConfig

remote = Client(
    endpoint="cad.example.internal:18495",
    tls=TLSConfig(ca_file="security/ca.pem", token_file="security/token.txt",
                  server_name="cad.example.internal"),
    client_workspace="client-files",
)
upload = remote.files.upload("parts/body.SLDPRT", "incoming/body.SLDPRT")
download = remote.files.download("exports/body.step", "received/body.step")
print(download["local_path"], download["sha256"])
```

The directories must exist. Per-client TLS snapshots its certificate/token
configuration; create a new Client after rotating them. File transfer reuses
bounded chunks, hashing, atomic publication, explicit overwrite and explicit
upload resume. It does not run a CAD export, embed unlimited bytes in the result,
or read outside the configured roots. A failed transfer raises the existing
`TransferError` with its transfer/session IDs when available. Byte progress is
an optional `progress(done_bytes, total_bytes)` callback. See
[the remote/workspace guide](remote-files.md) for security and recovery limits.

## Maintaining generated types

When operation/result schemas change, run `python scripts/dev/generate-sdk.py`
from the source checkout, then `python scripts/ci/verify-sdk-types.py` with mypy
installed. CI checks generation drift and representative consumer acceptance
and refusal. Generated data shapes do not replace native functional gates.
