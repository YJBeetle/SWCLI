# a5 driving-dimension increment

Status: typed CLI/protocol implemented on the **a5 development branch**, with
installed-wheel Windows verification; Wine delivery remains a separate gate.
The published a4 capabilities remain unchanged. Keep one public
daemon-backed execution surface, not a direct-COM/debug mode.

## First slice

Add a real driving diameter to an exact registered, unabsorbed circle sketch.
Initially require exactly one complete non-construction circle and no existing
dimensions. Reject ambiguous profiles, existing edits and driven/read-only
dimensions rather than overriding user intent. Preserve and restore the native
dimension-value prompt preference; verify the final value and circle geometry
after leaving the owned edit. A failed native mutation can retain a partial
dimension: return evidence/handle, not an automatic rollback claim.

The short document/worker-local dimension registry, exact owning-sketch
validation, request/result Schemas and catalog guards are implemented.
Development commands:

```text
sketch dimension-diameter SKETCH_ID --diameter-mm ...
dimension inspect DIMENSION_ID
dimension set DIMENSION_ID --value-mm ...
```

Diameter is not radius. Initial edits target the current configuration only,
with its name reported explicitly. Inspect must be read-only. Creation/edits
must obey document/session/lease/update-stamp guards and restore foreground
without changing session current. Close/reopen or worker restart invalidates
handles; native naming/save-as retains them only while the document is live.

Value editing must support a profile absorbed by a boss/cut and verify native
value, final geometry, rebuild diagnostics and downstream measurements. Do not
equate a successful dimension setter with a correct final model. Multi-config
editing, equations, arbitrary dimension types, center anchoring, full constraint
solving, topology-stable handles and transactions are outside this first slice.

Handles use `m-xxxxxx`, retain an exact native dimension plus owning registered
sketch, and never resolve by localized name. The adapter rechecks native feature
and display-dimension identity on every inspect/set. Same-path external
close/reopen is distinguished by native document identity, not filename reuse.
Set observes equation/design-table ownership before mutation and refuses it.
Background activation is checked on restoration; restoration failure retains
partial evidence but cannot return a successful operation.

## Native feasibility proof

On Windows with SOLIDWORKS 2025 SP5, the private COM probe added a driving
diameter on front/top/right planes, set 16 mm, extruded 10 mm, changed that same
dimension to 20 mm after absorption and rebuilt. Native volume changed from
2010.619298297468 to 3141.5926535897966 mm³, matching pi*r²*h on each plane.
The center was unchanged and the original prompt preference was restored.
This is native adapter feasibility, not installed CLI/protocol or Wine proof.

The installed swconst metadata identifies `swInputDimValOnCreate` as 10.
Late-bound pywin32 requires explicit null IDispatch for circle selection and
a typed double array/method binding for MathUtility point creation. Annotation
placement uses the inverse native model-to-sketch transform; public geometry
units remain explicit sketch-local millimeters.

Official API references: [AddDiameterDimension2](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~AddDiameterDimension2.html),
[SetSystemValue3](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.IDimension~SetSystemValue3.html),
[configuration scope](https://help.solidworks.com/2025/English/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swSetValueInConfiguration_e.html).

## Gates before exposing the slice

1. Native adapter/failure tests: invalid/stale/consumed/ambiguous profiles,
   native status, false-success values/geometry and cleanup failure warnings.
2. Registry and typed contracts: exact ownership, lease/stamp, replay and
   expired-handle tests, including background document selection.
3. Installed-wheel Windows smoke: all planes, duplicate rejection, downstream
   value editing and native save/reopen observation.
4. DockerSW Wine smoke without changing its six standard export artifacts.
5. Update both READMEs and the packaged agent guide only for implemented and
   verified public operations.
