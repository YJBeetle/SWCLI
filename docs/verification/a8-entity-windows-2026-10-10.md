# a8 installed hosted Windows verification — 2026-10-10

[CI 38060854902](https://github.com/YJBeetle/SWCLI/actions/runs/38060854902)
passed at runtime/source `55bf0a067a218f5094b5dfe1389e13bcd333640b`, reporting
`0.1.0a8.dev0`. This is the full cold-installed development gate, not a published
a8 asset or formal-version delivery receipt. No local Windows VM or MacSW host
was operated for this run.

## Installation and package provenance

The Windows 2025 hosted runner installed the official native prerequisites/core
and explicit Toolbox feature chain from streamed media, then installed exactly
one wheel from the **same workflow's** package artifact. It did not restore a
SOLIDWORKS installation snapshot or use editable SWCLI. The corrected pinned
WinFsp installation, actual Google Drive/ISO mounts and cold installation all
passed; the earlier WinFsp feed failure was not retried as a CAD operation.

Windows Python 3.9 and 3.14 unit jobs passed. The 3.14 log records **1183 tests**,
with two platform skips. Package/resource/Schema checks passed independently of
native modeling.

| Artifact | SHA-256 |
| --- | --- |
| `swcli-0.1.0a8.dev0-py3-none-any.whl` | `1773a7296bb6abb05e3c51875e63088ea2caa09e5a67bb912cc4af4e08d42e6a` |
| `swcli-0.1.0a8.dev0.tar.gz` | `8809dececf4612947f3d5375f461ebaa5ef34f1a9e52fec6e474d15f2f82b876` |

The wheel's extracted `swcli/` Python, Schema and skill resources match the
earlier [Wine wheel payload](a8-entity-wine-2026-10-10.md) byte for byte. Archive
hashes differ; file equality establishes runtime-payload consistency, not
equivalent host installation or a new DockerSW image.

## Unchanged host sequences

Both modes passed modeling, driving dimensions and required Toolbox in order,
without a business retry or a host replacement inside either sequence:

| Mode | SW PID | Modeling events | Driving events | Toolbox calls |
| --- | --- | --- | --- | --- |
| Visible | 7180 | 229 | 598 | 8 |
| Hidden | 1744 | 229 | 598 | 8 |

Both hosts are daemon-owned SOLIDWORKS 2025, revision `33.5.0`. First/final
modeling and driving host records and first/final Toolbox health agree on the
mode's PID. Modeling/driving terminal state is `completed`, success is true;
Toolbox outcome/native test are `passed`, completed is true. All cleanup and
Toolbox evidence-error lists are empty. Visible and hidden are intentionally
separate fresh hosts, not one cross-mode PID.

Both a8 entity records verify the complete 8-face/14-edge depth fixture:
7 planes, 1 cylinder, 12 lines and 2 circles. Exact repeated and mixed-kind IDs,
wrong-kind and stale-stamp refusal, cross-document rejection, leased unchanged
background reads, actual depth-write scope retirement and native close/read-only
reopen with fresh IDs passed. No edge length/closure/adjacency or general
topology-edit survival is inferred.

## Toolbox cold-install result

Both modes discover `C:\SWData`, **19 enabled standards**, **1844 models** and a
**652350-byte** official index. The representative instrument ball bearing
passes read-only open, diagnose, native body measurement and close on the same
host. Its before/after source SHA-256 agrees:
`ff3e407fe2a2b0411f927f3b5103789e8436e8594ccc7bf48964b438aab4897e`.

This closes the originally missing Windows component-chain inventory/native
part gate. The shared record does not independently observe the updater's exit
code (`null`), test every standard part, generate configurations or insert a
component into an assembly. Inventory/native verification is separate from the
installer's reported success.

## Evidence and remaining release gate

Native artifact ID `11673049506`, name
`swcli-windows-hosted-38060854902-1`, archive digest
`sha256:012e0a265b43aaa25b47b712ecb3665e639a5c03d5b720cc9eb1d2d70641b431`.
The downloaded files are under
`/private/tmp/swcli-a8-ci-38060854902.G9V5j2/native-evidence/swcli-native-smoke`.

| Terminal JSON | SHA-256 |
| --- | --- |
| `modeling/modeling.json` | `237d117693ee8f6ff30e09b5914a973055c358f5c7bb64c4c983cebabfe867e8` |
| `driving-dimensions/driving-dimensions.json` | `8b0279a1bdf79c9f91af60cb61a7cd661cc25153ecf7dc03b0968b6773b66a32` |
| `toolbox/toolbox.json` | `aeadd2768183a553104f39fea8a9a1cd83d9d1956f61bbac892b04665d5bab72` |
| `hidden/modeling/modeling.json` | `04ecbda58fcd366cf8c9dad72c993f608b318a4b6ae129915006f18734aca220` |
| `hidden/driving-dimensions/driving-dimensions.json` | `a99717f701a99f146c70fa3c322cc2d0733499b74b637cc3b6571e061e559470` |
| `hidden/toolbox/toolbox.json` | `6314fd340534e970dd27bc512a1e1750a8c84e844ad4e1f592792eae5a5e34ff` |

Formal-version Windows and DockerSW image/six-export/promotion proof remain
separate release gates. Follow the [a8 release notes](../releases/v0.1.0a8.md)
for publication state; a green development run is not a release announcement.
