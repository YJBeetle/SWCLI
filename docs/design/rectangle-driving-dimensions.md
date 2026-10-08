# Next slice: rectangle driving dimensions

Status: native **visible Windows feasibility only**, not an a5 capability.
The [probe record](../verification/rectangle-dimensions-2026-10-08.md)
distinguishes size control from positioning. No public command names or result
Schemas are committed by this design note.

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
- Generalize dimension registry metadata with explicit profile/dimension kind
  before exposing linear handles through inspect/set/discovery.
- Two dimension creations are not an atomic transaction. A failed second step
  may leave the first dimension; return its exact handle/evidence. Do not retry,
  claim rollback or discard the original native failure during cleanup.
- Keep document/session selection, foreground restoration, lease/update-stamp
  guards and terminal request replay on the same daemon-only surface.

## Gate order

1. Pure profile observation: malformed/native metadata, topology, degeneracy,
   large/nonfinite geometry, near-corner ambiguity and shuffled edge order.
2. Internal adapters: independent size/center verification, unchanged other
   size, failed/partial creation and owned cleanup tests.
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
