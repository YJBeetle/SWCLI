# a8 formal-version runtime gates — 2026-10-11

This record separates the formal `0.1.0a8` Windows/Wine host gates from the
earlier development receipts and public distribution. No MacSW repo, CI, App,
container or local Windows VM was operated for these runs.

## Installed hosted Windows passed

[SWCLI CI 38063625340](https://github.com/YJBeetle/SWCLI/actions/runs/38063625340)
passed at **`15e09626a500d34e6212c70719584fede7291efe`**. Its same-workflow wheel
was installed normally on a cold-installed Windows 2025 hosted runner. Python
3.9/3.14 tests, wheel/sdist/resource checks, actual media mounts and official
core/Toolbox installation passed. Runtime health reports server `0.1.0a8` and
SOLIDWORKS 2025 revision `33.5.0`.

Independently downloaded terminal records confirm the unchanged host sequences:

| Mode | SW PID | Modeling events | Driving events | Toolbox calls |
| --- | --- | --- | --- | --- |
| Visible | 1384 | 229 | 598 | 8 |
| Hidden | 4508 | 229 | 598 | 8 |

Modeling/driving report `completed` and success; Toolbox reports `passed`,
completed and native-test passed. Cleanup/evidence errors are empty. First/final
modeling/driving host and Toolbox health retain the mode-specific PID; the two
modes intentionally use separate hosts. Complete 8-face/14-edge observations,
mixed/repeated exact IDs, wrong-kind/CAS/cross-document refusals, unchanged
leased background reads, real-write retirement and close/reopen fresh IDs pass.

Both Toolbox inventories have 19 enabled standards, 1844 models and a
652350-byte index. The representative ball bearing's source hash remains
`ff3e407fe2a2b0411f927f3b5103789e8436e8594ccc7bf48964b438aab4897e`.
Updater exit code is unobserved (`null`); this is not specification selection,
generated-configuration or assembly-insertion proof.

| Terminal record | SHA-256 |
| --- | --- |
| Windows visible modeling | `92927862ca1d0390a7523fb3c984db835418bbb4e76c9c53854096d23fa6921d` |
| Windows visible driving | `8874f62aa11bf409b2162ec7f42240da8114506e10b2e7b6c90f5a33a6ee0f95` |
| Windows visible Toolbox | `88cdb4a6193fd823d82c2c88e269057694f9af4136a160bfb6ffe764325bd14a` |
| Windows hidden modeling | `d2817c5537ee9202d26c956fc878c8999d24fe3f34e8ff10e7a5855f107c4db3` |
| Windows hidden driving | `cc68326a08c6dfddbf301d2f017cb5d634520f3dcd9e49d714e7ec2766b27beb` |
| Windows hidden Toolbox | `13c190327bc2f5b86023001e1827a61b1cb209728223a717128c423bbd3a5cde` |

Native artifact `swcli-windows-hosted-38063625340-1`, ID `11674447816`, digest
`sha256:f42e4219e1df7dde7354eda2c8a5a22312257d8fbc4a04d8070c06397ad7d6e0`.
Local download: `/private/tmp/swcli-a8-formal-evidence.MXOWCp`.

| Same-workflow distribution | SHA-256 |
| --- | --- |
| `swcli-0.1.0a8-py3-none-any.whl` | `3da7596967ddb8a0ae4ae2a5d0ca1d35ed056cf534a83812e6e9dc3ad0738a9f` |
| `swcli-0.1.0a8.tar.gz` | `95dfcf7ee3c1b873aaee7333a57411a2c35eb079125b68fefef453908bb6562a` |

## Linux/Wine delivery: first failures preserved

[DockerSW 38048268839](https://github.com/YJBeetle/DockerSW/actions/runs/38048268839)
completed real exports, modeling, driving, Toolbox and localized smoke, but
failed **Upload export smoke-test artifacts**: the runner could not read the
root-container-owned `toolbox/toolbox.json` (`EACCES`, atomic-file mode 0600).
This was an evidence-upload failure, not a CAD failure or a successful workflow.
Parent fix `3a6e1fa` grants read/traverse permissions only within the two public
evidence roots, without following symlinks or exposing private installer inputs.

The first formal candidate
[DockerSW 38063720326](https://github.com/YJBeetle/DockerSW/actions/runs/38063720326)
failed **Run Logic Tests** before image/runtime jobs. A legitimate
`duration_ms: 0.045835999998189436` collided with a test's raw-string check for
edge coordinate `0.045`. Child fix `244e9e5` checks the allowed event fields and
non-timing metadata, with an injected collision time. It changes only a test,
not the native logging or CAD code, and retains the no-argument/result guarantee.

DockerSW candidate **`d924d9bfeafd966611e1868754a5c29bdbd8a68d`** pins
**`244e9e51ac7d3f3da8cacdbba419440dd0e6b22f`** and includes both fixes.
[CI 38065149214](https://github.com/YJBeetle/DockerSW/actions/runs/38065149214)
is the formal delivery gate; its terminal runtime/artifact/promotion receipt is
still pending. The candidate's Python, Schema and packaged skill files match
the successful formal Windows wheel byte for byte; source tests/docs and
archive hashes differ. That comparison does not replace a Wine host gate.

## Distribution boundary

Local normal wheel installation, isolated CLI/Schema/skill verification,
`twine check`, source-payload checks and 69 affected portable tests passed.
These are not published assets. The latest public release remains a7 until
formal delivery and publication receipts are completed. Exact face/edge IDs
remain conservative worker/document-local references, not trimmed topology or
arbitrary edit-survival guarantees.
