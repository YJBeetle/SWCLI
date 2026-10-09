# a7 feature observation: development verification

This records read-only development proof, **not an a7 release** or feature-edit
support. The public implementation is `cc1ba7e5295b92e50d5f57da8e443b9d91298975`,
following registry `a13c470` and native observer `259cf34`. Package version is
`0.1.0a7.dev0`; the public a6 assets remain unchanged.

## Portable contracts

886 tests passed, with eight Windows-only tests skipped on macOS. New coverage
includes exact native feature identity/lifetime, bounded/cycle-safe traversal,
strict native flags, nonmutating state snapshots, request/result/CLI contracts,
background leased reads, update-stamp refusal and no partial wire handles.
Shared-gate tests additionally reject wrong native depth and observation drift,
and preserve holder leases during simulated slow observation groups.

## Native Windows read-only proof

SOLIDWORKS 2025 revision `33.5.0`, Windows ARM64 with AMD64 Python 3.14.7 and
pywin32 312. Explicitly shared existing SW PID **1096**; the probe did not stop
it or replace it. Test documents/files were limited to
`C:\Workspace\SWCLI-tests\a7-feature-read-FFzBLq`.

The internal probe created a 100×50×20 mm boss and a radius-3 mm, depth-5 mm
cut, then observed them with another part in the foreground. The public probe
opened only that saved test file read-only and exercised the actual CLI over TCP
against a disposable shared COM worker. Both probes passed and cleaned up their
test documents; original documents/foreground and the same SW PID were preserved.

- Native boss depth **20 mm**, type `Extrusion`; native cut depth **5 mm**,
  displayed type `ICE` with underlying type `Cut`.
- Complete unchanged configuration/edit/modified/stamp/foreground observations.
  Test part stamp **146** remained 146; reopened reads kept `modified: false`.
- Rename and repeated observations reused live handles. Close/reopen allocated
  fresh IDs; public inspection of a retired ID returned `FeatureNotFound`.
- Public capability Schema matched; stale-stamp reads returned
  `DocumentUpdateConflict`. Depth-write capability was absent.

Local raw evidence was retained under the test workspace and copied to
`/private/tmp/swcli-a7-feature-read.FFzBLq/`:

| Evidence | SHA256 |
| --- | --- |
| `feature-read.json` | `25157e1363a306c07e00aea74af22c6faadaadadb75d7485d98f4590456bb618` |
| `feature-public.json` | `1b9a6b064b28d0dda4d24ec849459c2ec6d192a664b94120dd86d00a72252ac6` |

These are local, non-hosted artifacts, not public CI attestations. The public
probe read without a write token on a leased test document; the distinct
non-holder session path is covered by portable contracts and the new shared gate.

## Still pending

- Hosted Windows execution of the extended shared modeling gate.
- Linux/Wine and macOS/Wine runtime proof for these new operations; older a6
  host passes do not establish a7 feature support.
- Exact feature handles in creation results and guarded blind depth edits,
  including protected-control checks and rollback/restoration ownership.
- Formal a7 candidate, release assets and distribution verification.

No setter, automatic retry, source save, transaction rollback or host restart is
part of the feature read path.
