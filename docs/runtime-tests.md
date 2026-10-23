# Shared real-runtime tests

SWCLI owns the CAD test operations and assertions. Its Windows CI prepares a
native SOLIDWORKS host; DockerSW prepares Linux/Wine; MacSW is responsible for
macOS/Wine provisioning. The two integration projects call the same scripts,
not copies of the modeling assertions. These are CI tools delivered in the
source checkout/sdist, not installed `sw-cli` subcommands or a mock backend.

## Entry points

### Coverage tiers and host modes

The modeling and driving entry points accept `--suite core|full` (direct-call
default: `full`). Evidence includes `suite`; driving refuses a predecessor
record from a different tier. Both tiers retain same-host checks, lease renewal,
strict artifact/geometry assertions, per-case empty document catalog checks and
first-failure propagation. No hidden-mode lifecycle-only substitute is used.

- `core`: native modeling, generated assembly save/reopen and mesh exports,
  supplied official sample exports, supplied drawing roundtrips and failed-cut
  recovery. Driving retains the full Front cases (guards, center fixes,
  diameter/rectangle save/reopen and expired handles). Top/Right each verify
  driving diameter, fixed rectangle center, width/height edits and solid geometry,
  without repeating the Front permission/CAS/save-reopen matrix.
- `full`: all original modeling cases, including reverse-cut and feature-depth
  face/edge observations, plus all three-plane driving combinations. Optional
  fixture switches remain explicit in both tiers; no missing fixture is inferred
  as passing. Toolbox remains required by platform wrappers in both tiers.

Windows always runs a lightweight visible startup/open/inspect/close/stop smoke
followed by hidden business tests, using separate instances and evidence.
Main pushes and manual CI runs select hidden `full`, with no coverage-tier input,
without repeating the CAD suite visibly. Each functional set owns a
fresh session, with no restart inside a set. MacSW retains its own host-mode
policy; this does not authorize MacSW signing. DockerSW uses the same independent
visible smoke plus hidden `full` acceptance before image promotion. Six published
exports remain independent. Lower-level scripts retain `core` for focused developer
diagnostics, not an alternative CI acceptance policy.

`scripts/ci/verify-visible.py` is an independent shared entrypoint: it checks
visible/owned/connected host identity, opens one supplied part read-only, inspects
it, closes it, verifies an empty catalog and unchanged host, and requests stop.
Adapters start the host and verify process teardown. It does not create models,
save, rebuild or export, and does not invoke the full set coordinator. MacSW can
call this entrypoint alone when only lightweight visible coverage is desired;
that is not hidden CAD proof. Existing evidence is never overwritten.
The entrypoint accepts `--request-timeout` (default: 120 seconds), reusing the
shared finite, positive, at-most-3600-second validation. Platform adapters may
explicitly select a larger budget for slow hosts; this changes no CAD assertions
or product defaults. The CLI subprocess limit is the request budget plus the
existing 15-second transport grace. Evidence records both limits, and a timeout
still fails the run without retrying the CAD call.

Case methods and shared geometry assertions are in `scripts/ci/gate_support/`.
Entry points retain transport, fixture paths, leases, evidence and cleanup;
platform wrappers only provision and invoke the shared coordinator.

### Isolated functional sets

`scripts/ci/verify-runtime-sets.py` is the shared Windows/Linux-Wine/macOS-Wine
coordinator. Install and prepare once on one runner/container, then run its
platform-independent plan: 11 sets in core, 19 in full. Named entrypoints cover
native modeling, assemblies, exports, drawing Save/SaveAs, continuation,
diameter dimensions, center constraints, rectangle dimensions and Toolbox;
full additionally runs reverse-cut, feature-depth, fillets, drawing creation with
standard views and complete Top/Right cases.
The entrypoints delegate existing CAD assertions; they do not duplicate them.

The full coordinator requires `--drawing-template` with the host's Windows path.
Windows supplies the registry-discovered installation and selects its official
`data/templates/gb.drwdot`, as do the Wine host adapters. Clean installs do not
necessarily contain the first-run-generated `ProgramData/.../gb_a4.drwdot` found
on a configured workstation. An explicit `SWCLI_DRAWING_TEMPLATE` local filesystem
path overrides host selection. Missing templates fail; actual A4 sheet properties
remain checked by the CAD adapter. The drawing entrypoint
uses `--drawing-template` directly (no `--suite`) and writes `drawings.json`.

Every set starts a foreground daemon with a fresh owned SW session and stops it after
checking the real document catalog is empty. Unknown documents, attached/shared
hosts, wrong visibility, remaining SW processes, incomplete proof or shutdown failure stop
the run; failed CAD operations are not retried. The continuation→Front diameter
bridge deliberately runs two scripts in ONE session to retain cross-script
failure-recovery proof. No Wine server, license service or container restart is
performed between sets.

PID values may be recycled, particularly inside Wine. After normal launcher exit
and before the next start, the shared runner checks the native OS process inventory
(`tasklist` on Windows, `ps` on Linux/macOS). It must find no `SLDWORKS.exe` process
within a bounded 30-second wait; unavailable/malformed inventory fails closed.
Evidence records a fresh test-instance UUID and both boundary observations, not globally
unique PID numbers. This does not weaken unchanged-host checks inside a set, kill
leftover processes, or retry failed CAD calls. Run only in an isolated CI environment.

Lifecycle status probes may time out while our foreground daemon is acquiring
SW, or reset after an exclusive empty daemon acknowledged shutdown. Only those
known transitions wait within their original deadlines, with each probe capped
by the remaining time. A timeout/reset on the initial unknown endpoint is fatal;
it does not authorize stopping or starting a host. Shutdown still requires an
acknowledged stop followed by a refused connection, or an explicitly tagged
connect timeout (Windows closed loopback ports may time out instead of refusing).
A generic timeout/reset alone is never shutdown proof. Startup still requires a live launcher and an
exclusive connected host. CAD failures and post-case health failures are never
retried. Windows-only extra-host startup uses an elapsed-time deadline too.

Use `--output-dir` and its matching Windows `--host-output-dir`, `--mode`,
`--suite`, the installed sample paths, and a private `--fixture-work-dir` with
matching `--host-fixture-work-dir`. An integration wrapper may supply one
absolute executable `--cli-command`; Windows defaults to the current isolated
Python's installed SWCLI. `runtime-sets.json` records expected/completed sets,
per-set host/server PIDs, step records, shutdown status and finite budgets.
Public modeling/driving/Toolbox result files and command logs remain separate.

Source-only integration adapters also supply repeatable `--python-path` absolute
source/dependency directories. Child scripts retain `python -I`; an explicit
bootstrap inserts only these trusted directories, never ambient `PYTHONPATH` or
the working directory. Windows and MacSW keep the default installed-package
path. Evidence records the explicit paths. Windows pins foreground daemon
handles at launch and records bounded shutdown/exit-code proof even when the
preflight launcher exited long before the final check; null/nonzero exits fail.

With `SWCLI_TRACE_NATIVE_CALLS=1`, document opening also flushes native boundaries
around `SldWorks.OpenDoc6` (including dispatch lookup) and subsequent document
description. These contain no file/configuration arguments and preserve native
results/exceptions. A pending open boundary enables existing bounded macOS host
sampling; no timeout extension or failed-operation retry is introduced.

The Windows wrapper supplies the installed `bezel moldbase.slddrw` in both
tiers and modes. The shared coordinator copies the complete sibling reference tree to a unique
temporary directory outside uploaded evidence, then delegates both drawing
Save3 and native SaveAs roundtrips to the shared modeling gate. Missing fixtures
fail explicitly; temporary references are cleaned on success and failure without
masking the original gate error. Only validated drawings and result records are
published as evidence; installed drawings are never saved in place.

### Full case catalog

- `scripts/ci/verify-modeling.py`: capabilities, native update stamps, leases
  and stale-write rejection, background sketches/extrusions/cuts, analytical
  measurements, native save/reopen and existing-target protection. The final
  case rejects a nonintersecting cut, checks no cleanup warnings, closed sketch
  edit state and unchanged solid geometry, closes the native document, then
  creates a new background circle **without restarting the host**.
  Its a7 `feature-depth` case independently creates a single-solid
  rectangle boss/circle cut, verifies lease/CAS and cross-document refusals,
  edits boss/cut depths with analytical volume checks, checks equal-depth
  calls skip setters/commits/rebuilds while retaining complete selection
  restoration, saves/reopens native depths with fresh handles, and requires
  a read-only reopened part to reject depth edits before selection access.
  The a8 gate reuses that same fixture for complete discovery of
  8 faces and 14 edges (12 box lines and 2 blind-hole circles), analytical face
  geometry, raw edge endpoints and line/circle geometry. Repeated reads must
  preserve IDs across mixed face/edge groups; wrong-kind, CAS and cross-document
  lookups must fail. Real depth writes retire both kinds, and read-only native
  close/reopen must issue fresh IDs. Reordered traversal and opposite native
  curve/edge sense are accepted; no edge length, closure or normalized trim is
  inferred. It uses the installed CLI, not COM setup or a new host; the six
  export artifacts are unchanged. Lease renewals surround additional read and
  refusal groups on slow hosts, without increasing TTL or retrying failures.
  These are required gate assertions, not proof that every host has passed.
- `scripts/ci/verify-driving-dimensions.py`: three-plane driving diameter
  creation, inspect/edit, guards, native save/reopen and discovery of fresh
  sketch/dimension handles; explicit center fixing and saved fix readback;
  rectangle width/height creation, leased background inspection, single-axis
  edits with preserved other size/center, downstream native volume and expired
  handle rejection. Saved rectangles are closed/reopened read-only and expose
  fresh exact width/height handles via `dimension.discover-rectangle`; repeated
  discovery and inspection must preserve IDs, stamp, geometry, configuration
  and both sessions' foreground/current state. The front-plane size commands
  and discovery use the installed CLI with the selector before the handle.
  This describes the gate's required checks, not a completed host proof.
  Run it after modeling on the same ready daemon.
- `scripts/ci/verify-invalid-requests.py`: invalid wire requests must leave
  the host and documents unchanged.
- `scripts/ci/verify-toolbox.py`: verify the configured Toolbox database,
  nonempty official index and nonempty native parts for every enabled standard.
  Then open one deterministic representative part read-only through the public
  CLI, diagnose without rebuilding, measure solid geometry and close only that
  owned document. It checks unchanged source bytes, document state, pre-existing
  documents and the original host. No COM escape hatch or updater invocation.

Windows-only startup/attach/disconnect behavior remains in
`scripts/ci/windows/smoke-solidworks.ps1`; its equation fixture deliberately
uses native setup and is not presented as a cross-platform public CLI test.
Installer and Wine lifecycle checks belong to their respective host projects.
Toolbox installation/repair remains host-owned; the shared gate only verifies
the deployed result and public document operations. Each wrapper requires it
after modeling/driving on the same host. A failure blocks delivery, never triggers
a repair, restart or retry of the operation.
The six DockerSW published export artifacts remain a separate delivery gate.
Shared modeling and the Windows wrapper explicitly request `capabilities
--full --json` so detailed request/result contract drift remains a CI failure;
normal clients use the small summary or one operation instead. Health probes
do not serialize the schema catalog.
Windows complete acceptance runs `-VisibleSmoke` then `-Hidden -Suite full` using
one installation and independent evidence directories. The visible smoke checks
an exclusively owned, connected host with `visible=true`, reads one installed
part read-only, checks unchanged host identity and an empty catalog, then stops
its own daemon/SW. It never runs CAD, dimension, export or equation cases.
Business runs require `-Hidden`; visible success is not full interactive CAD proof.
Its native job downloads
the same run's `swcli-dist` artifact, requires exactly one wheel, installs it
normally and verifies installed resources before either mode. It does not use
an editable checkout as the native runtime; the checkout only supplies the CI
scripts and fixtures. Each hidden functional set retains an unchanged native
PID; the continuation-to-Front-diameter bridge retains that same host across
its two scripts. Passing visible mode is not proof of hidden/background behavior.
The Windows-only equation setup runs in a separate hidden test daemon. A
source-delivered, test-only launcher prepares the exact equation fixture in the
worker's existing STA COM session using a private one-shot request file. It
checks session/document/PID identity and never uses ROT or starts another SW
instance. Production protocol operations, schemas and installed sources are
unchanged; no raw-COM endpoint is added. The subsequent equation protection
assertions still use the public installed daemon operations. The old ROT helper
remains available for independent fixture diagnostics, not the CI path.
The Windows CI installer explicitly selects the official Toolbox program,
data and English-resource feature chains alongside the core features. It requires
the installation medium's `Toolbox/ToolboxUpdates.zip`, keeps `INSTALLLEVEL=100`
and does not select all add-ins. MSI success alone still does not prove Toolbox
deployment: the shared inventory/read-only native gate must pass afterwards.

## Development validation

During implementation, run the directly affected tests and the relevant shared
dependency/contract tests first. Do not repeat the entire suite or reinstall
SOLIDWORKS for every small edit. For example, the internal entity increment uses
the entity/reference/registry cases, native trace tests and the shared feature
snapshot tests. Keep tests sensitive to the original failure; faster execution
must not mean weaker geometry/state assertions or retrying a native failure.

Slow native or packaging checks may run in a background agent while development
continues elsewhere. Give each check an exact commit/source hash, an independent
environment/evidence directory and exclusive ownership of its test host. Do
not let two agents manipulate the same SW/daemon or install into one shared
Python environment concurrently. Preserve user-owned processes/documents and
the first failure record.

Full suite, isolated distribution checks and installed cross-host native gates
remain integration/release requirements. Batch related validated commits before
pushing an integration checkpoint; do not manually rerun the full gate for each
commit. A green targeted test or local COM probe is not a replacement for a
formal Windows/Wine delivery pass or publication receipt.

## Calling the gates

Prepare a disposable, connected daemon with no native documents open. Use a
new output directory for each run. Do not restart between gates or retry native
failures: that can hide process-state contamination. The scripts never install,
start, stop or restart SOLIDWORKS. Cleanup closes only their own documents and
retains cleanup errors; it does not turn a failed gate into success.

Both gates explicitly acquire/renew ten-minute leases for bounded observation
groups. Every holder write renews first, including
expected-rejection checks and cleanup closes. This does not extend command/CI
deadlines or change the daemon's 60-second default. An expired lease still fails;
neither gate silently reacquires it or retries the native operation. The driving
gate renews before both protocol writes and its installed-CLI writes; contender
and read-only observation requests retain their original lease-free contexts.

On Windows, use the Python environment with the current SWCLI installed:

```powershell
python -I scripts/ci/verify-modeling.py --output-dir C:\Workspace\proof\modeling
python -I scripts/ci/verify-driving-dimensions.py --output-dir C:\Workspace\proof\driving --after-modeling C:\Workspace\proof\modeling\modeling.json
```

Linux/macOS callers run the test scripts with native Python, provide the local
absolute CLI executable via `--cli-command`, and separately supply the
daemon-visible Windows directory via `--host-output-dir`. For example:

```sh
python3 scripts/ci/verify-modeling.py \
  --output-dir /ci-proof/modeling \
  --host-output-dir 'C:\ci-proof\modeling' \
  --cli-command /usr/local/bin/sw-cli \
  --endpoint 127.0.0.1:18495
```

The host wrapper must obtain that path from its actual Wine mappings, never
assume `Z:` exists, and ensure both paths identify the same writable directory.
The default CLI is isolated installed Python (`python -I -m swcli`), not an
old global executable. `SWCLI_ENDPOINT` is the default endpoint when set.

Both scripts accept `--request-timeout` in seconds: a finite positive number,
at most 3600, with an unchanged default of 120. Slower hosts can pass
`--request-timeout 300` to both gates. The same configured budget is forwarded
to the CLI and to the driving gate's direct daemon calls; each CLI subprocess
gets an additional 15 seconds to return its result. Existing shorter CLI health
probe limits remain unchanged. This does not extend the host wrapper's overall
phase deadline, lease TTL or introduce retries.

The modeling gate also accepts `--depth-request-timeout` (default **600**,
same finite-positive/3600-second bounds) for guarded depth writes and equal-depth
checks. Complete profile/scope/state verification is more expensive than an
export; an instrumented Windows ARM64 native write took 134 seconds. Other
operations still use `--request-timeout` (default 120). Each modeling event
records the actual request budget; the CLI process gets 15 extra seconds.
Host projects must budget the overall modeling phase for these additional
operations, independently of the six export artifacts' short deadline.

Pass the successful local `modeling.json` to the driving script using
`--after-modeling`. It rejects failed/interrupted records, missing native cut
continuation proof and any host PID change between the two gates **before**
creating a driving fixture. The driving gate also verifies the host PID at its
end. Both CI wrappers use this linkage; standalone dimension investigations
may omit the flag but are not evidence of the full consecutive sequence.

The default gate also generates a 40 × 30 × 10 mm solid PRT and a new one-part
ASM using public `document create --type assembly` and `assembly add-component`.
It checks strict native SaveAs/Save3, actual sizes, clean writable/read-only
reopens, fresh IDs and unchanged configuration/feature signatures and hashes.
No official-sample modified-state exception applies to this generated model.
See [native assembly save boundaries](design/assembly-native-save.md).

The saved PRT and ASM each strictly export STL, 3MF, AMF and GLB in that same
daemon/SOLIDWORKS instance. Eight `model_exports` receipts record artifact
metadata, bounded container/basic-geometry checks, unchanged source state and
native-file hashes. Outputs stay in the modeling evidence directory, not the
six formal DockerSW delivery artifacts. A missing translator, invalid output,
source change or failure blocks the gate; no retry/restart or alternate format
substitution is allowed. Passing these checks is not proof of watertightness,
tessellation accuracy or material fidelity.

Supply `--sample-part` and `--sample-assembly` together, both as absolute
daemon-visible Windows/UNC paths, to add installed-sample update-stamp, lease
export and multi-document foreground-restoration checks. They are opened
read-only and never saved. Without them, that named case is absent from the
record rather than claimed as verified. All core modeling cases use generated
parts and do not depend on installed sample locations or localized names.

## Evidence and proof boundaries

### Toolbox policy and paths

See the [first Windows/Linux runtime receipt](verification/toolbox-2026-10-10.md)
for exact tested script versions and the still-separate hosted proof boundary.

Windows resolves the actual `Toolbox Data Location` from the current-user then
machine registry; Wine hosts supply `--wine-prefix` and the script resolves that
same setting through the prefix's real drive mappings. No year, drive letter,
installation location, standard count or part count is hardcoded. Ambiguous
locations fail instead of choosing a version arbitrarily. UNC/external setups
may supply a paired `--data-dir LOCAL --host-data-dir WINDOWS_OR_UNC` explicitly.

```sh
python scripts/ci/verify-toolbox.py --output-dir /ci-smoke/toolbox \
  --wine-prefix /root/.wine --require-toolbox \
  --cli-command /usr/local/bin/sw-cli --request-timeout 120
```

`--require-toolbox` makes an unconfigured library a failure. Without it, only an
unconfigured library is a named `skipped` result (`completed: false`); a configured
but incomplete library still fails. `--inventory-only` performs no CLI/COM calls:
it may pass file checks while reporting `native_test: not-run`. It is diagnostic
evidence, not the full runtime delivery gate. The default CLI uses the caller's
installed Python; a Wine wrapper must pass its native client executable.

`toolbox.json` exclusively reserves evidence before actions, atomically
checkpoints raw CLI results including request metadata, retains the first error
and separate cleanup errors, and reports the selected standard's model counts
and source checksums. It does not parse/deserialize the proprietary binary index,
load SwToolbox/SwBrowser, select specifications, generate configurations or insert
components into assemblies. Those require future explicit product operations.
The original updater exit code is recorded as unavailable (`null`): do not infer
it from MSI success or file presence. Hosts must independently check/log any
updater they actually invoke. Installer logs may contain private inputs and must
not be copied wholesale into public gate evidence.

`modeling.json` records stage, command, exit status, stdout/stderr, actual host
PID, successful cases and cleanup errors. `driving-dimensions.json` retains the
dimension protocol/CLI events and native verification. Both exclusively reserve
their records before host operations and checkpoint complete JSON atomically,
so an externally killed script leaves an honest `running` record. Existing
records and native artifacts are not overwritten on repeated runs.
Both records include `request_timeout_seconds` (configured per-request budget)
and `cli_process_timeout_seconds` (that budget plus the 15-second process margin).
The modeling record additionally includes `depth_request_timeout_seconds` and
each event's actual `request_timeout_seconds`; a longer depth budget must not be
mistaken for a global extension or a retry policy.

Portable fake-CLI tests validate the test control flow, exact CLI syntax,
failure reporting and evidence. Only successful execution on actual Windows,
Linux/Wine or macOS/Wine establishes that host's native CAD proof. Build/package
success alone does not establish installation, COM activation or modeling.
