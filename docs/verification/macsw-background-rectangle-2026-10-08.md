# MacSW background rectangle timeout — 2026-10-08

## Confirmed failure, not yet a root cause

[MacSW run 37727420806](https://github.com/YJBeetle/MacSW/actions/runs/37727420806)
used MacSW `ac3dd87cb84759c362df0b4871fb1df12c20e731` and SWCLI
`86c52f27c0b2bdcfe0bf990debfc840481608d58`. App build, fresh official
installation, fixture preparation and visible owned host startup passed. Native
PID was **488**, revision **33.5.0**, language Chinese Simplified.

Downloaded `MacSW-SOLIDWORKS-runtime-evidence` confirms that `verify-modeling.py`
created A and B, with B foreground/current. On A, a missing lease and a wrong
update stamp were correctly refused before activation; the 600-second lease
was renewed. The **first actual background front rectangle** (100 × 50 mm,
center 10, 20 mm), request `1ef525fa-9bdb-435e-a653-b125fd903736`, then exceeded
its unchanged 120-second worker deadline. The supervisor terminated the owned
worker/SOLIDWORKS. Driving dimensions and hidden mode were not reached.

There was no preceding executed cut in this chain. This is therefore not proof
of the earlier rejected-cut command residue, nor a hidden-mode-only failure.
`ISupportErrorInfo` warnings also occur with successful calls and are not alone
a causal diagnosis. Later cleanup `REGDB_E_CLASSNOTREG` attempts cannot be
reinterpreted as failure of the first, already successful host acquisition.

The original daemon log has no native call boundaries. It cannot distinguish
`ActivateDoc3`, plane resolution/selection, entering sketch edit, rectangle
creation, exiting edit, or final geometry observation. Native Windows and Linux
Wine passing a5 gates do not establish MacSW correctness.

## Next evidence: opt-in call boundaries

Start the daemon with **`SWCLI_TRACE_NATIVE_CALLS=1`** in its environment. It emits
JSON lines with `event=swcli.native-call`, request ID, operation, worker PID,
monotonic timestamp, sequence, stage, call and `begin`/`end`/`error` phase.
Each begin is written and flushed **before** invoking the covered call; end/error
includes elapsed milliseconds, and error includes only the exception type.
No native arguments, return values, exception messages, file contents, lease
tokens or licensing inputs are logged by this diagnostic.

The switch defaults off. It runs on the owning worker thread, adds no COM calls,
and does not retry, adjust deadlines, activate a replacement host or weaken a
geometry assertion. Broken diagnostic output does not replace the original CAD
result/error. Idle/startup probes outside a dispatched request do not emit these
records. Reads through `_com_value`, temporary activation/restoration and the
fresh profile lifecycle are covered; this is not a complete COM profiler.

Match `(worker_pid, request_id, sequence)` and correlate with the business
failure. Nested calls have distinct sequences. If the worker is killed, an
unmatched innermost begin identifies the last covered entered call, **not** a
deadlock or vendor root cause. `end` means returned; a returned failure payload
is still a failed business operation. Absence of diagnostic lines is not proof
that native work never started.

MacSW owns enabling this option for its isolated runtime adapter and collecting
the daemon logs. The shared modeling → driving order, host identity assertions,
120-second operation deadlines and geometry checks remain unchanged. Portable
logger/activation/profile/worker tests are not a macOS runtime pass; subsequent
instrumented runs and the remaining proof boundary are recorded below.

## Instrumented runs: accumulated call latency

[MacSW run 37732440131](https://github.com/YJBeetle/MacSW/actions/runs/37732440131)
fixed SWCLI `93d40e274be9d3714ccab00905fc36a6675fc195`. Fresh installation and
visible startup passed. The first rectangle succeeded in 113.723 seconds;
the following extrusion returned a native feature and reached diagnostics
after `EditRebuild3`, but exceeded 120 seconds during traversal. Ninety
completed trace boundaries covered about 80.572 seconds. The last
`GetNextFeature` began with only about 1.4 seconds remaining, so its unmatched
begin does not establish a deadlock.

[MacSW run 37736636613](https://github.com/YJBeetle/MacSW/actions/runs/37736636613)
restored the official base and used the same SWCLI source. Rectangle,
extrusion, circle and sketch inspection succeeded in approximately 55.971,
48.371, 103.160 and 111.440 seconds. The first cut returned a native feature,
then exhausted its deadline during post-rebuild diagnostic traversal. The
last covered call again began with less than two seconds remaining. Across
37 host samples, SOLIDWORKS CPU median was 177.1%, compared with 0% for the
two Python processes. This locates CPU activity in the native host, but does
not identify a responsible thread, renderer, translation layer or Wine module.

## Local same-instance API-sequence experiment

On 2026-10-08, the existing MacSW main bottle completed both visible and hidden
shared modeling (85 events) followed by driving dimensions (242 events), with
no cleanup errors. Each mode retained one owned host throughout; this is not
a hosted-runner or fresh-installation pass. MacSW does not supply the optional
installed Part/Assembly sample case, so 85 is not the Windows/DockerSW 97-event
matrix.

A separate visible, owned instance (native PID 1004, revision 33.5.0) then
created two fresh Parts and timed reads of the same background Part. In
false → true → false `CommandInProgress` order, the same 18-feature diagnostic
traversal took 4.308, 0.086 and 4.280 seconds; the 20-title-read plus traversal
batches took 4.820, 0.102 and 5.107 seconds. The original false flag was restored
and only this experiment's documents/host were closed. An earlier activation
while the local license server was stopped never reached a timing batch and
is not counted as a modeling failure or part of this comparison.

This supports request-scoped use of the official update-suppression flag on
owned hosts. It does not prove the hosted CI timeout is fixed, does not explain
the independent native `CloseDoc` exception, and does not supersede the Linux
rejected-cut investigation where this flag alone did not fix the failure.
The unchanged shared gates must still validate the implementation on Windows,
Linux Wine and macOS Wine.

## Request-scoped implementation validation

The implementation under test is SWCLI
`f75a56f05ae8246749514dbaf36d49a79b2cf495` (`0.1.0a6.dev0`), not the published
a5 package. Every row below completed modeling followed by driving dimensions
on the same owned native PID, without a restart between gates. All result
files report `success=true`, `state=completed` and zero cleanup errors.

| Host and evidence | Mode | Native PID | Modeling events | Driving events |
| --- | --- | --- | --- | --- |
| [Windows CI 37740915090](https://github.com/YJBeetle/SWCLI/actions/runs/37740915090) | Visible | 2424 | 97 | 242 |
| Same Windows CI | Hidden | 1744 | 97 | 242 |
| Local MacSW existing main bottle | Visible | 1332 | 85 | 242 |
| Same local bottle, separate complete sequence | Hidden | 1972 | 85 | 242 |
| workspaceroot Linux Wine, source-overlay integration check | Hidden | 620 | 97 | 242 |

Local MacSW used the rebuilt App and an explicitly synchronized Windows Python
backend, with a recoverable copy of the previous package. Its generated files
are confined to `C:\Workspace\MacSW-trace-20261008.6A0yEq`. Both sequences
ended with an empty document list and normal daemon shutdown. The optional
installed sample case remains absent, explaining the 85-event count.

Linux used the existing `localhost/swcli-a5-probe:20261008` runtime with the
current `src` and shared CI scripts mounted into a dedicated Podman container.
The original image and public tags were not changed. The test daemon stopped
normally with no open documents; the dedicated container was subsequently
removed, while generated results remain on the host. This is integration
evidence, not an image build, promotion or release.

The Windows CI artifact was downloaded and its four result files inspected.
Visible and hidden box BMPs were also visually checked: both show the modeled
solid. The workflow's packaging, both Python unit-test matrices, real modeling
and export job all passed. Local portable tests ran 619 tests with eight
Windows-only skips; MacSW's established `make test` and `make app` passed.

[MacSW CI 37741088903](https://github.com/YJBeetle/MacSW/actions/runs/37741088903)
used MacSW `71f23a7909e71e870b06bb083b2af634d293b681` and the same SWCLI pin.
Build, fresh installation and official-base snapshot passed, but the runtime
job failed in `Shared modeling then driving dimensions on one host`. Its
first failure was saved background document close, request
`0d553828-551f-47ff-b946-b85ef048e0e0`, returning native `0x800703e6` rather
than a worker timeout. It reached 56 modeling events; driving and hidden
mode were not reached. Two further close failures belong to cleanup.

The preceding rectangle, extrusion and cut operation trace maxima were
23.107, 18.648 and 13.419 seconds. All three planes, inspection, measurement
and native save returned successfully before close. This demonstrates that
this run progressed beyond the earlier accumulated-call timeouts, not that
the hosted workflow is fixed. The same native close error predates the
request-scoped implementation. Twenty-seven host samples still had native
CPU median 176.1%, versus 0% for Python.

The captured server-side access exception is not proof of a whole-process
crash or a responsible vendor/module. The next diagnostic adds opt-in,
immediately flushed `SldWorks.CloseDoc` begin/end/error boundaries through
the existing logger; no title/arguments are logged. The call, document
selection, original failure result and test assertions remain unchanged.

## Separate unresolved local rendering observation

After the hidden local sequence, reopening its saved `model.SLDPRT` and strict
STEP export succeeded. An 800 × 600 isometric BMP also satisfied the existing
file/dimension checks, but visual inspection found a uniformly white image.
Those checks establish a bitmap artifact, not useful scene content.

A separate owned visible host, PID 396, rendered the same read-only model in
false → true → false `CommandInProgress` order. All three BMPs contained one
RGB color across all 480,000 pixels. A subsequent comparison explicitly
calling `IModelView.GraphicsRedraw` before capture was also white in all three
states. Thus enabling the flag is not necessary for this observation; this
does not identify its origin or establish that rendering was correct before
the implementation.

In another owned visible instance, PID 1880, the user brought the SW window
to the foreground and confirmed its state. An otherwise identical CLI render
of the same open document remained white; the before/after BMP SHA-256 values
were identical. The user also confirmed that the actual model area displays
the solid. Thus simply foregrounding the window did not fix this observation;
the visible scene and BMP capture diverge. That foreground comparison alone
does not identify the responsible native API or Wine module. Keep it separate from hosted accumulated
call latency and from the earlier native close exception.

### Linux BMP content comparison

A subsequent workspaceroot check used SWCLI
`fb147c19e65a4d4b2a84e8e8c140c1589171c54e` over the same existing
`localhost/swcli-a5-probe:20261008` runtime: Wine 11.16, SOLIDWORKS 33.5.0,
Xvfb and Mesa llvmpipe. The daemon-owned hidden PID was 616 and the separate
visible PID was 1464. Each host opened both model copies read-only and rendered
800 × 600 isometric BMPs through the actual CLI, then closed both documents.

| Model source | Hidden distinct RGB colors | Visible distinct RGB colors |
| --- | --- | --- |
| Exact MacSW model that produced white BMPs locally | 3683 | 3700 |
| Previous Linux shared modeling gate | 3650 | 3737 |

All four BMPs were visually inspected and contain the modeled solids, not only
a background gradient. All measurements returned five solid bodies and total
volume approximately 308558.406140636 mm³. The transferred Mac model SHA-256
matches the local source:
`e77c6e4c461226ffd507700824e8d4a609ea318944eab2bdfc633ebeb2d5c438`.
An independent 8 × 8 memory-DC OpenGL probe also succeeded: bitmap/GDI/OpenGL
pixel format selected, context made current and all 64 DIB pixels read back red.

The daemon stopped normally with empty document lists; only the dedicated test
container was removed. Evidence remains at workspaceroot
`/tmp/swcli-bmp.ETxLrC/output` and locally at
`/private/tmp/swcli-bmp-linux.En0KlH`. No image or release was changed.
This check did not reproduce the white BMP on Linux, narrowing this observation
to the tested MacSW winemac/CGL path, not proving every Wine host is unaffected.
Native Mac capture diagnostics and the unsuccessful pixel-format advertisement
experiment are recorded in
[MacSW's investigation](https://github.com/YJBeetle/MacSW/blob/master/docs/native-modeling-investigation.md#位图像素格式与离屏-drawable-对照).

## Hosted cut timeout after the bitmap probe fix — 2026-10-09

[MacSW CI 37822674940](https://github.com/YJBeetle/MacSW/actions/runs/37822674940)
used MacSW `2edce5cd0e8578f43c5b556dc05c6ed6dae2a26d` and SWCLI
`fb147c19e65a4d4b2a84e8e8c140c1589171c54e`. Build and installed-base cache
validation passed. All eight memory-DC bitmap/OpenGL cases completed with
correct pixels under Apple Software Renderer; the prior process/pipe wait
failure was not reproduced. The owned visible host acquired PID **504**,
revision **33.5.0**, and entered shared modeling.

The background front rectangle (100×50 mm at 10,20 mm), 20 mm boss, measured
volume approximately 100000 mm³ and radius 4 mm circle all passed. First failure
was the 20 mm cut, request `11e763f6-f503-4e45-8119-47a52b9f8adc`, exceeding
the unchanged 120-second worker deadline. Driving dimensions, model close
verification and hidden mode were not reached. Subsequent cleanup registration
failures occurred after the supervisor terminated the owned host; they are not
evidence that its original startup failed.

The cut trace starts at monotonic 730.643. Target activation returned at 736.796;
the last covered read was `FeatureManager`, ending at 741.831. That leaves
roughly 109 seconds unaccounted for by covered calls. `FeatureCut4`, native
definition reads and cleanup were previously unbracketed, so this is not yet
proof that `FeatureCut4` itself blocked or that a particular Wine/SW module is
responsible. The cut adapter and request-scoped API sequence are unchanged
between this pin and the later development mainline; upgrading alone is not
an established fix.

The next diagnostic uses the existing opt-in logger to bracket selection,
`FeatureManager.FeatureCut4`, before/after measurement and diagnostics, exact
depth/end-condition reads, and `SetPickMode`/selection cleanup. Calls retain
their existing arguments, order and STA thread. Native errors and cleanup
warnings are preserved, with no retry, deadline extension or intermediate host
restart. A returned `None` still produces `CutExtrusionFailed` even though the
native trace reports `end`, not `error`.

Five adapter trace tests cover flushed begin before invocation, matching
boundaries, returned failure versus exception, separate cleanup errors, later
definition failure without cancelling a created cut, and broken output without
changing the CAD result. These are portable instrumentation tests, not a native
macOS runtime pass. MacSW already enables `SWCLI_TRACE_NATIVE_CALLS=1`; its next
runtime run must use the new fixed source and preserve the same modeling chain.
