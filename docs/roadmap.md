# Product roadmap

This is the project's execution roadmap, not a promise of release dates or
protocol stability. Capabilities and the installed version are authoritative.

## v0.1.0a4: first reusable part-modeling loop

Implemented and covered by portable tests and native Windows smoke:

- one operation catalog for parameters, result contracts and execution guards;
- unsaved part creation with exact, short-lived document handles;
- fresh rectangle/full-circle sketches on origin planes, explicit millimeter
  dimensions and native post-edit verification;
- sketch-ID-based blind solid extrusion, reverse and merge controls, native
  definition and rebuild/body verification;
- new-filename native part save-as, retained live handles/leases, existing-target
  rejection and close/reopen verification;
- read-only native solid-body volume, area and volume-weighted centroid,
  explicitly scoped to body sums rather than a geometric union or material mass;
- sketch-ID-based blind cut extrusion with explicit all-solid scope, common
  normal/reverse direction and native/volume-removal verification;
- read-only sketch-ID observation including native constraint/absorption state
  and line/arc geometry, with explicit incomplete coverage for other types;
- product-facing skill and guide packaged with SWCLI, with an installed-wheel
  resource/Schema gate.

DockerSW's real Wine gate mirrors the part-modeling primitives in addition to
the six existing export outputs. A source/unit/native-Windows pass does not
prove Wine delivery: confirm the relevant DockerSW CI before claiming support.
These features are available in the v0.1.0a4 pre-release, not the older a3 wheel.

## Next modeling increments

The a5 driving-dimension slice is scoped in
[driving dimensions](design/driving-dimensions.md). Its typed creation/inspect/set
operations are available in **v0.1.0a5**. Installed-wheel Windows,
fresh hosted Windows visible/hidden modes and independent hidden Wine delivery
have passed at the exact formal-version candidate recorded in the
[a5 release notes](releases/v0.1.0a5.md). Release assets and runtime CI have
distinct provenance; a green development gate is not itself a publication.

Read-only `sketch.list` is also available since a5 to recover
fresh exact 2D sketch handles from opened/reopened native parts. Native Windows
and Wine discovery gates have passed for the verified development candidate.
Discovery of saved diameter handles is exposed as the narrow operation
`dimension.discover-diameter SKETCH_ID`, following its three-plane internal
Windows proof. It preserves explicit unobservable/ambiguous outcomes, strict
native metadata and unchanged configuration/edit/stamp checks; an empty display
chain is not absence proof. The installed public gate repeats discovery after
native reopen and checks the recovered ID through typed inspection. Fresh hosted
Windows dual-mode verification and independent DockerSW Wine delivery now pass
this slice, including failed-cut continuation in the same hidden host. The exact
commit, artifacts, image promotion and state-preservation checks are recorded in
[the a5 verification record](verification/a5-2026-10-07.md).
Do not infer dimensions from names or claim arbitrary dimension support.

1. Extend driving dimensions/relations beyond the verified single-circle
   diameter slice and add supported feature edits, so the native model is not
   merely editable but intentionally parameterized.
   The next [rectangle size/positioning slice](design/rectangle-driving-dimensions.md)
   has internal creation/read/edit and separate explicit center-fix adapters
   with visible Windows size/center, background-read, volume, exact relation
   and partial-failure evidence. Center fixing initially rejects extra/origin
   relations instead of adding redundant constraints. Its development
   `sketch.fix-center` CLI/protocol contract now preserves native evidence and
   enforces the existing document/lease/stamp/foreground guards. The shared
   driving gate now covers three-plane fixes/no-ops, origin refusal and native
   reopen with expired-handle rejection. Installed public center-fix verification
   now passes fresh hosted Windows and MacSW software-renderer visible/hidden
   gates, with independent terminal-artifact review; exact versions and proof
   boundaries are recorded in the
   [rectangle verification record](verification/rectangle-dimensions-2026-10-08.md).
   Development `sketch.dimension-rectangle` and role-specific `dimension.inspect/set`
   contracts are now wired with exact IDs, per-step native evidence and existing
   guards. Installed size creation/read/edit now pass local Windows visible/hidden
   gates (`9380bc9`). The development `dimension.discover-rectangle` contract and
   shared save/reopen gate are implemented, and local installed Windows dual-mode
   discovery passed at `c402c23`; hosted Windows dual-mode discovery also passed
   at `f4dd43c`. Wine proof remains unfinished. These results are not an a6 release or an a5
   wheel feature.
2. Extend profiles/end conditions and selected-body/face support only with
   explicit reference and verification semantics.

Each increment needs request/result Schema, document/lease/stamp guards,
portable failure tests, real Windows proof and the appropriate Wine gate.
Partial mutation is not rollback; do not publish an automatic transaction
guarantee without implementing and proving its recovery boundary.

## Later protocol and integrations

- Stable entity references with topology/revision validation and explicit stale
  reference behavior, not guessed feature names or face indices.
- Batches/transactions with documented partial-result and recovery semantics.
- Typed Python SDK and a thin MCP adapter over the same daemon protocol; no
  second public COM/raw-Python execution surface.
- Authenticated encrypted remote transport, workspace/file transfer and
  artifact IDs/downloads before treating server paths as a remote product API.
- Assembly and drawing creation/editing after the part loop is reliable.

The longer-term application goal includes translating supported OpenSCAD
descriptions into editable SOLIDWORKS-native sketches, dimensions and feature
trees, not silently falling back to mesh-only import. The converter is an
upper-layer application; this goal does not require designing it now.

## Release gate

The current pre-release and its verification boundaries are recorded in
[v0.1.0a5 release notes](releases/v0.1.0a5.md). A pre-release does not imply a
stable compatibility commitment.

Continue pre-releases until the protocol and recovery boundaries can support a
compatibility commitment. A new release must name its exact verified commit,
installation command, Windows/Wine evidence and known limitations. Do not
equate a built wheel, a registry push or cached installation with successful
real modeling/exports. CI filename routing stays in the consumer's workflow;
do not recreate a generic `sw-export` policy wrapper.
