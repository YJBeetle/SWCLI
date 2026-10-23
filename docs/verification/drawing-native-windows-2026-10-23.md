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
