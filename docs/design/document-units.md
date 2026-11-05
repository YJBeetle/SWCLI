# Document length display units

A17 begins document options with a bounded document length display profile.
The intended operations are read-only `document.units` and lease/CAS-protected
`document.units-set`. Three independent local Windows native calibration
groups passed for parts and assemblies. Installed public CLI fixture cases completed locally; the outer teardown
record and independent process-exit followup are described below. Complete
Windows CI acceptance remains pending.

## Native API and scope

`IModelDoc2.GetUnits` returns five short values in the order LengthUnit,
FractionBase, FractionValue, SignificantDigits and RoundToFraction.
`IModelDoc2.SetUnits` sets the corresponding document length unit and formatting
fields and returns void. Successful completion therefore requires a fresh,
complete five-field readback.

- [GetUnits](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~GetUnits.html)
- [SetUnits parameters](https://help.solidworks.com/2022/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~SetUnits.html)
- [Official 2025 COM example](https://help.solidworks.com/2025/english/api/sldworksapi/Get_and_Set_Units_Example_CPlusPlus_COM.htm)
- [Document property unit settings](https://help.solidworks.com/2024/english/api/swconst/DP_Units.htm)

The initial candidate targets millimeter/inch length display and decimal
places 0 through 8 in the calibrated decimal profile. Default part and
assembly settings read `[0,1,8,2,0]`; the unused fraction denominator 8 is
preserved. Fractional and unknown formatting profiles remain read-only. The protocol's
existing geometry lengths continue to use millimeters.

Whole unit systems (MMGS/MKS/IPS), mass and angle units, fractional formatting,
annotation fonts and other drawing options require separate increments.
Application-level `ISldWorks.SetUserPreference*Value` changes system defaults
and is outside this document operation.

## Required behavior

Reads must preserve the selected document's configuration, modified flag,
update stamp, edit state and foreground/current identities. Unknown native
codes must remain observable without inventing a mapping.

Writes require the current document lease and update stamp where supplied.
Reject unsupported profiles and parameters before calling the setter. A
same-value request returns without a setter. A changed request performs one
native write, reads all fields back and records whether mutation was attempted
or may have occurred. Native failures do not cause retries or rollback.

The local calibration must own a fresh hidden host and only newly created
documents, preserve any preexisting user instance, compare physical geometry,
and verify saved-copy hashes and read-only reopened settings. Part and assembly
samples, precision boundaries, background selection and cleanup are required
before public write acceptance. Final installed CLI acceptance runs in CI.

## Local Windows calibration evidence

All groups use one fresh hidden owned host, native timeout 600 seconds and group
timeout 1800 seconds, with empty cleanup errors and confirmed process exit.
They are diagnostic groups with `full_acceptance_eligible=false`; public
daemon/CLI coverage is recorded separately.

| Group | Native scope | Report SHA-256 |
| --- | --- | --- |
| b16d | mm/inch, precision 2/4, same-value no setter, native save/reopen | `58b38caf8ff16b4550c984b02b3e89e16370e3e60e555552436bd3cf27dc0fdd` |
| e30f | precision 0/8 and extension precision cross-read, persisted 8 | `be93108cb0a519154048ea3331ee85f703bb5aa509da3bb43103a4d2a68f0403` |
| f59c | exact adapter snapshot, precision/unit-only, old-value conflicts, dirty/no-op and read-only refusal | `0ff358f0061ce32540ceb35a7e7dcc7ba03dee04ff053c8504c029a7d2acdec0` |

The f59c adapter source SHA-256 is
`e131dce191b400f3e004851c914637c439a6f8c75172fd5bec969db64379c6c8`.
Across six part/assembly samples, native files, geometry and settings survived
save/read-only reopen with clean teardown. The part box retained 12000 mm3
volume and 3800 mm2 area.

`SetUnits` does not advance the observed document update stamp or set its dirty
flag. The adapter marks the changed document for saving with `SetSaveFlag`.
Callers can supply `expected_length_unit` and `expected_decimal_places`
(`--if-length-unit`, `--if-decimal-places`) to reject changed display values.
Document lease and update-stamp checks continue to apply to their own context.
No global preference setter was called. Application-level observations compared
only default template paths, not an exhaustive system-preference snapshot.

A17 introduces the first document-option slice. A18 is planned to continue
annotation arrows, bent leaders, zero display and separately calibrated font
and drafting-standard operations. The complete document-properties page remains
a sequence of explicitly validated fields.

## Installed public CLI development sample

The local package at source commit
`b48c5f2e27e0317880b44e86ae9e4fde640b712e` included skills update
`353a720975d50d4df16d1da0e3a3f167de9e16d8` through a real merge.
The packaged skill, usage guide and official API navigation matched source
bytes. A fresh isolated Windows environment installed the resulting wheel
normally and passed installed resource and dependency checks.

The two part/assembly public CLI cases completed successfully on owned hidden
host 4440. Native request-correlated traces independently show six SetUnits
calls, two SetSaveFlag calls, and no native setters for no-op or refused writes.
The cases verified six old-value refusals, two lease refusals, two stamp
refusals, two read-only refusals, precision 0/4/8, saved-copy hashes, unchanged
source bytes and fresh read-only reopened handles/settings. Geometry was
covered by the earlier private calibration, not by these public cases.

The first local outer wrapper checked the SW process immediately after daemon
exit and recorded a teardown failure. Its original failure report is preserved.
The public fixture receipt succeeded, daemon exit code was zero, and an
independent followup confirmed no remaining SW process. No successful mutations
were repeated. Future local wrapper runs use the same bounded exit grace as
the existing CI adapters. This sample does not replace complete CI acceptance.

| Development evidence | SHA-256 |
| --- | --- |
| Local wheel | `8281f0a9cca25fea65b1cf1c14109666c4007d6ecc79def7d9f0fcae9b26c399` |
| Public fixture receipt | `9fad0857d0da7a7834da97938687a7c490e2437dcef3e2a73391396197ad9578` |
| Native daemon trace | `e6258425cefc823d42439eaac7d068623df69c031034836803b69bab057ae858` |
| Original outer failure record | `98cc917b2dd15fed3c2a5e8492fd991ff0c7d4c5e266f88c6ff4a62f1f10f1be` |

Portable coverage passed the 1570-test core suite (21 skips) and the six new
public-gate regression tests. Exact `0.1.0a17` is frozen for one final installed
Windows full run and original CI package verification. It has not been released.
