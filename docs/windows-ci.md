# Windows CI design

SWCLI separates portable checks from tests that require a real native
SOLIDWORKS installation.

## Hosted CI

`.github/workflows/ci.yml` is the single hosted workflow. Its first stage runs
the unit suite on Windows 2025 with Python 3.9 and 3.14, parses every Windows CI
PowerShell script, verifies the installed CLI and protocol schemas, and builds
and checks both distributions on Linux. The Linux package job installs the
actual wheel and verifies the isolated CLI, all request/result Schemas and
packaged product skill/guide; Windows checks the same resources in the installed
checkout. These jobs do not activate COM, run Wine or require
SOLIDWORKS and are safe for pull requests.

The second stage depends on both unit tests and package validation. It runs the
native SOLIDWORKS E2E only for trusted `main` pushes or an explicit manual run;
any first-stage failure prevents the expensive installation and real export
job from starting. Wine execution remains the responsibility of integration
projects such as DockerSW and MacSW because their patched runtimes define
whether SOLIDWORKS is usable under Wine.

The earlier standalone installation-media probe has been retired after its
mounting path was incorporated into the E2E job. The unified workflow records
disk capacity and actual rclone VFS cache size, mounts Google Drive through
rclone and WinFsp, and uses ImDisk's `devio` shared-memory proxy to expose the
streamed ISO as a read-only virtual optical drive. Windows' `Mount-DiskImage`
cannot attach an ISO through a WinFsp-backed path on the hosted runner, and
WinCDEmu 4.1 cannot complete its unattended driver install on Windows Server
2025. With ImDisk, the user-mode `devio` process owns the remote file handle
while the kernel driver receives block reads through shared memory. The
official standalone `devio.exe` URL and SHA-256 are pinned. The optical volume
is detached before `devio` and rclone are stopped.

Required repository secret:

- `RCLONE_CONFIG_B64`: base64-encoded rclone configuration containing a
  `gdrive:` remote. The decoded file exists only for the duration of the job.

## Disposable hosted installation smoke

The host wrapper calls `scripts/ci/verify-modeling.py` first and
`scripts/ci/verify-driving-dimensions.py --after-modeling .../modeling.json`
second, without restarting the daemon/SOLIDWORKS. The shared modeling gate
requires a successful fresh background sketch after a native nonintersecting
cut rejection, no cleanup warnings, a closed edit and unchanged solid volume.
The driving gate refuses a replaced host or failed/incomplete predecessor.
The same visible/hidden host also runs `scripts/ci/verify-toolbox.py
--require-toolbox`: actual configured library inventory plus public read-only
standard-part open/diagnose/measure/close. It does not load the Toolbox add-ins
or replace the installer's responsibility to check actual deployment exit codes.

See [shared runtime tests](runtime-tests.md) for the portable entry points,
host/local path namespaces and evidence. These common assertions are no longer
duplicated in the Windows PowerShell host wrapper; equation setup, desktop
diagnostics and owned/attached host lifecycle checks remain Windows-specific.
The a7 shared gate also requires guarded boss/cut depth edits,
equal-depth lifecycle checks, independent volume and native save/reopen proof,
and read-only refusal before selection access. Its depth requests have a
separate 600-second budget; the remaining request budgets are unchanged.

The hosted installation is performed once. Its smoke wrapper runs first in the
default visible test mode, then again with `-Hidden` and a separate `hidden/`
evidence directory. Both modes use the same public gates and lifecycle checks;
there is no restart between modeling and driving within either mode. A fresh
host between these two independent mode runs is not native-failure recovery.
The hidden run is mandatory: visible-only success did not expose the rejected
cut's residual native command state. See the
[matched investigation](verification/linux-wine-rejected-cut-2026-10-08.md).
The Windows-only equation fixture remains mandatory in the visible run: its
native setup uses `GetActiveObject` to attach the exact existing ROT host, and
the hidden background host in the matched VM does not expose that entry. The
hidden run neither substitutes Dispatch nor changes visibility to bootstrap
this fixture. It still runs all public modeling/driving guards and lifecycle
checks; it does not claim separate hidden-mode native equation-fixture proof.

The second stage of `.github/workflows/ci.yml` is an integration test, not a
release pipeline or a declaration that Windows Server is an officially
supported SOLIDWORKS workstation. It mirrors the proven DockerSW order where
it also applies to native Windows:

1. stream the complete official ISO and expose it through ImDisk as a read-only
   optical volume, without selectively extracting an assumed dependency set;
2. install the official x64 VBA 7.1 engine (`prereqs\VBA\vba71.msi`) and its
   required English resources (`vba71_1033.msi`), then Login Manager; preserve
   their complete media directories, including external CAB payloads;
3. import `sw2025_network_serials_licensing.reg` immediately before the main
   core MSI performs AppSearch, explicitly targeting
   `C:\Program Files\SOLIDWORKS`; Login Manager keeps its own
   `Common Files\SOLIDWORKS Shared` layout;
4. apply the private test-only program overlay;
5. start the private FlexNet server and wait for `lmutil lmstat` to succeed;
6. install the current checkout; its platform marker installs pywin32 on
   Windows automatically;
7. start the resident daemon with `sw-cli daemon serve`, capture desktop/window
   diagnostics around first startup, then use typed CLI requests against its
   single COM worker for a real model, structural inspection, diagnosis,
   deterministic render, and verified STEP export;
8. verify capabilities, document list/use/rebuild/save, lease acquire/status/
   renew/release and saved-document reopening, with worker-side result Schema
   validation enabled for every typed operation; send malformed wire requests
   and require unchanged host PID/documents; reject invalid restart waits
   without stopping or replacing the connected SOLIDWORKS PID; create distinct unsaved parts
   and make three verified rectangle sketches on a background part, checking
   lease/stale-stamp rejection, sketch IDs, closed edit state and restoration of
   the foreground/current document; extrude all three sketches with native
   depth/direction/merge checks, verify the first body dimensions, and reject
   reuse of an absorbed sketch; create full circles on all three background
   origin planes, verify native radius/center and extrude them as separate
   bodies; observe a leased background part from another session and require
   the initial 100×50×20 body to measure 100000 mm³, 16000 mm² and the expected
   centroid; cut a radius-4 circle through that body and compare removed volume
   and final surface area to the analytic hole geometry; observe the leased
   background circle from a read-only session before and after absorption,
   checking native geometry/state and exact cut owner without changing foreground;
   use a separate reversed
   boss/cut part to verify the CLI's common sketch-normal direction convention;
   reject reuse of absorbed cut profiles and verify that a nonintersecting
   profile returns `CutExtrusionFailed` without changing the measured solid;
   save the generic modeled part under a new
   native filename, verify unchanged document/lease/sketch identities and
   rejection of an existing target without changing its hash, then close and
   reopen under an independent session to verify body count, volume, surface
   area and diagnostics;
9. run the public four-hole plate example using only typed CLI commands in a
   Unicode output directory while forcing the caller's legacy CP936 encoding,
   require the example to restore that encoding, verify
   analytic volume/area, native save/reopen, strict STEP export and BMP preview,
   and retain these additional generated artifacts under `plate-example`;
10. close the model, externally terminate the daemon-owned SOLIDWORKS process,
   and require health to report `host_connected: false`, clear the stale host,
   and retain `HostDisconnected` without silently restarting on a business
   request;
11. require graceful daemon shutdown to succeed with the host already absent,
   reject `--attach-existing` when no host exists without creating SOLIDWORKS,
   then launch a visible host from a separate COM fixture and explicitly attach.
   Verify that daemon
   stop preserves that host's process, ownership and visibility; attach again,
   terminate only this fixture host, and require the same truthful disconnected
   state, blocked business request and graceful stop as for an owned host;
12. allow ten seconds of elapsed wall time for idle disconnect detection,
   including CLI/status subprocess overhead rather than counting polling sleeps;
   then upload the generated native part, render, export, JSON responses, and
   desktop/window diagnostics as evidence.

The external-host fixture uses `DispatchEx` from an independent Python STA
process, with no SWCLI import or daemon connection. It sets the foreground
`UserControl`/`Visible` properties and waits for native startup completion, then
exits. The PowerShell gate requires that exact visible SOLIDWORKS PID to survive
the fixture process exit before attaching swclid. This tests external-instance
ownership, not whether a human's first double-click startup is fully configured.
It does not change any add-in or license registry setting, click a dialog or
accept terms. Startup failure retains desktop diagnostics and fails the gate.

The previous direct-EXE fixture was replaced: a fresh interactive launch on the
hosted runner displayed the SOLIDWORKS License Agreement even though its
COM-created host had already completed modeling/export. That historical failure
is retained in the [a4 verification record](verification/a4-2026-10-07.md).
The new fixture does not claim to resolve that first-use GUI prerequisite or
prove every interactive startup path. Product attach mode remains unchanged.

The Wine `win32u.so` and Wine-Mono patches from DockerSW are intentionally not
used on native Windows. Only SWCLI-created model/export evidence and disk/cache
measurements are uploaded. The workflow never uploads official installation
media, installed SOLIDWORKS files, private overlays, registry files, FlexNet
files, or license-server logs. On failure, the MSI verbose logs are uploaded
for 14 days before cleanup, matching DockerSW's diagnostic boundary; those logs
can contain installer properties and are therefore treated as private CI
evidence. Desktop screenshots and visible-window metadata from the first-start
smoke are retained with the SWCLI-generated evidence so modal startup failures
remain diagnosable when COM never becomes ready. All other private inputs and
the rclone credential are removed in an unconditional cleanup step; the hosted
VM is then discarded by GitHub.

The [official 2025 installation guide](https://files.solidworks.com/Supportfiles/SW_Installation_Guide/2025/English/install_guide.pdf)
(pages 36–39) requires both x64 VBA packages for every language. Additional
language packages are unnecessary for this English runner. These prerequisites
are installed automatically by SOLIDWORKS Installation Manager, but this CI
uses the core MSI directly and must install them explicitly. VSTA is a separate
optional component, not a substitute for VBA. No historical VBA repair patch
is added to this installation path.

The official VBA prerequisite helper writes `vba-runtime.json` into
the public smoke-evidence directory, even when a VBA installer fails. It records
only VBA product names/versions/Installer product keys and the existence/version
of the native `VBE7.DLL` and English `VBE7INTL.DLL`. Registry inspection does not
use `Win32_Product`, which can trigger MSI repair, and never exports licensing
properties. An incomplete registry read is explicitly marked. Inventory write
failure cannot replace the original installation failure; with no original
failure it fails the installation step. The inventory proves neither successful
VBA initialization inside SOLIDWORKS nor equation evaluation: those still need
real execution evidence. If either required DLL remains absent after successful
MSI calls, the installation step fails; an earlier
installer failure always keeps its original error. The [official installation FAQ](https://www.solidworks.com/support/frequently-asked-questions?page=1&term_id=417)
connects failed VBA initialization to unavailable equations/macros, but does not
establish that every `EquationMgr.Add2` failure has this cause.

## Installation cache boundary

SOLIDWORKS installation snapshot restore/save is temporarily disabled. Every
hosted run performs runner cleanup, streams the ISO, and installs the official
VBA engine, VBA language package, Login Manager and core MSI before applying the
private test overlay. The normal modeling, equation, lifecycle and export gates
remain mandatory; Python package caching is unrelated and remains enabled.

[Run 37596644263](https://github.com/YJBeetle/SWCLI/actions/runs/37596644263)
passed with a full fresh installation. The next
[cache-hit run 37599969164](https://github.com/YJBeetle/SWCLI/actions/runs/37599969164)
passed the three-plane driving-dimension gate but rejected the unchanged native
equation fixture (`Add2 = -1`, equation count remained zero). Both runs recorded
the same VBA product and DLL versions; the cache-hit VBA and Login Manager MSI
logs reported success. This establishes a behavior difference, not its cause:
DLL presence does not prove successful VBA initialization inside SOLIDWORKS.

The retained export/restore scripts use manifest format 2 and preserve program
files plus selected SW configuration and application COM keys. They reinstall
the official VBA and Login Manager media, but do not recreate the complete
native core installation or prove parity of its registration state. The hosted
workflow no longer calls these scripts. Snapshot caching must remain disabled
until fresh-runner restoration proves native core/VBA integration and passes
the same real gates. Broad registry imports and fabricated Windows Installer
product/component registration are not a substitute for that proof.
