# Part Image Quality and GLB evidence boundary

This branch adds document display-quality observation and a **default-closed
internal write candidate**, not accepted GLB export-option support. No release,
main integration, production host or local Windows VM is involved.

## Public contract

- `document.image-quality` / `document image-quality`: one complete part-only
  snapshot. `shaded_mode` is coarse/fine/custom/other, not a slider percentage.
- `document.image-quality-set` / `document image-quality-set FIELD VALUE`:
  field-specific typed value, complete `expected_quality`, required
  `expected_update_stamp` and `lease_id`. CLI uses `--if-quality`,
  `--if-update-stamp`, `--lease`. SDK methods and MCP `execute` share this schema.
- Writable candidates: `shaded_mode` (coarse/fine, native 1/2; custom=3 is observed only),
  `shaded_deviation_mm` (native meters), `optimize_edge_length` (boolean).
  Read-only observations: `save_tessellation`, `apply_to_referenced_parts`.
- Snapshot: five normalized values, all five raw `native` members, and
  `deviation_range: {status, bounds_m}`. Status 0 has two actual native bounds;
  status 1 has no bounds and cannot authorize a deviation write. Status -1 or an
  unexpected return shape fails. No alternate getter retry is performed.
- CAS compares the complete snapshot exactly. JSON int/float equivalents are
  allowed, booleans are never numeric substitutes, nonfinite/duplicate/nested
  invalid JSON is rejected. Target readback/noop tolerance is 1e-12 mm.
- A custom deviation uses one Double setter. Its transition to observed custom
  mode is a declared linked change; the readback must actually classify as custom.
  The convenience preset setter accepts coarse/fine only: native Integer custom
  returned True but stayed fine on 33.5.0, so that target is rejected before COM.
  Preset changes may explicitly report linked deviation changes; native range
  changes and all unrelated members still fail. No second setter or rollback.
- Lease/stamp checks precede native access. The adapter preserves path/title,
  type, configuration, edit context, access mode and foreground. Setter false,
  exception or non-boolean results stop immediately with partial mutation
  evidence. Unexpected results remain serializable so schema validation cannot
  replace the first native cause. At most one dirty mark follows verified
  readback. Same-value operations call no setter or dirty mark.

Without `SWCLI_IMAGE_QUALITY_CALIBRATION=1` in the daemon process, writing returns
`DocumentImageQualityUnsupported` before native preference access. The dedicated
owned-host CI wrapper enables it only for its new daemon and restores the parent
environment. This switch is internal; a passing calibration does not
implicitly promote the candidate to public acceptance.

## Official evidence

[Document preference range API](https://help.solidworks.com/2023/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~GetUserPreferenceDoubleValueRange.html)
distinguishes current/min/max success (0), current-only (1), failure (-1).
[Document preference API](https://help.solidworks.com/2023/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~GetUserPreferenceDouble.html)
uses a document extension and the explicit no-option selector.
[Official shaded quality enum](https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swImageQualityShaded_e.html?id=2.10.1.427)
confirms coarse/fine/custom modes and the separate custom-deviation preference.
The offline official 2025 sample header declares Integer 44 / Double 32 /
Toggle 210, 255, 158 and shaded modes 1/2/3. The internal gate verifies **every
one** against the installed official `swconst.tlb`, records its SHA256 and fails
on any discrepancy.

[XR export UI](https://help.solidworks.com/2025/german/SolidWorks/sldworks/t_export_using_extended_reality.htm)
contains format-specific scene/animation/Draco options. Their public automation
mapping is unverified here. No invented `IExportGltfData`, arbitrary COM option
dictionary, registry write, global preference setter or STL parameter is used.
Image Quality API readback is not evidence that GLB tessellation changed.

## Targeted Windows calibration

Manual CI input `image_quality_calibration=true`, `native_full=false` works only
on `codex/docprops-export-options`. Targeted concurrency uses its own profile +
`github.ref` with cancellation disabled; full/release retain the original group.
It reuses the installation job, skips
property/annotation fixtures and visible/full modeling suites, and invokes one
owned hidden daemon. It never enables PR-secret workflows. Per request: 600 s;
whole calibration: external hard 1800 s watchdog, including SDK/decode/cleanup.
First failure stops. No API retry, group restart or automatic rollback.

The installed public CLI generates an analytic cylinder (r=10 mm, h=10 mm) and
box (40×30×10 mm), verifies kernel volume/area, changes edge optimization,
coarse/fine/custom mode and a legal actual custom deviation. It checks full CAS
refusal and noops, native call counts/order and one setter per changed request.
The SDK independently reads the same background handle under another session.
Before its first setter, each fixture is saved, reopened read-only with raw
quality/geometry/hash checks, and reopened writable; the baseline file is
retained unchanged even on first-call failure. Each quality level is then saved
to a distinct native file, strictly exported once,
closed, reopened with a fresh read-only handle, checked for complete **raw**
quality persistence and unchanged geometry/file SHA. It then reopens writable
for the next level, preserving a single host throughout.

The diagnostic parser inspects actual binary positions/normals/indices and
triangle/strip/fan modes. Draco requires real `DracoPy` decode with attribute
IDs from the GLB extension, plus count agreement against accessors; compressed
byte size is never treated as topology. Unknown required extensions, sparse or
unsupported attributes, external buffers, invalid indices, nonfinite data and
incomplete chunks fail closed. Bounds are explicitly **mesh-local**.

The report records triangle counts and whether differences were observed, even
if no difference occurs. It compares materials, scene/extensions and options
observable in the artifact. The six XR preferences cannot yet be independently
read/fixed, so it records `glb_control_proven=false` even when triangle counts
differ. This is an association under one unchanged process's defaults, not a
validated general exporter control. A separate XR API mapping and controlled
format-option experiment remain required.

Original reports, CLI stdout/stderr, request journal, native trace, saved parts,
GLBs and cleanup receipts are uploaded on success or failure. Portable fake
host tests and synthetic/actual Draco parser tests prove gate behavior only.
They cannot be substituted for Windows evidence or full public acceptance.


The property-persistence group is independent of the GLB experiment: it runs
first with `--document-properties`, covers both fixtures and both boolean
values, and explicitly records no GLB coverage. Only after it succeeds does the
strict GLB group start in the same owned host. Each group retains 600/1800 s
budgets; the whole CI step remains capped at 35 minutes. An exporter failure
cannot be relabeled as a property API failure or used as property acceptance.

A native 33.5.0 artifact declared 3696 embedded buffer bytes but contained a
zero-length BIN chunk. The production container check now rejects that case;
metadata/accessor counts are not mesh evidence. The next internal experiment
uses an ASCII staging basename with a single `.glb` extension, enabled only by
`SWCLI_GLB_PLAIN_STAGING_CALIBRATION=1` in its owned daemon. This tests a filename
hypothesis without changing the API, preferences or retry policy; it does not
establish a cause. Default staging is unchanged. Rejected bytes are retained as
an explicitly invalid CI diagnostic, never published as successful CAD output.


The 33.5.0 Integer-custom failure is preserved in run 42271766677: coarse and
fine had saved/reopened successfully; setting Integer 44 to 3 returned True but
left both the raw mode (2) and deviation unchanged. The official enumeration
explicitly directs custom values to `swImageQualityShadedDeviation`. The next
single-Double calibration must prove its linked custom classification; neither
the True return nor the documented route alone is accepted as native proof.


The prepared separate public gate clears both internal switches. In addition to
installed CLI persistence and SDK observation, it discovers the live write
request/result schemas through the MCP bridge and reads the exact background
handle through MCP, checking raw quality and native trace. This path has not yet
passed native acceptance. A cleanup failure clears every acceptance flag.

At the user-requested closeout, run 42280265165 at c85ca5f remains in progress
before CAD setup. Public writes remain closed and no merge-ready acceptance is
claimed. Follow WORK_HANDOFF.md for the exact snapshot and preserved originals.


Run 42280265165 subsequently failed the unchanged strict readback check: a
single Double request for 0.06927710843373494 mm returned True and selected
custom mode, but the native value became 0.07142857142857144 mm. The receipt
preserved possible mutation and stopped before dirty marking, box or GLB.
The arbitrary range interpolation was therefore an invalid exact test target.
The corrected calibration requests the fixture's initial, independently
observed native custom value after the preset stages, retaining the same
readback, raw persistence, geometry and trace requirements. It does not infer
a quantization grid or prove arbitrary in-range values are exactly writable.
Public writes remain closed. Original failure ZIP and independent first-failure
audit are preserved under run-42280265165 in the handoff artifact directory.
