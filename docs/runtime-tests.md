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
- `scripts/ci/verify-driving-dimensions.py`: three-plane driving diameter
  creation, inspect/edit, guards, native save/reopen and discovery of fresh
  sketch/dimension handles. Run it after modeling on the same ready daemon.
- `scripts/ci/verify-invalid-requests.py`: invalid wire requests must leave
  the host and documents unchanged.

Windows-only startup/attach/disconnect behavior remains in
`scripts/ci/windows/smoke-solidworks.ps1`; its equation fixture deliberately
uses native setup and is not presented as a cross-platform public CLI test.
Installer and Wine lifecycle checks belong to their respective host projects.
The six DockerSW published export artifacts remain a separate delivery gate.

## Calling the gates

Prepare a disposable, connected daemon with no native documents open. Use a
new output directory for each run. Do not restart between gates or retry native
failures: that can hide process-state contamination. The scripts never install,
start, stop or restart SOLIDWORKS. Cleanup closes only their own documents and
retains cleanup errors; it does not turn a failed gate into success.

Both gates explicitly acquire/renew ten-minute leases, covering each CI
phase and bounded observation groups. Every holder write renews first, including
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

Portable fake-CLI tests validate the test control flow, exact CLI syntax,
failure reporting and evidence. Only successful execution on actual Windows,
Linux/Wine or macOS/Wine establishes that host's native CAD proof. Build/package
success alone does not establish installation, COM activation or modeling.
