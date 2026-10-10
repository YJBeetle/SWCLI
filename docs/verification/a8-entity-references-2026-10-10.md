# a8 internal entity-reference binding — 2026-10-10

This is **internal Windows feasibility/adapter proof**, not a public entity
operation, Wine result or promise of topology survival after editing. a7 remains
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
post-edit topology checks. Those remain the next internal observation boundary
before public `entity.list/inspect` wiring and independent host gates.
