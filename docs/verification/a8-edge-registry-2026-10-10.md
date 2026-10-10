# a8 internal mixed face/edge registry — 2026-10-10

This verifies current-source internal Windows registry behavior, not installed
edge CLI/HTTP support, Wine, topology edits or native scope-change survival.

## Implemented boundary

`7bd7fe1` adds edge bindings to the existing DocumentRegistry-owned EntityRegistry.
Faces and edges have separate complete sets but share configuration/update-stamp,
body ownership and the worker-wide issued-token set. Same-scope repetition reuses
only exact native identities. Observed scope changes permanently retire both
kinds; failed batches do not publish partial IDs. Resolution defaults to faces
and requires explicit edge kind for an edge ID. Public commands still expose
faces only.

All **130** related portable tests pass, including 15 mixed-kind registry cases.
These prove conservative scope retirement, native-error atomicity, cross-kind
body/reference conflict refusal, wrong-kind/document rejection and lifecycle
wiring. Scope-change proof in this increment is portable, not a real model edit.

## Actual current-source Windows proof

Production sources at `7bd7fe1db765189719211545a40e7cac58735cb4` were copied into
an independent Windows workspace and imported using the existing isolated test
Python. The harness attached to the user's existing visible SOLIDWORKS 2025
`33.5.0`, PID **1096**, without restarting it or changing the installed package.

It opened only its own read-only copy of the existing boss/circular-cut fixture.
For each of two openings, two complete observations yielded **8 faces + 14
edges**, registered disjoint short IDs and independently checked exact native
resolution. Repeated observations and reversed complete-set registration reused
the same IDs without removing the other kind. Every wrong-kind lookup failed.

External native CloseDoc followed by DocumentRegistry.sync invalidated both
kinds, including retained registry objects. Reopening the same path produced a
new registry and IDs disjoint from all previously issued face/edge IDs. Neither
native model objects nor reference bytes were used as a serialized public ID.

Each opening stayed in configuration `默认`, stamp **146**, modified false,
not editing, and background with the original foreground identity. The copied
file hash remained unchanged. After both closes, the original document set,
native identities, foreground, SW PID and user document state (`零件1`, stamp
102, modified false) were unchanged. Cleanup errors were empty. No selection,
rebuild, save, solver/display setting or Wine operation ran; only the harness
restored foreground around opening/closing its copy.

## Provenance

Local evidence: `/private/tmp/swcli-edge-registry-native.G9zwSq`.
Windows workspace: `C:\Workspace\SWCLI-tests\edge-registry-G9zwSq`.

| Evidence/source | SHA-256 |
| --- | --- |
| `registry-native.json` | `a840e5589d6cb09908c223b07f4c0b406dea444426362098b667d481785af505` |
| `trace.log` | `149d838950fbf3827342b7dbbe8e0e1febf2dcac81816c3cca464d82243d7535` |
| registry | `c995a96b8bbca8e53d65cdd9c5ef1ab53fa365e237ea4a7db887e2c818cfb825` |
| owning document registry | `16b52bae229986a15a6f9e8581987f6eaea3c277d5ae40500447d2904ef207a4` |
| face observer | `5d512296ffdda2e55bf3a47c724acef7ffa3bc716dcb3e3320339497832c5b63` |
| edge observer | `e4e0f8762d5cb05713cb188806e5a9e40e43ca1cf7adbc8a8e3595f5a07ca31d` |
| edge geometry | `ca72020bb6c312c51473f717ca63ae00e3475cf72b57696f8b7a1e103ab2b618` |
| reference helper | `ff926e17a384e3826668d769ad98b3e3515a8a36deea0aac0cfc17896bc97a6e` |
| fixture before/after | `368bb2a8c23c6d811f2013e2e9e9d8fb9b009cecaa3362e143147cb0c5d70729` |

All copied production hashes match this checkout. The trace contains **12888**
JSON records, **6444** paired request/sequence begin/end boundaries and no error
phase. Four outer observation/registration intervals total about **94.04 s**;
this includes extra test re-registration and is not a public latency guarantee.

## Next boundary

Wire explicit kind-aware edge parameters/results into the operation catalog and
CLI, then prove installed Windows and independent Wine gates. Do not infer edge
length, closure, seam, adjacency, editing permission or topology-edit survival
from this receipt. MacSW remains paused and unchanged; DockerSW's integration
source and pin were not changed.
