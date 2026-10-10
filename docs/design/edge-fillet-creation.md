# Exact edge-targeted fillet creation

Status: **planned after a8**, not an advertised operation or a release promise.
This is the next proposed use of a8's exact edge observations. Native feasibility
and installed Windows/Wine gates must precede public exposure.

## First increment

Create one symmetric, circular, constant-radius fillet on **one explicitly
identified edge** of a writable, single-configuration, single-solid part.
Require a positive finite radius in millimeters. Start native calibration on
an exterior straight edge of a rectangular boss; do not infer support for all
edges from that fixture. Tangent propagation, multiple targets/radii, face/full-
round/partial fillets, conic profiles, surfaces and assembly features remain
outside the first contract.

The proposed operation is `feature.fillet`, with an exact `e-` edge handle and
`radius_mm`. CLI spelling and final result fields follow the proven adapter,
not the other way around. A face handle, stale scope, unknown or cross-document
handle must fail before native mutation. Coordinates, edge array indices,
localized names and whatever is currently selected are not target selectors.

Observation is not write authority. Resolve the document/session, enforce its
lease and expected update stamp, then verify the complete live edge set,
persistent-reference round trip, native identity and owning solid. Reuse the
existing document/entity registries instead of adding a second identity system.
GUI edits and other daemons remain outside the lease boundary.

## Native feasibility before protocol implementation

SOLIDWORKS documents constant-radius creation through
[CreateDefinition](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~CreateDefinition.html),
[ISimpleFilletFeatureData2 initialization](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISimpleFilletFeatureData2~Initialize.html)
and `CreateFeature`. Its
[FeatureFillet3 documentation](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~FeatureFillet3.html)
marks that older creation path obsolete for constant-radius fillets since 2020.
Prefer the definition-based path for calibration, not a long opaque argument
list copied from an unrelated macro.

Prove late-bound COM bindings, native enum values, explicit radius/profile and
disabled tangent propagation on the supported SW2025 host. The data object's
[Edges property](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISimpleFilletFeatureData2~Edges.html)
does not by itself prove that creation or post-creation selection access is
side-effect free. Calibrate exact object targeting and native target readback;
do not silently fall back to location/name selection when a binding fails.

Run on the resident STA with native-call begin/end traces. Before taking owned
selection access, establish whether an existing selection can be restored
exactly; otherwise reject it before changing it. Preserve the former foreground
and session current. No global display/inference preference changes are needed
merely to create a fillet.

## Result and failure evidence

Retain the exact feature returned by creation, not ActiveDoc's last feature.
Verify its native kind, requested radius/profile/propagation and target scope,
complete rebuild diagnostics and final one-solid metrics. A non-null COM result
alone is not success. Adding a fillet handle must not imply that the existing
extrusion-only `feature.inspect/set-depth` adapter supports it: extend typed
observation deliberately or report that limitation explicitly.

Any owned selection/access must be released and restoration verified, including
failures. Record whether creation may have happened and the available exact
feature/diagnostic/metric evidence. Never retry, save, delete the partial feature
or restart the host automatically. A failed postcondition is not rollback.
After a changed native stamp, old face/edge IDs stay stale under the a8 policy;
clients rediscover and reconsider targets before another edit.

## Gates

- Portable failures: invalid radius and kind, stale/cross-document targets,
  lease/CAS rejection, unknown native settings, null/false-success creation,
  wrong radius/target scope, unhealthy rebuild and restoration failures.
- Native calibration: generated box, one exact edge, one radius. Independently
  verify volume removed against `(1 - pi/4) * radius_mm**2 * edge_length_mm` for
  the known convex right-angle fixture. The fixture length is independently
  known; this does not add an edge-length promise to `entity.inspect`.
- Same-host continuation: background-document restoration, stale-ID refusal,
  rediscovery, native save/close/reopen and unchanged read-only observations.
- Installed Windows visible/hidden and DockerSW hidden Wine use the shared
  script, without retrying failed CAD operations or replacing the host between
  modeling and driving gates. Keep the six export artifacts unchanged.

This plan does not claim MacSW validation, general topology survival, editable
fillet radius discovery or a transaction guarantee.
