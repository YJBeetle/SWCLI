# a8 explicit edge operations — 2026-10-10

This proves current-source CLI argument mapping and actual Windows typed
handlers, not installed client/TCP, Wine, native topology-edit survival or a
published version. The shared installed modeling gate still checks faces; its
edge extension and installed cross-host proof remain the next integration step.

## Implementation and first failure

`6025fce` wires `entity.list/inspect --kind edge` through strict kind-aware
parameters/results and the existing shared document-local registry. Faces
remain the default. Count/scope/descriptor types are disjoint; limits apply to
the selected complete kind. Raw edge parameters are separate from untrimmed
line/circle geometry, with no length, closure or edit-authority claim.

The first actual typed read at that commit failed on the existing **face** path:
`OperationResultInvalid: entity.list: entity kind disagrees with observation scope`.
The semantic validator reused its collection-kind variable for the first face's
surface kind, so the second face was incorrectly rejected. This was a Python
contract regression, not a SOLIDWORKS crash or Wine failure. Original user state
was restored and the failing JSON/trace retained.

`2cc5fdd` separates collection kind from surface classification and adds complete
multi-surface/multi-curve public/private response regression tests. The corrected
source was tested in a new Windows workspace with the same assertions and a new
read-only copy. No failing operation was retried within a running gate or changed
to a weaker assertion. Portable proof: **231** entity/CLI/protocol/result/schema/
sdist-related cases plus **22** existing shared modeling/sequence cases pass.

## Corrected actual Windows proof

The harness imports a copied production checkout at `2cc5fdd`, uses the actual
CLI parser/mapping, execute_operation handlers and public result validators.
It does not install a wheel or exercise socket transport. It attaches through
ROT to the unchanged visible SOLIDWORKS 2025 `33.5.0`, PID **1096**, and opens
only its own read-only boss/circular-cut copy.

The **15** calls include **8** successful observations and **7** expected
refusals. Complete reads return 8 faces and 14 edges (12 lines/2 circles).
Repeated edge reads preserve IDs and descriptors; line/circle inspections and
face inspection after edge discovery preserve their exact handles. A different
session holds the writer lease: lease-free observations do not activate the
background copy or change the reader's remembered current document.

Refusals cover CAS before issuance, default-face lookup of an edge, explicit-edge
lookup of a face, cross-document lookup, the wrong kind's limit, the closed owning
document and an expired edge ID after reopen. Reopening the same path issues face
and edge IDs disjoint from the previous opening. Every successful response passes
its actual result Schema and semantic validation.

The copied document stays in configuration `默认`, stamp **146**, modified false,
not editing and background; both observations bracket identical state. File
bytes remain unchanged. Cleanup closes only the copy and restores the original
foreground. The original document set/native identities, user document state
(`零件1`, stamp 102, modified false), foreground and SW PID are preserved;
cleanup errors are empty. There was no selection, rebuild, save, display/solver
change, daemon/SW restart or MacSW/Wine operation.

## Provenance

Local evidence: `/private/tmp/swcli-edge-registry-native.G9zwSq`.
Corrected Windows workspace: `C:\Workspace\SWCLI-tests\edge-typed-G9zwSq-v2`.
The previous failed workspace is `C:\Workspace\SWCLI-tests\edge-typed-G9zwSq`.

| Evidence/source | SHA-256 |
| --- | --- |
| `typed-native.json` | `5e28afb2d1066ce65739314d8e4a218f003ea27da1c4cfaa7d51b0e60be64c64` |
| `typed-trace.log` | `757abe4029960c698eee62c88c0bc52149c53e3ffe40d3e69a334341d5d067e9` |
| `typed-native-firstfailure.json` | `1f7fd99437c0787904717b900db185a603cf6643785687a30a466b34e6d1670a` |
| `typed-trace-firstfailure.log` | `11ec8899d486b840c12be2df748cc955e7089a7fead27ae488a97d0f32a8d5ae` |
| CLI | `7c65c87f7d0eb8106ae9c8d7a76986c11275bc09afc8a5f5f47afe9dd920929f` |
| typed handlers | `3d519608e4fa0e49c347adab3f5a7b1f8425bdb0c26b6e13b2040c0f83cbb9f2` |
| entity contracts | `c823080186d1025598a059a85577308ce0bfc23398f330b50ff95d21be125598` |
| operation catalog | `a1f9364c62b4e164c97614599ab14e15ed233ea14b5867d5abf6245f83aaf01e` |
| result schemas | `b49a88e4a1e99f567f4a7d7cf8b849163996175a60ef95b16d46525229ba36b7` |
| capabilities schema | `fb7e6cd948f87f6f60889bf298685c5f7ec0a8b7a255528c7b53386a172b02c5` |
| copied fixture before/after | `368bb2a8c23c6d811f2013e2e9e9d8fb9b009cecaa3362e143147cb0c5d70729` |

All copied production hashes match the corrected checkout, including the
unchanged registry/observer/reference helpers recorded in the preceding receipts.
The corrected trace contains **12302** JSON records and **6151** paired begin/end
boundaries with no native error phase. Expected refusals are caught inside the
harness's traced scope and recorded in JSON, so outer trace completion is not
itself proof of successful business execution. The outer intervals total about
**74.79 s**, a bounded fixture measurement, not a latency guarantee.

## Remaining boundary

Add edges to the existing shared installed-client modeling fixture: complete
line/circle geometry, repeat IDs, wrong-kind/document/CAS refusal, retirement
after real depth edits and fresh close/reopen IDs. Run formal installed Windows
and independent Linux/Wine gates at a coherent integration checkpoint. MacSW is
paused; neither its repository/main bottle nor DockerSW's source/pin was changed.
No trimmed-length, false-sense normalization, closure or modifying edge consumer
is validated here.
