# Drawing API calibration — Windows, 2026-10-23

Internal API evidence only, not a new public drawing command or Wine proof.
The visible SW2025 host reported revision `33.5.0`; work stayed in generated
fixtures under `C:\Workspace\SWCLI-tests`. No existing user model was edited.

## First failure retained

`drawing-native-20261023-first` created the saved clean 40 × 30 × 10 mm part
and a drawing from the installed `gb_a4.drwdot`, but failed before inserting
views: `GetViews` returned nested raw `PyIDispatch` objects rather than Python
Dispatch wrappers. The failed property lookup is not a failed native view
creation. Commit `7650776` wraps the returned objects explicitly and identifies
the documented first sheet pseudo-view; unreferenced later views fail rather
than being silently discarded. Cleanup completed without errors.

## Successful first-angle observation

`drawing-native-20261023-bindings` passed at `7650776` with empty cleanup errors.
Official installed `swconst.tlb` gave `swDwgPaperA4size=6`; NewDocument arguments
were paper 6 and zero width/height, deliberately matching the A4 template.
This does not prove paper inheritance for arbitrary templates.

The original sheet properties were `[6,12,1,1,1,0.297,0.21,1]`. The sheet's
first-angle flag selected one `Create1stAngleViews2` call. Three model views
were then observed, plus the separate sheet pseudo-view. All referenced the
generated part and its saved native configuration. Positions, outlines, scale
ratios and model-to-view matrices were captured. Native automatic scaling
changed sheet scale from 1:1 to 2:1; this is observed behavior, not a promised
fixed layout/scale. SaveAs3, close, reopen and repeated three-view reference/
configuration checks passed. The owned SW process exited normally.

The template reports a legacy format path
`v:\updated cs\a4 - gb - landscape.slddrt`. The calibration did not resolve or
prove external format availability/title-block fidelity; the reported path
alone is neither proof of corruption nor proof of complete formatting.

| Evidence in the successful directory | SHA-256 |
| --- | --- |
| `report.json` | `f007cec3deca1858e6392915243f9dbc9a8fccae44ca6e400c177c401eedb92b` |
| `trace.jsonl` | `b1ec3f6c7ddc12612705ff672ab7efd5e078313f9b855e48cef8a90fbbad1405` |
| `fixture.SLDDRW` | `c0589a179573332e6dcaad63f427d8c23624ce80ffcf6443043090204e605582` |

Remaining gates: deliberate projection change preserving template state,
orientation/layout classification, full source-state invariance, ASM reference,
strict PDF/DWG exports and Windows/Wine typed integration. No runtime passed
merely because the portable calibration-script tests passed.

## Explicit third-angle projection

The subsequent `drawing-native-20261023-third` run at `23087b8` passed with no
failure or cleanup errors. Before invoking the setter, the installed SW2025
`sldworks.tlb` confirmed ISheet.SetProperties2's eight arguments and void
return: `(I4,I4,R8,R8,BOOL,R8,R8,BOOL)`. No boolean success was invented for
that void method. The [official getter documentation](https://help.solidworks.com/2018/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.isheet~getproperties2.html)
explains the corresponding eight property slots.

Changing first-angle to third-angle through SetProperties2 and rebuilding
preserved the other seven sheet properties, sheet name and format path on the
generated drawing. Three model views then referenced the exact saved part and
configuration. Native save/reopen preserved those references and the third-angle
flag. Source path/configuration/modified/update stamp matched the baseline both
after insertion and after drawing reopen. The owned SW exited normally.

The native matrices and positions differ consistently between both runs:
front is identity; the horizontal-axis rotation view is below front for first
angle and above front for third angle. Both side views are placed to the right,
but their rotation matrices have opposite signs. These are raw calibration
observations, not yet a general orientation classifier. Both runs auto-scaled
to 2:1. The legacy external format path was confirmed absent; embedded format
fidelity still needs separate validation rather than a silent path rewrite.

| Third-angle evidence | SHA-256 |
| --- | --- |
| `report.json` | `81cb03fe5388fd7df7f093fbe1c40dd959a3f7baf5e82c23a1c0a44889c708f2` |
| `trace.jsonl` | `98367675135767212f276c7d1f84e34036abe3e6491320a95db7d321dac0958f` |
| `fixture.SLDDRW` | `ed0fbdc9726b3663690c64f5b743ad93d743b069b578587d1527ba9ac00947fa` |

Projection/source invariance is now proven for this native PRT fixture.
ASM, general template inheritance, orientation/layout predicates, exports and
typed Windows/Wine integration remain open. Public drawing commands and a
MacSW CLI update have not been completed by this calibration.
