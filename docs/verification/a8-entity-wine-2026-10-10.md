# a8 face/edge Linux/Wine verification — 2026-10-10

The complete shared modeling, driving-dimension and Toolbox sequence passed its
first business run on the user's trusted `workspaceroot`. This is independent
Linux/Wine evidence, not a newly built DockerSW image or a published a8 release.
MacSW code, CI, App and containers were not operated.

## Exact payload and host

Runtime and public CI scripts come from SWCLI
`1cee28dab92c0579e2346e8356ec2fa55b248b9c`, reporting `0.1.0a8.dev0`.
The wheel was built locally and unpacked as the isolated runtime import payload
at `/opt/ci-swcli` in a new disposable container. The existing host wrapper
routes the Linux client and Wine Windows daemon/worker to that same payload;
platform dependencies come from the formal image. This is **not** a normal
Windows pip-install check or an editable source overlay.

| Input | SHA-256 |
| --- | --- |
| `swcli-0.1.0a8.dev0-py3-none-any.whl` | `8c867cab623fc9f621dc3a40adb8a402ef0404fdb1d74c3f83adfc7a80ff80ff` |
| exact `scripts/ci` source archive | `e4f6b754d906dba2e92261e13efbdefaebb582dfa8265b095c65483372d10a28` |

The existing base is `ghcr.io/yjbeetle/sw-executable:sha-d1f1f9d-cli`, image ID
`397343988c6e6d6bf540f45b33cf505078e090e7c8ad7c7618ae2e6fcd04f14f`.
Startup reports Wine 11.16 / Wine-Mono 11.3.0. SOLIDWORKS 2025 `33.5.0` remained
hidden, daemon-owned PID **612** from modeling through driving and Toolbox.
Neither a business operation retry nor an intervening host restart was used.

## Shared gates

The unmodified `verify-modeling.py` completed **229 events**, including installed
part/assembly sample arguments, the existing sketch/extrusion/cut continuation
and guarded depth-edit checks. Its a8 fixture verifies:

- complete 8-face set: 7 planes and 1 cylinder;
- complete 14-edge set: 12 lines and 2 circles, with raw curve parameters and
  independent analytic-geometry assertions;
- exact repeated-ID reuse and mixed face/edge ID preservation;
- wrong-kind, stale-stamp and cross-document refusals;
- leased background reads without state/current/foreground mutation;
- conservative retirement after actual depth writes;
- native save/read-only reopen with fresh IDs and verified depth/geometry.

The record contains 39 public entity commands: 23 successful observations and
16 expected refusals, all checked by the gate rather than treated as retries.

`verify-driving-dimensions.py --after-modeling .../modeling.json` then completed
**598 events** on that same PID, covering front/top/right cases. Both terminal
records have `state: completed`, `success: true` and empty cleanup errors.

The subsequent required Toolbox gate completed **8 public CLI calls**, with
`outcome: passed`, `completed: true`, `native_test: passed`, and empty cleanup and
evidence errors. Registry discovery found `C:\SWData`, 19 enabled standards,
1844 models and a 652345-byte official index. The representative instrument ball
bearing was opened read-only, diagnosed, measured and closed without changing
its source SHA-256:
`ff3e407fe2a2b0411f927f3b5103789e8436e8594ccc7bf48964b438aab4897e`.
First/final Toolbox health also reports PID 612.

| Terminal record | SHA-256 |
| --- | --- |
| `modeling/modeling.json` | `46446e06962299001eb26cffb5e7c29f51fd21fe52d59df4aea4e537f386addf` |
| `driving/driving-dimensions.json` | `556a8eadf79317352d2e4385997bc12b3542e20a071da3a0c35bfb23483b239e` |
| `toolbox/toolbox.json` | `f5c4c028b804df0367b507b5bdd04654846f582fe9c7cafd1aeb26a9019f9624` |

## Cleanup and remaining boundary

Daemon stop returned success and the container exited **0**. Evidence and
generated artifacts were downloaded before removing only
`swcli-a8-1cee28d-proof`; the pre-existing container was left untouched. Local
evidence is `/private/tmp/swcli-a8-checkpoint.yjFMh3/wine-evidence`; the host copy
remains at `/tmp/swcli-a8-checkpoint.XTHjbpCL/evidence`.

No source-library repair or installer execution was performed. Toolbox updater
exit code remains unknown (`null`); inventory is not proof of every standard
part, specification selection or assembly insertion. This sequence does not
claim the six official export artifacts, a new image build/promotion, native
Mac proof, trimmed-edge/adjacency semantics or topology-edit survival.

The narrow installed Windows copy proof is separate. Full hosted Windows
visible/hidden a8 proof is still pending in
[SWCLI CI 38056417517](https://github.com/YJBeetle/SWCLI/actions/runs/38056417517).
Its cold installer includes the independently diagnosed Toolbox component-chain
correction; this Wine run on an already deployed library does not prove that
Windows installation fix.
