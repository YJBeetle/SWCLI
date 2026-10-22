# Internal fillet calibration — macOS/Wine, 2026-10-23

This is a local native API feasibility receipt, **not** public CLI support or
Windows acceptance. No `feature.fillet` operation has been advertised.

## Environment and scope

- The already running MacSW build App and its existing main bottle were used;
  the separate App in `/Applications` was not used or updated.
- Wine 11.16, Mono 11.3.0, SOLIDWORKS revision `33.5.0`; the bundled backend
  matched its manifest at `1ccd449e6d04af75c56c1908603abddfdaacaded`.
- The existing launch coordinator and compatibility environment were retained
  (`WINE_MONO_AOT=none`). No runtime synchronization, registry change or Wine
  restart was performed. Windows VM startup was not retried.
- One owned, visible SW instance and one STA Python process executed the probe.
  The final successful run's SW PID was `1420` in the Wine/Windows namespace.
  Only a generated 40 × 30 × 10 mm native box was opened or modified.

## Proven narrow case

Official installed `swconst.tlb` values were read, not guessed:
`swFmFillet=1`, `swConstRadiusFillet=0`, `swFeatureFilletCircular=0`.
One known 10 mm straight exterior box edge was selected through its actual
native object with mark 1; its persistent reference matched the selected object.

`CreateDefinition → Initialize → CreateFeature` returned a native `Fillet`
feature in about 1.75 seconds. Radius was `0.002 m`, profile circular and tangent
propagation false. `GetDefinition/AccessSelections` exposed exactly one edge
with the original persistent-reference bytes and matching settings.
`ReleaseSelectionAccess` completed; rebuilding succeeded, full traversal of 21
features reported no issues or truncation, and one solid remained.

| Check | mm³ |
| --- | ---: |
| Original volume | 11999.999999999998 |
| Final volume | 11991.415926535898 |
| Actual volume removed | 8.584073464100584 |
| Expected `(1 - π/4) × 2² × 10` | 8.584073464102069 |

Final selection count was zero. The owned document was closed without saving
the fillet, and its owned SW instance exited normally. FlexNet, Wine, user models
and the MacSW repository/App/configuration were not modified.

## Evidence and first failures

Local evidence is in the independent temporary directory
`/private/tmp/swcli-fillet-native.aFE0zY` (not a permanent public artifact):

- `trace-v4.jsonl`, SHA-256
  `6613d39442f67d8df30d2e23e961bf849b523b67d8159fdb2890261c86475a17`.
- Final private `probe.py`, SHA-256
  `738ebc26550e4f34a20ec15bbc204ea0d436a9b4f6f18a69e79531ea44a18092`.
- Original generated `fixture.SLDPRT`, SHA-256
  `12d40638e4bb9c431cdecb4b39ef1ee068754d72620d89bce949815fffb248ac`.

Earlier traces were retained: v1 misread Python type-library metadata before
SW startup; v2 created the box but used a no-argument COM getter as a callable;
v3 created/verified the fillet but invoked a rebuild boolean as a function.
v4 corrected probe bindings using the existing `_com_value` convention without
changing the geometry, radius or assertions. No failed native fillet operation
was retried or hidden.

## Remaining proof

Run the explicit internal calibration on native Windows CI before exposing the
operation. This receipt does not prove general edge eligibility, concurrent
lease/CAS guards, background-tab restoration, save/reopen or stable topology
references. The [planned public slice](../design/edge-fillet-creation.md) retains
those separate boundaries; a successful native call is not the complete feature.
