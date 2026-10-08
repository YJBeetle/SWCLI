# Next slice: rectangle driving dimensions

Status: internal creation adapter verified on **visible Windows**, not an a5
or public CLI capability.
The [probe record](../verification/rectangle-dimensions-2026-10-08.md)
distinguishes size control from positioning. No public command names or result
Schemas are committed by this design note.

The strict read-only rectangle observation primitive is implemented and has
portable topology/metadata/ordering tests. Shared native length metadata now
accepts an explicit internal diameter/width/height role; it does not infer that
role from a name or reinterpret a diameter response as a rectangle dimension.
The internal creation adapter now creates exact width/height native handles,
verifies each solver step's dimensions and unchanged center, and retains partial
failure evidence. Three-plane Windows probes cover same-size creation, an
explicitly positioned fixture's resize and refusal of unanchored center drift.
Internal registry entries retain an explicit profile/dimension binding and
refuse contradictory roles for the same native object. Public inspect/set
contracts still support diameters only and reject internal linear bindings
before activation; the probe's explicit fixed-center fixture is not an
implemented positioning operation.

## Narrow acceptance target

An exact axis-aligned native center-rectangle profile gets width/height driving
dimensions, remains a rectangle after edits, changes downstream extrusion volume
as expected and can be observed after native save/close/reopen. Initially reject
nonrectangular, rotated, ambiguous and already-dimensioned profiles. Use exact
native entities and independent geometry, not localized names or array order.

Width/height control does **not** imply preserved center or full definition.
Observe bounds and center before/after every solver edit. The visible probe
moved an unanchored center; adding an explicit native fixed-center relation
preserved it. Do not silently fix the center inside a size command. Positioning
must be an explicit, separately verified intent, whether exposed through its
own operation or an explicit constraint option. The initial implementation
must report/refuse unintended placement changes rather than hiding them.

## Implementation boundaries

- First add a strict, read-only rectangle observation primitive. Validate four
  unique connected axis-aligned straight edges and finite sketch-local geometry;
  construction geometry must not masquerade as a profile edge. A rectangular
  bounding box alone is not proof of a rectangle.
- Resolve horizontal/vertical edges geometrically and retain their exact COM
  objects. Internal snapshot indices are not public or persistent references.
- Reuse native type/value, exact owning-sketch identity, current configuration,
  equation/design-table/read-only refusal, edit and preference cleanup. Do not
  reinterpret the existing diameter-specific result as a generic length.
- Dimension registry metadata now carries explicit profile/dimension kind;
  still verify linear inspect/set/discovery before exposing those bindings.
  Re-observation cannot change a live object's semantic role or discard handles
  when a conflicting binding is detected.
- Two dimension creations are not an atomic transaction. A failed second step
  may leave the first dimension; return its exact handle/evidence. Do not retry,
  claim rollback or discard the original native failure during cleanup.
  An unsuccessful or cleanup-failed adapter result must not publish its partial
  handles as verified width/height bindings. Initial creation accepts an empty
  observable display chain, not proof that arbitrary saved or hidden dimensions
  are absent.
- Keep document/session selection, foreground restoration, lease/update-stamp
  guards and terminal request replay on the same daemon-only surface.

## Gate order

1. Pure profile observation: malformed/native metadata, topology, degeneracy,
   large/nonfinite geometry, near-corner ambiguity and shuffled edge order.
2. Internal adapters: independent size/center verification, unchanged other
   size, failed/partial creation and owned cleanup tests. Creation has portable
   tests and visible Windows proof; explicit positioning and existing-dimension
   edits still need their own native readback and verification.
3. Registry/catalog/request/result/CLI contracts, including background documents
   and stale/leased/stamp-conflicting handles.
4. Installed public Windows gates on front/top/right, visible and hidden, with
   native save/reopen/discovery. Extend existing shared gates rather than adding
   a parallel smoke framework.
5. DockerSW runs the same gates on its default hidden Wine host. Preserve six
   existing export outputs and ten-minute phase budgets. MacSW owns macOS host
   delivery; a version update alone is not its runtime evidence.

Only after public native proof should the READMEs/product skill advertise new
commands. SDK/MCP, OpenSCAD, arbitrary relations and topology references remain
separate work.
