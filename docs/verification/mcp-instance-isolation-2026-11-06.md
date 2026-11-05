# MCP and independent SOLIDWORKS instance diagnostics — 2026-11-06

This is local development evidence, not a complete native acceptance or a
release receipt. MCP uses stdio over the existing daemon protocol; no HTTP
listener, COM worker, native timeout, lease/CAS or CAD handler change is needed.
Independent default host startup remains disabled when an existing registered
SOLIDWORKS instance is found. The existing explicit attach mode is retained.

## Native Windows 2025 SP5.0

The Parallels Windows guest had no SLDWORKS processes before the test. All
fixtures/reports are under `C:\Workspace\SWCLI-tests`. The visible reference
instance was launched through the installed executable, not through swclid.

- `multi-instance-win-20261106` stopped in OS harness setup because
  `win32process.WaitForInputIdle` was unavailable. It never attempted COM
  activation. The harness was corrected to use `user32.WaitForInputIdle`.
- `multi-instance-win-20261106-fixed`: visible PID **3052**, revision **33.5.0**,
  one clean unsaved part (`零件1`, update stamp 140). A single `DispatchEx`
  returned the **same PID 3052**. The probe refused to set visibility, claim
  ownership or exit this returned second reference. This rules out simply
  removing the existing-instance guard around DispatchEx.
- `multi-instance-win-rot-20261106` stopped during reference-window setup;
  the executable-created host had not become visible. No second process was
  created. The fixture setup was corrected to explicitly show only its own
  reference instance with user control enabled.
- `multi-instance-win-rot-visible-20261106`: visible PID **5956** and its clean
  reference part. Starting another executable produced PID **9956**. ROT had
  `SolidWorks_PID_5956` and `SolidWorks_PID_9956`, and exact PID binding returned
  **9956**. Background mode and hiding succeeded, but
  `StartupProcessCompleted` never became true within the existing **300 s**
  startup wait. No hidden-model operation or persistence claim was made.
  The reason for the incomplete second startup remains unresolved.

All native failures stop the diagnostic; there is no activation retry or
rollback. Cleanup targets only the probe-owned, identity-checked hosts. The
final report has no cleanup exceptions, and a separate process check found
no SLDWORKS process after the probes. This proves distinct process/ROT binding
is possible, but does **not** prove the requested hidden instance is usable
or safe enough to enable by default.

## DockerSW Wine 11.16

Used cached `2025-zh-cn-cli` image ID
`sha256:43d63bd2b336152fabd32b86703ecce644704bd284ae32d0e28b8e5ac1f1c7af`
in dedicated temporary NAS containers, without user-directory mounts or
published ports. No MacSW app/container or existing Docker service was used.
The runtime reported Wine **11.16** and Wine-Mono **11.3.0**.

The first container used `--network none`; its internal FlexNet startup failed
with `Unknown Hostname` before native diagnosis. After this infrastructure
cause was identified, a new isolated container with normal internal networking
and no published ports reached license-server readiness.

The executable-created visible-reference PID was **556**. Its first
`GetActiveObject` failed with **MK_E_UNAVAILABLE**. Read-only OS/ROT inspection
then found `SolidWorks_PID_556` together with a visible
**SOLIDWORKS 许可协议** dialog and splash screen. The reference application was
not ready; no terms were accepted, no failed GetActiveObject was retried, and
no second-host activation or success conclusion was claimed. Wine independent
instance behavior remains **unverified**, rather than proven unsupported.

Raw reports/trace/window inventory are archived under the local evidence root
and copied to the Windows workspace. Both temporary containers were removed
after collection. Images and existing containers were kept.

## Consequence for MCP

MCP may lazily start a local daemon when none is reachable, using the existing
lifecycle checks. An existing visible user instance still needs explicit
`sw-cli daemon start --attach-existing`. It must not silently reuse a visible
instance as if it were a new hidden owned host. Finishing process/ROT startup
and verifying document isolation plus owned-only exit on both hosts are needed
before changing that default.

The adjacent JSON records hashes of the original local diagnostic files;
it does not substitute for a successful native acceptance or release.
