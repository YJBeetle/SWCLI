# a8 installed face/edge CLI — Windows receipt

Status: **narrow installed Windows proof passed**, not a hosted delivery gate,
Wine proof or a published a8 release. Source candidate: `b3dd286`.

## Shared gate increment

`scripts/ci/verify-modeling.py` now observes edges on its existing analytical
box/blind-hole depth fixture. It requires 8 faces and 14 edges: 12 complete box
lines and 2 radius-3 circles at the blind-hole entry/bottom. Raw endpoints,
untrimmed line roots/directions and circle centers/axes/radii are checked without
inferring a public edge length, closure or normalized trim.

The required sequence preserves exact IDs on repeated reads and across mixed
face/edge discovery, rejects wrong-kind/cross-document/CAS requests, retires both
kinds after real depth writes, and requires disjoint new IDs after native
save/close/read-only reopen. It uses only the installed public CLI and the same
host, without adding an artifact to the six-export gate.

**185 directly related portable tests passed.** Gate fault tests reject wrong or
duplicated geometry, tilted axes, incompatible fields, face-registry eviction,
acceptance of stale edges and reopened-ID reuse. Reordered traversal and opposite
native curve/edge sense remain valid. A virtual slow host also passes: renewals
are inserted between bounded read/refusal groups, not a longer lease TTL or a
retry of an operation. These tests are not native CAD proof.

## Actual installed Windows proof

A fresh venv under `C:\Workspace\SWCLI-tests\edge-installed-qh2jfV-v2`
installed the built `0.1.0a8.dev0` wheel with its normal platform dependencies,
including pywin32 312 and jsonschema 4.26.0. The isolated installed-resource check
passed. Every business command runs `python -I -m swcli` from that venv, through
TCP `127.0.0.1:18578` to an installed daemon/worker from the same distribution.
No production module is imported from the checkout or injected with PYTHONPATH.

The daemon explicitly attaches to the existing visible SOLIDWORKS 2025
`33.5.0`, PID **1096**, and reports shared-interactive ownership. The temporary
harness uses native COM only to snapshot the original user documents and restore
their foreground around public opens/cleanup. It reuses the shared gate's actual
face/edge observation methods rather than copying geometry assertions.

The **73** recorded public commands include **29 entity requests**: **18**
successful observations and **11** expected refusals (7 `EntityNotFound`,
2 `DocumentUpdateConflict`, 2 `DocumentNotFound`). Both openings of the same
own read-only copy return:

- 8 exact faces and 14 exact edges, with the expected analytical fixture geometry;
- repeated identical ID-to-descriptor maps, line/circle inspection and a live
  face inspection after edge discovery;
- lease-free background observations while another session holds the writer
  lease, preserving reader current and native foreground;
- wrong-kind, wrong-stamp, cross-document and closed-document refusal;
- all face/edge IDs newly issued and disjoint from the prior opening; an expired
  edge ID is rejected against the reopened document.

The copy remains unmodified, background and in the same native state (stamp
**146**); source file bytes are unchanged. Cleanup closes only that copy and
stops only the attached test daemon. Original native document identities,
`零件1` stamp 102/modified false, foreground and SW PID are preserved. Cleanup
errors are empty; the user SW instance remains running.

The paired native trace contains **24,616** records / **12,308** complete call
pairs across approximately **195.97 seconds**. Its 11 error endings are exactly
the expected outer operation refusals above; no native COM method failed.

## First harness failure retained

The first temporary harness did not create the shared gate's exclusive evidence
file before its first checkpoint. It stopped with `FileNotFoundError` **before
sending the capabilities/business request**. The attached test daemon was
stopped, and original SW/documents were preserved. Its logs remain under
`first-harness-failure/`; no `modeling.json` was produced. The harness was aligned
with the normal shared entry point's exclusive file initialization and rerun in
a new workspace. No failed native CAD operation was retried or bypassed.

## Provenance

Local evidence: `/private/tmp/swcli-a8-edge-installed.qh2jfV`.

| Evidence | SHA-256 |
| --- | --- |
| wheel | `ffd65aef262cf3e33a74e8a5f6fdb2baee743931c21720a904bd9d70ebbaad9f` |
| shared `verify-modeling.py` | `82ff9607417fddaeb1aaa28319f5f4c5deea1ecc4acb4b79efa5a439326153cb` |
| `modeling.json` | `5673bc0ed41586842e44ff2fa48a5b269fc1023900a503de5783a31cfeeb2222` |
| `daemon-stderr.log` | `2d9af5184acf5d058d3c938de5bc9e5f0a6bc41f4b5c2a5bff371f1cb0529781` |
| `install.log` | `ae3f6a52064045a4e5b7cd2ce00109fb175d4bd56fc7cd332cfad4fce369a54f` |
| corrected temporary harness | `b50f80a4dd34a99ca4d134fd44d4ed9b0ed1c13f984f279bc024d158a67a60b3` |
| first harness `stdout.log` | `1233b0f891ea24498aed4be8edf57a4551fce41615d94ed12a86fd2130d3897d` |
| first harness `stderr.log` | `0bc8e25d44f3d5bce4c6c073cef5c5e2997a5a1096d51a0228dbd32638b6e9eb` |
| fixture before/after | `368bb2a8c23c6d811f2013e2e9e9d8fb9b009cecaa3362e143147cb0c5d70729` |

## Remaining proof boundary

This is not the complete generated-modeling/depth-write sequence on an empty
disposable host, nor hosted Windows visible/hidden or independent Wine delivery
proof. In particular, native edge retirement after an actual depth write remains
a shared-gate requirement, not established by this read-only copy check.
Topology-edit survival, trimmed boundary semantics, modifying consumers and a8
publication remain outside this increment. MacSW and DockerSW integration pins
were not changed.
