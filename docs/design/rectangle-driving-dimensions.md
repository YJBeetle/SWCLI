# Next slice: rectangle driving dimensions

Status: internal size creation/read/edit and explicit center-fix adapters verified on **visible Windows**.
The development typed operation `sketch.fix-center` is now wired to the CLI,
catalog, result contract and document/lease/stamp/foreground guards. Installed
public Windows and Wine verification is still pending; this is not an a5 capability.
The existing shared driving gate now exercises explicit fixing on three planes,
repeated no-ops, lease/stamp refusal, background restoration and native
save/close/reopen readback with fresh sketch handles. The front-plane case uses
the installed CLI with `--document` before the positional sketch ID. It also
checks origin-relation refusal without mutation. No host restart or retry is
inserted between modeling, diameter edits and these center checks.
The [probe record](../verification/rectangle-dimensions-2026-10-08.md)
distinguishes size control from positioning. No public command names or result
Schemas are committed here for the size/discovery slice.

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
before activation. The original fixed-center fixture has now been replaced in
an independent source-only probe by the explicitly invoked internal center-fix
adapter. Its development typed wrapper fixes only the verified current center;
it accepts no coordinates, guessed point IDs or implicit size changes. Existing
exact fixes are verified no-ops. Native snapshot IDs in results are evidence,
not persistent references or registered constraint handles.
The internal read adapter verifies the bound native type, complete display chain
and independent rectangle geometry without activation, selection, rebuild or
sketch editing. It observes driven/read-only/external controls without overriding
them, reports geometry mismatch, and rejects changing/incomplete reads.
The internal single-axis edit verifies both dimensions and the original center,
current configuration, complete rebuild diagnostics and fresh downstream
measurement. It refuses external controls and existing edits, reports possible
mutation for any attempted setter failure and never adds a position constraint.
The internal center observer proves native corner connectivity, two exact
construction diagonals and two unsuppressed center/diagonal coincidences. It
uses entity-kind-scoped GetID pairs within the exact owning sketch, not point
wrapper equality, localized names or coordinate coincidence. These are snapshot
keys, not persistent IDs. Its read adapter verifies unchanged stamp/config/edit.
The separate internal center-fix adapter adds one native FIXED relation to that
verified point, checks relation definitions, unchanged geometry/configuration
and valid solver state before/after sketch exit, and preserves partial failure
evidence. An already verified fixed center is a read-only no-op.

This first positioning slice deliberately rejects absorbed profiles, additional
or suppressed center relations and fully constrained profiles without an exact
existing fix. In particular, a rectangle created at the origin can already have
an automatic point/origin coincidence: reject it before selection/edit rather
than adding a redundant FIXED relation or pretending arbitrary position controls
were analyzed. Size operations themselves are unchanged by this restriction.

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
   tests and visible Windows proof. Read-only width/height inspection also has
   absorbed/background-document proof. Single-axis edits of absorbed profiles
   have visible three-plane size/center and volume proof. The explicit center-fix
   adapter also has same-host three-plane size/edit/volume proof, exact native
   relation readback and origin preflight refusal. Saved-model discovery and
   installed public contracts remain pending.
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
