# Shared real-runtime tests

SWCLI owns the CAD test operations and assertions. Its Windows CI prepares a
native SOLIDWORKS host; DockerSW prepares Linux/Wine; MacSW is responsible for
macOS/Wine provisioning. The two integration projects call the same scripts,
not copies of the modeling assertions. These are CI tools delivered in the
source checkout/sdist, not installed `sw-cli` subcommands or a mock backend.

## Entry points

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

Windows-only startup/attach/disconnect behavior remains in
`scripts/ci/windows/smoke-solidworks.ps1`; its equation fixture deliberately
uses native setup and is not presented as a cross-platform public CLI test.
Installer and Wine lifecycle checks belong to their respective host projects.
The six DockerSW published export artifacts remain a separate delivery gate.
Windows hosted CI runs that same wrapper in visible and `-Hidden` modes using
one installation and independent evidence directories. Modeling and driving
share one unchanged native PID within each mode; passing visible mode is not
proof of hidden/background behavior.
The Windows-only equation setup attaches through ROT and is required in the
visible run only. Its hidden-host ROT limitation does not make the public
modeling/driving gates optional and is not resolved by starting another host.

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

Supply `--sample-part` and `--sample-assembly` together, both as absolute
daemon-visible Windows/UNC paths, to add installed-sample update-stamp, lease
export and multi-document foreground-restoration checks. They are opened
read-only and never saved. Without them, that named case is absent from the
record rather than claimed as verified. All core modeling cases use generated
parts and do not depend on installed sample locations or localized names.

## Evidence and proof boundaries

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
