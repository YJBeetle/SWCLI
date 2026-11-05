# Document custom property reads

The a15 candidate adds `document.properties` through the existing operation
catalog, daemon and CLI. It targets an open document by its exact handle or
session selection.

```powershell
sw-cli document properties --document d-ab12cd --json
sw-cli document properties --document d-ab12cd --name "Drawing No" --json
```

The result has document scope and a list of properties. Each row preserves the
name, native type code, stored expression, evaluated value, native cache or
resolution result, resolution flag and linked flag. A missing named property
returns an empty list. An existing empty value returns a row with empty strings.
Listing requires the native count and unique name array to agree, within a
1000-property bound. Unreadable native outputs fail the operation.

The adapter uses `IModelDocExtension.CustomPropertyManager("")` and
`ICustomPropertyManager.Get6` with `UseCached=true`. This selects general
document metadata and permits cached evaluations. It compares the document
type, active configuration, modified flag, update stamp and foreground native
identity before and after the read. The daemon applies the existing session,
document-handle and expected-stamp checks. Background reads use the selected
native object directly.

The first native proof uses owned part and assembly fixtures with Chinese text,
empty text, numeric and boolean fields, plus a configuration-specific shadow of
a general property. It exercises public operation dispatch, name lookup,
missing-name lookup, background/session preservation, save and read-only
reopen, file hashes and host cleanup. The fixture seeding is private calibration
code. Drawing and broader saved-document fixtures require subsequent proof.
The calibration receipt is followed by the existing full CAD gate.

Installed CLI and Wine acceptance remain pending for this candidate.

## Native API sources

- [Document or configuration property manager](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.imodeldocextension~custompropertymanager.html)
- [Get6 value and cache behavior](https://help.solidworks.com/2018/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ICustomPropertyManager~Get6.html)
- [Native property read result codes](https://help.solidworks.com/2025/english/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swCustomInfoGetResult_e.html)

## Windows native proof

[Calibration 41982776387](https://github.com/YJBeetle/SWCLI/actions/runs/41982776387)
passed at `26a54509a517c405bf5f27f8479f067049b86337`. Its original artifact
`13397985026` ZIP SHA-256 is
`1ab1d12831596dd3c41af221dd74c8cfcf46b6f72b29661dd434adbb5ae276a2`.
Independent verification confirmed two native fixtures, fourteen property reads,
configuration shadow isolation, empty-versus-missing values, unchanged state,
read-only reopen, file hashes and owned host teardown.

The calibration report SHA-256 is
`28dbee8e25af512f9f2ca8789321bca6f689ad966bdd89b20e61eaf23462416c`,
and its trace SHA-256 is
`48f2a76e79eebb0e7f6f507b577d92cb0de155c3d231ef3713a0a8f5f75e2971`.
The subsequent existing Windows full gate passed all nineteen sets and twenty
steps with clean process boundaries, followed by complete evidence upload.
The visible gate passed as well.

The next Windows gate opens these separately prepared files through the
installed CLI and daemon. It checks exact values, types, missing lookups,
background reads under another session's lease, stale-stamp refusal, fresh
handles on reopen and unchanged fixture hashes. Its receipt is additional to
the existing full matrix. Wine persistence validation will use a DockerSW
candidate containing the `0020` MSXML namespace serialization fix.
