# Modeling and native observation rules

Read these for modeling, dimension/feature edits, entity observation or drawing creation.
The [usage guide](usage.md) contains the concrete workflows and schema examples.

- If `sketch.list` is advertised, discover fresh live sketch handles after
  opening/reopening a part, then inspect the returned IDs. Never reuse IDs
  from a closed document or assume listing also discovers dimensions.
- If `dimension.discover-diameter` is advertised, recover the observable unique
  single-circle diameter using a fresh exact sketch ID. Unobservable is not
  absent; do not guess by name or create a replacement dimension on failure.
- For hosts advertising driving dimensions, use their returned dimension handles
  and inspect parameter ownership before editing. A diameter is not a radius;
  edits target the current configuration and must not override equations or
  design tables. See the usage guide's parameterized-circle workflow.
- For supported rectangles, positioning and size are separate: `sketch.fix-center`
  is explicit; `sketch.dimension-rectangle` does not anchor the center implicitly.
  Inspect/edit the returned width/height roles, not guessed native dimensions.
  See the usage guide's parameterized-rectangle workflow and discovery limits.
- If feature observation/depth editing is advertised, use returned exact feature
  handles, not tree names. Inspection is read-only, not edit eligibility.
  `feature.set-depth` has narrow profile/scope/control guards; equal depth still
  performs native selection access and can advance the update stamp. Read the
  usage guide's depth-editing boundary before editing or handling a failure.
- Verify native state and geometry after a change. A failed operation can leave
  partial geometry; inspect before retrying. Do not claim automatic rollback,
  full constraint solving, or exact measurements from approximate body boxes.
- If `entity.list/inspect` is advertised, use the returned `e-` handles for exact
  read-only faces (default) or edges (explicit `--kind edge` on both commands).
  Never infer kind from an opaque ID. A configuration/stamp change permanently
  retires both kinds; rediscover and reconsider the target, never choose the
  nearest-looking entity. Untrimmed surfaces/curves and raw edge parameters
  are not trimmed boundaries, length/closure guarantees or edit authority.
  See the usage guide for scope/units and unknown/stale handling.
- If `feature.fillet` is advertised, read
  the guide's single-edge boundary first. Use a freshly observed edge ID;
  possible creation retires face/edge IDs even on failure. Do not retry a failed
  fillet or assume its returned feature supports extrusion depth editing.
- For a host advertising `drawing.standard-views`, read the
  guide's drawing workflow. It needs an explicit A4 DRWDOT, projection and a
  saved clean source/configuration. Do not infer drawing creation from PDF/DWG
  export support or save/modify the source to bypass a refusal.
