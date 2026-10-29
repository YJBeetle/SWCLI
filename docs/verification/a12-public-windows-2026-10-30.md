# a12 guarded public-operation Windows development proof — 2026-10-30

Candidate: `0.1.0a12.dev0` on `codex/a12-through-all`; public implementation
commit `ee07885`. This source-based VM
proof uses the real CLI parser/mapping, request validation, daemon operation
handler/document registry, lease/CAS checks, temporary activation, native adapter,
exact feature binding and response validation. It does not start a daemon or
exercise an installed client/network transport, and is not full Windows/Wine or
MacSW acceptance. No a12 release is claimed.

## Twelve public creation cases

One existing Windows SOLIDWORKS 2025 SP5 host (PID 10672, visible) completed
circle/rectangle × front/top/right × normal/reverse. Each own temporary fixture
received a typed `--through-all` request without depth; the exact returned
feature was resolved from the document registry, not a name or last-feature
lookup. All 12 response schemas passed, end condition was 1, all-body scope was
false, and depth/verified depth/tolerance were null. The native unused 1 mm
argument was never reported as travel.

For every case, conflicting depth, another session's lease, a stale update stamp
and the same sketch handle in another document were refused before mutation or
foreground changes (48 refusals). Successful background creation restored the
existing foreground and preserved the session's current document.

The original analytic volume/area checks passed at 10 mm, after the **test-only
native fixture boss edit** to 25 mm, and after native save/close/read-only reopen
with fresh unique-cut discovery. The existing user document was never saved,
closed, edited, or used as a fixture. Exact retained document identity/catalog,
visibility, saved flag false and update stamp 102 matched before and after;
cleanup errors were empty. There was no host exit/restart or failed CAD retry.

Evidence: `/private/tmp/swcli-a12-vm-public-20261030/{report.json,trace.jsonl,native-files/}`.
Report SHA256: `f82ac91ac30f63891c4875e08482d0184e3ae155919140ebf93d96a27bd2a4c5`.

| Profile | Plane | Reverse | Saved native SHA256 |
|---|---|---|---|
| circle | front | false | `293d62994c40a00140d18116d03d81947eb48c305563e75de34ed2bf4771185b` |
| circle | front | true | `ede8450e8c9ca17fe0721b43eb5d1797aa41c486eaf39f8128ed2c616402a12c` |
| circle | top | false | `5b52e72376f8611856b788d4c18d89fa5c182a4a0f8ac1415e0e44ea124690f7` |
| circle | top | true | `60a60b206006aee4887b150526b95b0013e4d1fa280235933a74b984ce767b22` |
| circle | right | false | `abc4502ea95d608860e2859a9fa485993ef7e3fb7940ddbc62ecc158fd715e66` |
| circle | right | true | `0c56276eadc072fd09f0fe89955e4838848aa236fca6aa9c5d6dbdb9af1a1609` |
| rectangle | front | false | `febed3ba68319cea1000242fae562939d7671d0f5b6937fb1730c8637f288131` |
| rectangle | front | true | `79cb4863d54aadc9028660d2161807f42e24e75ca6825147ae33d6c5b4ca638e` |
| rectangle | top | false | `0c61f6677cbe528d6b3dcc416a8a48abcd478a773c30a6a4ad652ffa97ead520` |
| rectangle | top | true | `186d9f80e5e8ef35c85d59b915a4614bb66baf9e237fe0c70819d3204a393106` |
| rectangle | right | false | `49838dd84049a58ada0929a87de35183984de9be3773dfdff60b47d3ae440520` |
| rectangle | right | true | `4d74cf572dd10acf9ed4c55d9056c34b6d14040c35a7c82a85ff3e8e7c6ef895` |

## Separate public growth/refusal control

A private writable copy of the generated front/normal circle fixture was opened;
its source hash was preserved. Public `feature.list` supplied exact boss/cut
handles. `feature.set-depth` on the through-all cut was refused with
`UnsupportedDepthDefinition`. The same public writer successfully grew the
blind boss from 25 to 30 mm. The cut remained native end 1 and read-only
`feature.inspect` reported unchanged state. Analytic volume was
`35151.76998353076 mm³` and surface area `7108.938009881545 mm²`, both matching
the 40×30×30 mm box minus the radius-3 through-hole. The source hash and existing
user document snapshot were unchanged; cleanup errors were empty.

Evidence: `/private/tmp/swcli-a12-vm-public-growth-20261030/{report.json,trace.jsonl}`.
Report SHA256: `658f8b0ac4b3e372c616d54fb83b5763c85010692c8b0962c9248f6dd1432288`.
This is one public growth control, not a claim that all twelve growth edits used
the public setter. The installed full gate uses the public setter in all twelve.

## Portable verification and pending acceptance

The public implementation and shared gate passed 1503 tests (21 platform skips).
The full plan keeps its 19 sets and original blind/geometry/timeout checks;
`reverse-cut` additionally requires the twelve public through-all cases including
public boss growth, native roundtrip, fresh handles, clean diagnostics and hashes.
The twelve-case native calibration remains a separate diagnostic, not a substitute
for that installed full receipt. MacSW remains excluded by the owner's instruction.
Development wheel/sdist build, Twine validation, source-package completeness and
a fresh isolated no-COM wheel installation all passed. The first no-isolation
build attempt lacked local setuptools; the standard isolated backend build
succeeded without a product change. These are development outputs, not released
a11 replacements. Installed native CI/Wine receipts must still be recorded
independently before release approval.
