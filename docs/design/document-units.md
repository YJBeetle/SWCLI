# Document length display units

A17 begins document options with a bounded document length display profile.
The intended operations are read-only `document.units` and lease/CAS-protected
`document.units-set`. Three independent local Windows native calibration
groups passed for parts and assemblies. Public installed daemon/CLI acceptance
is still pending.

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
