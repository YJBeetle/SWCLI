# a7 guarded feature-depth runtime verification — 2026-10-10

This is development runtime evidence for `0.1.0a7.dev0`, not a formal a7 release,
published wheel or DockerSW image-promotion claim. The earlier adapter, source
CLI and read-only-refusal proofs are in the
[feature observation record](a7-feature-observation-2026-10-10.md).

## Installed hosted Windows

[SWCLI CI 38034020992](https://github.com/YJBeetle/SWCLI/actions/runs/38034020992)
passed at **`57f221a81464abd11f2eae0c2f48103050b9f8c6`**. Both Python 3.9/3.14
unit jobs, distributions and fresh installed native runtime passed. Independently
downloaded terminal artifacts confirm the shared modeling and driving records:

| Mode | SW PID | Modeling events | Driving events | Result |
| --- | --- | --- | --- | --- |
| visible | 5016 | 158 | 598 | completed, success, no cleanup errors |
| hidden | 9148 | 158 | 598 | completed, success, no cleanup errors |

Each mode retained its SW2025 `33.5.0` instance throughout both gates. The new
single-solid background fixture reused exact boss/cut creation handles, refused
missing leases and stale stamps, changed boss **20 → 25 mm** then cut **5 → 8 mm**,
and measured **124858.62833058843 → 124773.80532894151 mm³**. Equal-depth calls
had all mutation flags false and no rebuild, while owned selection access moved
the stamp **174 → 176** and **184 → 186**. Foreground/session restoration,
current-configuration scope and native selection release passed.

Native save/close/read-only reopen recovered fresh feature IDs with depths
25/8 mm and the same expected solid volume. Read-only set-depth was refused
with `DocumentNotWritable` before access or staging, preserving document state.
The original rejected-cut continuation, installed sample exports, dimensions,
render and lifecycle gates also passed. These fixtures do not establish support
for arbitrary feature profiles, references, configurations or protected controls.

Artifact: `swcli-windows-hosted-38034020992-1`.

| Terminal record | SHA-256 |
| --- | --- |
| visible `modeling/modeling.json` | `5e220d653723e3f36f6483e6cd0d5e21e3961669289e82cfc0c6edbfd986476c` |
| visible `driving-dimensions/driving-dimensions.json` | `0d7e3561ee87e32d23a39c15ef1717d4ec04fc2223bbb7292c5d6d9c5ac43665` |
| hidden `modeling/modeling.json` | `d6869ff21ba8bd524db33e4141deee484af66f3d6d49f777f95606aa0e88a746` |
| hidden `driving-dimensions/driving-dimensions.json` | `9ecc451fcf01c0c2f70fcb927825a9409cce8419951be65203ef1029cf629e59` |

Local download: `/private/tmp/swcli-ci-38034020992-depth`.

## Independent Linux/Wine: initial failures preserved

On the user's trusted `workspaceroot`, an independent disposable container used
existing base image **`843436fefe1a`** (`sw-executable:2025-zh-cn-cli`) and the exact
source archive of `57f221a`, mounted read-only. This is an old base with a new
source overlay, not the current DockerSW delivery image. Its hidden owned SW2025
`33.5.0` instance is PID **596**. The archive SHA-256 is
`400d7cf1e48573c14c05adaabeea995fa96395e2f39203ed86a43599115fa1f0`.

The first attempt failed during capability discovery because the old base's
Linux Python lacked `jsonschema`; no CAD operation ran. The existing formal
dependency payload was copied from local image `d69ff56f1ea3`, and its Windows
dependencies were added to the disposable container's Python site-packages.
No published image was changed and SW PID 596 was not restarted.

The second attempt passed the existing modeling/read/save/reopen cases and all
four actual boss/cut depth/equal-depth calls. It then failed the gate's raw
dictionary-equality assertion: independently measured cut volume differed by
about **3×10⁻¹¹ mm³** between consecutive calls
(`124773.80532894151` versus `124773.80532894148`). All equal-depth mutation flags
were false, no rebuild was reported, and body count/area/centroid agreed. This is
not evidence of a native setter failure or a dead host. Cleanup closed the
gate's own documents without errors; SW PID 596 remained connected.

First depth-failure record SHA-256:
`727eee60e3a05120415c20bf35f498fbdacfe3d9beb85198e4623234dc9743f9`.
Both failed records remain under `/tmp/swcli-a7-depth-20261010.DZ6POg/evidence`;
the depth record was copied to
`/private/tmp/swcli-a7-depth-edit.BiQz5q/wine-first-depth-failure`.

Gate fix **`9795d1a`** replaces cross-call dictionary equality with independent
finite numeric checks for every metric: exact solid count, `max(1e-6, |baseline|
× 1e-12)` absolute tolerance for volume/area/each centroid axis. It retains strict
no-setter/no-commit/no-rebuild flags, the analytical-volume checks and all native
restoration assertions. Portable cases allow one-ULP roundoff but reject
`1e-4` metric changes, changed body counts, invalid values and mutation flags.
The full suite passed **1011 tests**, with eight Windows-only skips on macOS.

A new complete gate on fresh models uses that corrected script with the same
native runtime/host, not a retry of the previous CAD operations. Its outcome is
still pending; no complete Wine gate, promoted image or formal a7 host proof is
claimed here yet. macOS/Wine proof remains independent and pending.
