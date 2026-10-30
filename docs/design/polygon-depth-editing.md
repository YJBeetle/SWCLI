# Polygon feature-depth editing: next bounded investigation

Status: **design only, not implemented or accepted**. The published a13
`8d6e5d3` still refuses polygon `feature.set-depth` with
`UnsupportedDepthProfile`. No new native setter authority, schema capability,
through-all support or release is introduced by this document.

## Current evidence and missing proof

The final a13 Windows and Wine archives prove 48 public polygon blind boss/cut
combinations, exact native closed cycles, saved/read-only reopened models and
fresh feature handles. All 48 polygon depth edits are deliberately refused with
the four mutation flags false. Creation acceptance does not authorize editing.
The exact runtime/archive/package identities are linked from the
[a13 release record](../releases/v0.1.0a13.md).

The existing depth writer already owns controls, lease/CAS, access/release,
current-configuration scope, single commit, rebuild/readback and partial failure
reporting. Its profile gate in `windows_feature_depth_profiles.py` accepts one
exact absorbed circle/axis-aligned rectangle profile with stable repeated
parents/geometry/transform. Keep that writer and its other guards intact.

`windows_polygons.observe_polygon_sketch` checks native edges against the
creation request's ordered vertices. An opened native file has no trusted
creation request. Remembered vertices, a feature name, segment enumeration order
or final body count therefore cannot establish eligibility for a depth write.

## First investigation: native-only profile observation

Add a separately testable observer before changing the depth guard. Its proposed
input is the exact absorbed native 2D sketch already resolved through live
parent/owner identity checks. It must need neither a creation cache nor a public
sketch handle, so the same observation can be repeated after native reopen.

Required observations:

- Complete bounded segment enumeration: 3–64 native lines, no construction
  geometry, arcs, splines, null or unreadable members. Keep the existing circle
  and rectangle routes and their accepted construction geometry unchanged.
- Every endpoint must have finite readable sketch-local coordinates and lie in
  the sketch XY plane within the existing a13 tolerance. Keep the existing
  representability, short-edge, duplicate, collinear, crossing/touching,
  near-touching and sliver rejection rules; do not enlarge a tolerance.
- Reconstruct endpoint adjacency independently of segment order and each line's
  endpoint direction. Require one unambiguous vertex matching, no self/duplicate
  edge, degree two at every vertex, and one connected cycle containing all
  segments. Ambiguous or nontransitive tolerance matches fail closed.
- Traverse the resulting cycle and pass its coordinates through the existing
  pure polygon validator. Require exactly one observable native closed contour.
  Never repair an open/disconnected contour or discard extra geometry.
- Use a documented deterministic cycle representation for repeated native
  fingerprint comparisons, independent of rotation and traversal direction.
  Retain complete vertices/edges and transform as private evidence; area alone
  cannot identify a profile. Canonical order is not the original request winding.
- Require native profile/parent ownership, all segment geometry and the complete
  model-to-sketch transform to remain stable across repeated observations.
  Unreadable native data is an observation failure, not permission to try a
  different profile classifier or native API again.

Portable adversarial cases must cover shuffled/reversed lines, repeated read
ordering, both windings, concavity, four-edge profiles, disconnected cycles,
degree/edge duplicates, construction extras, nonplanarity, malformed native
values and ambiguous endpoint clusters. Fixtures must distinguish a supported
geometric refusal from an unavailable observation. The existing rectangle/circle
tests must remain unchanged in meaning.

## Writer integration remains a separate gate

Only after native Windows observer proof should a narrow profile classification
be admitted into the existing depth writer. There is no new public operation:
the proposed behavior is a carefully evidenced extension of `feature.set-depth`
on an exact live supported blind feature. Do not catch a failed native rectangle
read and silently reinterpret the same sketch as a polygon.

All existing feature controls, supported blind start/end/direction defaults,
single configuration, exact profile ownership, final/rollback body scope,
selected-contour and explicit direction-reference refusals remain necessary.
Extra bodies/surfaces, equations/design tables, thin/draft/two-direction,
through-all, suppression/freeze/rollback and unknown state remain outside scope.
An absorbed polygon does not weaken any of these independent guards.

Preserve the writer's existing owned selection-access/release lifecycles,
no-op semantics and reported stamp changes; staging/configuration/commit ordering and the four
mutation flags keep their existing meaning. A partial failure preserves first
error, exact handle and cleanup evidence. No retry, automatic rollback, implicit
save, daemon restart or group-internal host restart is added. Native 600-second
and per-set 1800-second limits stay unchanged.

## Native and installed acceptance before publication

1. Prove the read-only observer on triangle and concave L fixtures, both
   windings, front/top/right and forward/reverse blind bosses/cuts. Check
   absorbed profile ownership and the native-only fingerprint before and after
   save/read-only reopen. This diagnostic is not full public acceptance.
2. Prove depth growth, shrink and equal-depth behavior through the existing
   exact feature handle, preserving background/session state. For isolated
   constant-section fixtures derive expected volume, surface and world centroid
   independently for each new depth; do not claim a general proportional volume
   rule for arbitrary downstream geometry.
3. Include lease/CAS, cross-document/expired ID and unchanged-state refusals,
   native staging/commit/restoration failures, healthy untruncated diagnostics,
   fresh reopened IDs and saved file hashes. The old a13 depth refusal receipts
   remain valid historical evidence, not the new expected result of an enabled
   future operation.
4. Once the native binding and failure boundaries are proved, update the shared
   public gate and only affected contracts/docs/tests. Preserve full/core coverage
   distinctions and stop the group at its first failure. If a bounded gate cannot
   fit the existing per-set limit, revisit scope/group composition before
   dispatching; do not weaken the native or per-set limits to obtain a pass.
5. Freeze a separate future version and verify its original CI packages plus
   corresponding installed Windows and full Wine receipts. A13 source/tag/assets
   and Docker's released a13 gitlink stay unchanged. Formal publication again
   follows the owner's release-approval boundary.

This investigation is separate from polygon dimensions, arbitrary sketch
editing, persistent topology references, additional end conditions and
selected-body/face support. None is implied by recognizing one simple polygon.
