# a8 internal edge observation — 2026-10-10

This is current-source internal Windows proof, not public edge commands,
installed-wheel/HTTP/Wine support or topology-change survival.

## Implemented boundary

`7c86ab6` adds raw edge parameters and untrimmed line/circle geometry.
`f46084a` adds complete bounded single-solid ownership, exact native uniqueness,
private persistent-reference round trips, final complete-set verification and
unchanged configuration/stamp/modified/edit/foreground checks.

The reader requires a complete 1–64-edge set including hidden solid bodies and
rejects empty, multibody, surface-body, malformed and over-limit observations.
A reordered final array is allowed only when the exact native set is unchanged;
same-count replacement is not identity. Supported malformed geometry fails;
other curve kinds are explicitly unavailable. No partial records or bindings
are published after a failure.

Raw Sense and U parameters are retained separately from analytic geometry.
There is no interval normalization, length, closure, seam, adjacency or feature
ownership contract yet. Public `entity.list/inspect` still observes faces only.

## Actual current-source observer

The exact production helpers at `f46084a` were copied into a new private
Windows workspace and imported using an existing isolated Python environment.
This was not an installation upgrade or an installed public operation test.

The user's visible SOLIDWORKS 2025 `33.5.0`, PID **1096**, remained in place.
Only a new read-only copy of the existing 100×50×20 mm boss/radius-3/depth-5 cut
fixture was opened. Two consecutive complete observations returned **14** edges:
12 lines and 2 circles, with identical payloads and exact native bindings.
Native parameter/analytic arrays independently matched the adapter's converted
points, directions and radius; all references resolved to their exact edges.

The fixture configuration remained `默认`, stamp **146 → 146**, modified false,
not editing. It remained background with the same foreground identity. Closing
only the copy and restoring foreground preserved the user's original document
identity/state (`零件1`, stamp 102, modified false) and the same SW process.
Cleanup errors were empty. The observer made no selection, rebuild,
solver/display-setting change or save. The harness explicitly restored the
original foreground around opening/closing its copy; no daemon/SW restart or
Wine operation ran.

All observed native edge senses were **true**. Opposite sense retention has
portable tests, but this fixture does **not** prove normalization for false-sense
edges or any closed-edge interpretation. Do not upgrade that boundary to a
trimmed-length or fillet contract.

## Provenance

Local evidence: `/private/tmp/swcli-edge-observer-native.A26UAx`.
Windows workspace: `C:\Workspace\SWCLI-tests\edge-observer-A26UAx`.

| Evidence/source | SHA-256 |
| --- | --- |
| `observer-native.json` | `1404a3460f6243833509d65efdb11262e1abe9da2c018bd7431f2c18105049e4` |
| `trace.log` | `442d456085e4d02844f9bd85e40c4032f705cf7ace5b7f65d824b6b6f08247cf` |
| edge observer | `e4e0f8762d5cb05713cb188806e5a9e40e43ca1cf7adbc8a8e3595f5a07ca31d` |
| edge geometry | `ca72020bb6c312c51473f717ca63ae00e3475cf72b57696f8b7a1e103ab2b618` |
| reference helper | `ff926e17a384e3826668d769ad98b3e3515a8a36deea0aac0cfc17896bc97a6e` |
| fixture before/after | `368bb2a8c23c6d811f2013e2e9e9d8fb9b009cecaa3362e143147cb0c5d70729` |

The trace has 2884 JSON records, paired begin/end request/sequence boundaries
and no error phase. Selected outer native-call durations total about 12.88 s
across both reads; this is a bounded fixture measurement, not a scalability or
latency promise. Reference bytes remain private and are not included in the
observation payload.

## Portable proof and next boundary

All **115** related edge geometry/observer, existing face geometry/observer/reference,
native trace and entity registry/operation/result-contract tests pass. System
Python lacked `jsonschema`; protocol tests use the existing isolated test
environment rather than installing into or changing system Python.

Next work is explicit edge-handle lifecycle and contract wiring, then installed
Windows and independent Wine gates. Same-scope exact identity, mixed face/edge
handle ownership, stale references and incomplete-set refusal must be proved
before a modifying consumer. No MacSW repository, CI or main bottle was operated
for this increment; DockerSW's integration source and pin were not changed.
