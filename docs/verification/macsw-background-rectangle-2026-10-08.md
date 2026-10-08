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
