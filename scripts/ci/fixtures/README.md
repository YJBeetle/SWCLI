# Native origin-bound rejection fixture

`rectangle-origin-bound.SLDPRT` is our generated SW 2025 (33.5.0) part, not an
installation-media model. It contains one front-plane, 40x30 mm center rectangle
at (0,0), four profile sides, two construction diagonals and five sketch points.

Its center has three actual native coincident relations (type 9): two point-line
relations (entity types 2,3) to the diagonals and one point-point relation (2,2)
to the sketch origin. The extra origin relation is why `sketch.fix-center` must
return `UnsupportedCenterConstraint`; zero coordinates alone do not imply it.

Generated and reopened read-only in local macOS/Wine SW 2025 on 2026-10-09.
Native geometry/relations were identical before save and after reopen. The
adapter refused both observations. This is fixture certification, not hosted
Windows or software-renderer CI acceptance.

SHA-256: `0cea2c4681bb6fe98ea8aea8c72790742faf1df5b50df88b9932ca7b9f08ce98`.
The shared gate checks this hash and copies the fixture to its existing shared
output directory, then opens it read-only. It never saves or regenerates it.
Missing/corrupt assets fail instead of skipping the negative assertion.

To regenerate with Windows Python/pywin32, close SOLIDWORKS and run:

```powershell
python scripts/ci/fixtures/generate-origin-fixture.py C:\Workspace\NEW-origin-bound.SLDPRT
```

The maintainer-only generator deliberately uses native UI inference to attach
the origin, verifies actual relation kinds, verifies refusal, saves only to a
new path, closes/reopens and rechecks. It restores preferences and normally
exits its owned instance. Review the binary and update the gate's checksum when
replacing it. This is not a product raw-COM/debug entry point.
