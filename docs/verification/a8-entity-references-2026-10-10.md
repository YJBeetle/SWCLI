# a8 internal entity-reference binding — 2026-10-10

This records **Windows feasibility/adapter and typed-handler proof**, not an
installed-client/HTTP gate, Wine result or promise of topology survival. a7 remains
the published release; a8 development uses `0.1.0a8.dev0`.

## First failure and binding correction

The initial helper refused the first face because its strict byte-array check
accepted bytes/list/tuple but pywin32 returned **`builtins.memoryview`**. Native
type-only observation confirmed format `B`, dimension 1, item size 1, contiguous,
writable, length 563. No private reference bytes were printed. The earlier
test-only probe had used `bytes(raw)`, which had hidden this container difference.

The correction accepts only bounded, contiguous, one-dimensional unsigned-byte
memoryviews and immediately copies their bytes. Signed, multidimensional,
noncontiguous, released, empty and oversized buffers still fail. Resolution uses
UI1 SAFEARRAY input and a BYREF I4 sentinel; zero must actually be written and
the object must exist. Capture additionally requires exact native `IsSame == 1`.
Nonzero bitmasks, unknown statuses, boolean/numeric coercions and unsupported
identity do not become successful resolution. Native exceptions are preserved.
The **13 related portable tests pass**; no full/native gate was repeated.

## Actual helper on native Windows

A fresh read-only copy of the existing owned test fixture was opened in the
user's already-running SW2025 `33.5.0`, **PID 1096**. The exact production helper
captured and resolved all **8 faces**, with native identity checks passing.
Reference lengths were `[559, 559, 559, 559, 555, 555, 565, 515]`; reference
contents remained private. The original document set, their modified flags and
stamps, configuration, edit and foreground identities were unchanged. Only the
test copy was closed, the original foreground restored, and cleanup was empty.
No SOLIDWORKS or daemon process was started, terminated or restarted.

Trace records contain 8 capture, 16 resolution and 8 native comparison calls,
all with paired begin/end boundaries, totaling approximately 561 ms of native
call time on this host. That is a fixture measurement, not a general operation
latency guarantee.

| Evidence | SHA-256 |
| --- | --- |
| initial `helper-native-firstfailure.json` | `6321ae5b43d9189abee51f101a81bbe2a11e8f2dc4f5943e010b43aad87d56f5` |
| type-only failed observation | `46d272b21d7223af9e1f94b98f12e8a2e4bbadc5ac67f981ca13707e8f62627d` |
| successful `helper-native.json` | `2a01abd6f686216f7e37bb29d837799ac6ae53949244d460578bb5f665196b25` |
| successful `native-call-trace.log` | `4b4b94816920b5d4ac36263d3df0b2cfabce32ddd24c737c9e4bf84a012d1851` |
| tested helper source | `ff926e17a384e3826668d769ad98b3e3515a8a36deea0aac0cfc17896bc97a6e` |

Local evidence: `/private/tmp/swcli-a8-reference-helper.3C2pUY`. Work files are
under `C:\Workspace\SWCLI-tests`; the VM and the user's interactive SW remain
running. This round trip does **not** replace body/document ownership, complete
enumeration, entity-kind, stamp/configuration validity, registry lifetime or
post-edit topology checks. Public `entity.list/inspect` wiring and independent
host gates remain pending.

## Complete internal face observation

The next internal observer passed **12 related portable cases**, alongside the
13 binding cases, 11 native-trace cases and 18 existing feature-read cases. It
requires exactly one solid with no surface bodies, includes hidden bodies,
cross-checks the complete native face count, exact face/body ownership and native
duplicate identity, and only returns private bindings after the entire
configuration/stamp/edit/foreground check passes. Failed reads publish no
partial geometry or binding list. Planes/cylinders are observed, other surfaces
remain explicitly unclassified, and `area_mm2` carries `area_accuracy:
approximate`, following the documented
[IFace2.GetArea accuracy](https://help.solidworks.com/2018/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFace2~GetArea.html).

Its initial **64-face internal cap** bounds pairwise identity checks, not a
promise of scalable enumeration or a public limit. At this observer revision,
normal/radius geometry and short-handle lifetime were not yet implemented; the
following increments record those separately. Trimmed boundaries remain pending.

On another fresh read-only native fixture copy, the actual observer completed
**two consecutive reads** on SW PID **1096**, reporting one solid, 8 faces
(7 planes, 1 cylinder), identical complete payloads and binding lengths.
Default configuration, stamp 146, modified false, edit state and exact foreground
identity were unchanged. The original documents/state were preserved after
closing only the copy; cleanup was empty and SW was not replaced. Paired native
trace boundaries have no error; two reads total approximately 6.98 seconds of
native calls (including 90 identity comparisons). This highlights the need to
keep the current bounded probe separate from future enumeration scalability.

| Observer evidence | SHA-256 |
| --- | --- |
| `observer-native.json` | `77b928b70746e58ff9a421857bdaaa3138d1626aadc16242709fcc7d1880963b` |
| `native-call-trace.log` | `0c4f90875ea71167d9269a63d7d60fba083cd2708df34b5d38047beb228068a4` |
| observer source | `556a73f0041dd251ce26db1b48e141b48957fc5844bf9cbb775a57c99353e658` |

Local evidence: `/private/tmp/swcli-a8-observer-native.DvsH0i`. References source
is the same hash listed above. These are internal Windows results, not public
CLI, Wine or topology-edit survival proof.

## Short handles and owning-document lifetime

The internal EntityRegistry has 14 portable cases covering exact-identity reuse,
document-local ownership, complete-set validation, permanent scope retirement
and collision exclusion. A native component-only probe read 8 faces twice with
fresh COM wrappers, reused the same short IDs and verified all 8 IDs against their
exact native faces. After closing that registry, another fresh read-only copy's
registry issued 8 disjoint IDs from the shared issued set. The first set remained
unusable. This did not itself test DocumentRegistry wiring.

| Component evidence | SHA-256 |
| --- | --- |
| `registry-native.json` | `4f7e7f81aa3a99f0329ec897de7bf57509b8e54223eae243b0f5f7db475f22b8` |
| `native-call-trace.log` | `2ab3f112886580cb7c5d48656d689264127b89a8649f57ff17fcf13adaf3bc0e` |
| registry source | `7eea5e13e93e6a15684fe3f9194f96b699c6d4bab2426aac1f12ba6c6fca010f` |

Local component evidence: `/private/tmp/swcli-a8-registry-native.SD4a4a`.
DocumentRegistry subsequently acquired a per-entry EntityRegistry and closes it
on forget/external-close synchronization. Five additional portable lifecycle
cases pass (**19** registry cases total).

The first integrated native probe preserved its first failure: the extra
assertion that closing background A must keep B foreground failed. Reads, ID
reuse and fresh-wrapper entry reuse had passed, but old-ID rejection/reopen
assertions had not yet run. That result was not claimed as a passing lifecycle
probe, changed, or retried.

An independent causal sampling probe recorded the foreground before CloseDoc,
after CloseDoc but before sync, and after sync. **CloseDoc itself** moved the
foreground from B to an original user document; sync did not cause the switch.
Separate lifecycle assertions then passed: sync rejected all 8 old entity IDs;
reopening the same path created a fresh document entry/registry and 8 disjoint
IDs. B's configuration/stamp/modified state was unchanged. Closing a background
document must not be presumed to preserve foreground in future public lifecycle
contracts. No foreground-restoration behavior was added in this slice.

| Integrated lifecycle evidence | SHA-256 |
| --- | --- |
| first failed `document-entities-native.json` | `450d512e91fe7177621c072aaed3f47d95a428bda56d45e7ef8df24252b06432` |
| first failed native trace | `ca580db434eed20e08c3c0e3433f5b8a1d7540e97efa2a0a0ed199e8a499b6dd` |
| independent `close-causal-native.json` | `120b5dc37b3d0981ca6f75687f3eb731905c5dbfc1376834d50b4e9030b419f0` |
| independent causal trace | `30c15bc2ee971d8a257aa3b4f826e01ed3e9d53f2980af54caecd5f1a300cfc6` |
| DocumentRegistry source | `16b52bae229986a15a6f9e8581987f6eaea3c277d5ae40500447d2904ef207a4` |

Local integrated evidence: `/private/tmp/swcli-a8-doc-entities-native.xL1wVo` and
`/private/tmp/swcli-a8-close-causal-native.HGI7Yo`. All probes restored the user's
original document set, states and foreground on SW PID 1096, with empty cleanup
errors. No user model was saved or host process replaced. Actual native scope
changes/topology edits, public entity commands and Wine gates remain unproved.

## Analytic geometry container sampling

On an independent fresh read-only fixture, the 7 planes returned tuple
PlaneParams (6 values) and Normal (3 values), and the cylinder returned tuple
CylinderParams (7 values). FaceInSurfaceSense returned bool: true planes had
opposite surface/face normals, the one false plane had matching normals.
The cylinder's native array was `[0.01, 0.02, 0.005, 0, 0, -1,
0.003000000000000001]` (lengths in meters). Configuration, stamp 146, modified
false, edit and foreground identities remained unchanged; original user state
was restored on PID 1096 and cleanup was empty.

| Sampling evidence | SHA-256 |
| --- | --- |
| `face-geometry-native.json` | `d022d851ad7b9f602fbb6517085832edc723b0319603ef77db6c1ec0ddc24e23` |
| native trace | `1cf14b211ee5ba70566a192a27237b65f30eebaa3eb01d3c63ec930f27c91806` |

Local sampling evidence: `/private/tmp/swcli-a8-face-geometry-native.wC9ezT`.
The production parser added after sampling has 10 targeted portable cases, and
the observer has 13 (including complete refusal after malformed geometry), plus
13 reference cases: **36 related cases pass**. A read-only background portable
check additionally exercised 128 malformed-array slot assertions and 3 native
failure assertions; no partial faces or bindings escaped. These ad hoc assertions
are separate from the committed unittest case count.

The fixed production path at `a72bc56` then completed two full background A
reads and registry registrations with B foreground. The 8 IDs and finite JSON
geometry were identical across reads. Each plane's converted point, surface
normal and independent face outward normal matched direct native readback and
sense. The cylinder reported axis point `[10,20,5]` mm, direction `[0,0,-1]` and
radius `3.000000000000001` mm. No private references/native COM objects appeared
in the payload. Configuration, stamp 146, modified false, edit and B foreground
identity/state stayed unchanged; the original user document set/state/foreground
was restored on the same PID 1096 with empty cleanup errors. Source hashes were
unchanged before/after. Two observer+registration trace measurements were about
2.03/3.76 seconds; these are host measurements, not an API latency promise.

| Production geometry evidence | SHA-256 |
| --- | --- |
| `geometry-observer-native.json` | `06d97bcb2e89b43a62b3d4fdda04cd714db7bc3599a370d1d8772f4c9ceb4eee` |
| native trace | `a3f488ae083f6980438735a279f5bada47138ad64aaa82a8671d4cc4a6b6d1d6` |
| probe source | `dc10ce3410bfea980596876c03fbb92b908d9ba163d1eaa21d1bd1b1e0bc5dc0` |
| geometry source | `c94e5812e8679684ca8f747270c804f3ca02d38ef9163591e27832aa4134ad0d` |
| observer source | `79f8e130f9de92c69a20fdd3a208b6822c6ce4ed03eabd693c2001610f114498` |

Local production evidence: `/private/tmp/swcli-a8-geometry-observer-native.G7NhHM`.
These prove the **internal** Windows observer/registry, not public CLI, Wine,
arbitrary analytic surfaces, trimmed boundaries or actual topology-edit survival.

## Typed handlers and real stamp retirement

At fixed development commit `020be4c`, a separate probe exercised the real
`execute_operation` handlers and DocumentRegistry on SW PID 1096. New writable
copy A was leased by a writer (600 seconds); read-only B stayed foreground/current
for the reader. Two reader lists without a write token reused all 8 IDs;
plane/cylinder inspections matched. Wrong CAS, unknown and cross-document IDs
returned expected refusals without changing state/current/foreground. Each
successful result passed its actual operation result Schema and finite JSON.

One rebuild of **disposable A** advanced its native stamp 146 → 163. The old ID
failed with `EntityReferenceStale`; explicit listing issued 8 disjoint IDs. This
proves conservative stamp invalidation, not topology change/survival. Typed
close/discard rejected all retained IDs; same-path reopen rejected the prior ID
with `EntityNotFound` and issued IDs disjoint from both sets. All 15 events used
the same SW instance (about 32.9 seconds), original user state/foreground was
restored, cleanup was empty and eight source hashes were unchanged before/after.

| Typed handler evidence | SHA-256 |
| --- | --- |
| `entity-handler-native.json` | `255b9d239fe662c779c0ece2836312a78efc71dba5c96b15e12946f722a97eea` |
| native trace | `37554673cb017fb55afc8ea74bef520de872d12ed08ec2d4024a08064ddf555b` |
| probe source | `c46a41454ee807221ceb64d5474c3ca0931f9a46eae02c7150b26de7bdac11bd` |

Local evidence: `/private/tmp/swcli-a8-entity-handler-native.oA8tOM`.
No HTTP daemon/installed CLI was exercised here. The shared modeling script now
reuses its existing depth fixture for installed-CLI entity checks: geometry,
repeat, leased background reads, CAS/cross-document refusal, edit-stale and
read-only reopen. Fifteen script tests including wrong-radius/plane/outward-normal
refusal pass; installed Windows and Wine gates remain pending.

## Portable integration and isolated packaging

At runtime commit `fa935ab6dd9ff6a460d4f305de9e773b94653939`, all 1,087
portable tests completed in 24.851 seconds: passed, with 8 Windows PowerShell
prerequisite cases skipped on macOS. No socket/sandbox failures occurred.
All 50 runtime Python/schema files retained aggregate SHA-256
`16886f02875b33bdcd8c44744901e3fd8df33279377cfb356d32ff45cec97502`.

A copied-source wheel/sdist build passed metadata and sdist-boundary checks.
An isolated temporary installation passed installed command/schema/skill-resource
checks and entity CLI/catalog/handler agreement; every runtime resource matched
the copied source byte-for-byte. This proves packaging and portable wiring, not
actual COM execution through the installed CLI. The concurrently updated guides
were not part of that package snapshot, so a release package must be rebuilt.
Local receipt: `/private/tmp/swcli-a8-integration-package.72outI/verification-receipt.md`.

## Independent integration review

Two portable review reproductions were fixed in separate commits:

- `905e6e6`: the fixture gate previously checked each plane individually, so
  seven distinct IDs could all carry the same otherwise valid `-X` geometry.
  It now consumes the complete seven-plane direction/location set exactly once,
  rejects duplicate cut floors and small tilts, and accepts valid reordered
  faces. Sixteen modeling-gate tests pass. These are fixture assertions, not a
  new restriction on legitimate coplanar faces in general CAD models.
- `3575fca`: a failed list could observe a new configuration/stamp without
  retiring prior handles, allowing a subsequent return to the original scope
  to revive them. Verified before/after scope reads now retire IDs separately
  from complete geometry registration. No partial handles are issued; the
  first native error is retained. Same-scope failure keeps live exact handles.
  Forty-four entity operation/registry/result tests pass, including five new
  failure-boundary cases.

The earlier full-suite/package receipt remains evidence for its named runtime,
not for these later fixes. Current installed-host verification must name the
new runtime commit explicitly.

## First installed Windows CLI/HTTP probe and cleanup finding

A fixed `fa935ab` wheel (`5a2c00eaa31895976430b31f4b4fee2877adf95e9b1302c890dec57cb961fd39`)
was installed into an isolated Windows venv. Fifty runtime files matched it
byte-for-byte. The first probe's own 1-second connect-based idle-port precheck
timed out **before daemon/COM startup**; no business operation ran. Its JSON
`7645cc98ddbf9d2beda3bd2adb5c952e7f04e7c59f9278f69c848062ad61bf6e`
is retained at `/private/tmp/swcli-a8-installed-native.KHgz1I`.

An independent probe used bind to verify port availability. Twenty actual
CLI → HTTP → daemon commands passed entity repeat/inspect, leased background
reads, CAS/unknown/cross-document refusals, rebuild 146 → 163 retirement and
close/reopen. It used shared SW PID 1096 and disposable copies only. Normal
cleanup then found a real separate issue: `daemon stop` returned `ActiveDocument`
because the user's original document remained open. **Business checks passed;
normal cleanup did not**, so the overall run is not recorded as all green.

After exact listener/command-line/parent identity checks, independent fallback
cleanup ended only its own Python supervisor 1320 and worker 5884. SW PID 1096,
the original native document identity, foreground, modified flag and stamp 102
remained unchanged; the endpoint was released. Original failure evidence was
not overwritten. Local evidence: `/private/tmp/swcli-a8-installed-bind-native.X99L3x`.

| Installed probe evidence | SHA-256 |
| --- | --- |
| `installed-native.json` | `3b64fdb3f037e084681888c504134d9b7fef5c819eb3a88ab95302b716772b74` |
| `daemon.log` | `73e1386fbb27520b1bc681b40c3fe6ca1fe4ac7ba541b7560506f50b13ebb6b7` |
| `fallback-cleanup.json` | `ac650241b7b3975775fd3ce13aad9943e7de9f1f2d9086a018e2f58b4f9430e4` |

`0d02694` fixes shared shutdown to detach without checking or closing user
documents; owned shutdown still refuses open documents and exits only an empty
owned host. Seventy-nine daemon tests pass, including four ownership/document
combinations. Installed native regression for that fix remains pending.

## Shared-stop installed regression

An independent installed regression used runtime
`0d02694dd0ed397d23eef3a0ed79cbb5aa86ba64`, wheel SHA-256
`081030157822e58ed573726397921cf90a0d2fd384c99264a52544ae117c2635`.
Fifty installed Python/schema files matched the wheel. A disposable read-only
copy passed entity list/cylinder inspect and was closed. With the original user
document still open and foreground, actual CLI `daemon stop` returned success
and exit code 0. No SW process was killed or user document modified.

The probe's postcheck initially misinterpreted a PowerShell empty-property
projection `[null]` as a live process list. Its first failure JSON remains
unchanged. A separate read-only count check established zero listeners and zero
remaining supervisor/worker/launcher processes; SW 1096, original document
identity/foreground, modified=false and stamp 102 remained unchanged. This
closes the runtime stop finding, not the old probe artifact's failed status.
Local evidence: `/private/tmp/swcli-a8-shared-stop-native.wCvcRy`.

| Shared-stop regression evidence | SHA-256 |
| --- | --- |
| first `shared-stop-native.json` | `a3bddbcd16065381f60c526fbfde400991a07edca9858fdfe892445578c341eb` |
| independent `exit-readback.json` | `4c5780e0c9dda25fcc1e74991511719974b0874a7db22b4193c3db51ef95e51b` |
| `daemon.log` | `5c8a8a4e441d8462bb5907f3344c588af39f875733d6b075716f09eff3d94b62` |

## First Wine gate: CLI/result assertion mismatch

Fixed runtime `7d2dc1e` on the verified a7 DockerSW base
`sha256:b74f9de64fe35de06586299a9efecb7e204091bddf5a18f0cb0c96b5db9b8da9`
passed native-model/reverse-cut and returned a successful first entity list.
The shared script then incorrectly validated CLI `request_id` metadata against
the daemon business-result schema and stopped. Cleanup succeeded. This is a
gate defect, not a completed Wine entity gate or evidence of native failure.
First modeling JSON SHA-256:
`4193f5751254f4c9b0aa256f6a9f7a3e006ec4d97f7618b7680f547ab16ba277`;
daemon log: `498b061b7a09659c8084fd20200684c49bcd83f13eb4aa60658a51875ea09f24`.
Local first evidence: `/private/tmp/swcli-a8-wine-candidate.3IB1z4`.

`9b82b4e` preserves complete CLI evidence and removes only known
`request_id`/`replayed` fields from its business assertion view. Fake CLI results
now use the actual presentation helper; 17 associated gate tests pass, including
unknown-field rejection and replay metadata preservation. DockerSW/Wine follow-up
is paused at the user's request while a separate agent handles that host project;
its repository pin and images are not updated here.
