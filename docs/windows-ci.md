# Windows CI design

SWCLI separates portable checks from tests that require a real native
SOLIDWORKS installation.

## Hosted CI

`.github/workflows/ci.yml` runs the unit suite on Windows and builds the wheel
on Linux. These jobs do not run Wine or require SOLIDWORKS and are safe for
pull requests. Wine execution is intentionally left to integration projects
such as DockerSW and MacSW because their patched runtimes define whether
SOLIDWORKS is usable, not the host operating system alone.

`.github/workflows/windows-hosted-media-probe.yml` is a manual feasibility
probe for disposable GitHub-hosted Windows runners. It can remove optional
preinstalled SDK payloads, mounts Google Drive through rclone and WinFsp, then
uses ImDisk's `devio` shared-memory proxy to expose the streamed ISO as a
read-only virtual optical drive. It deliberately does not install or execute
SOLIDWORKS, so media/cache and virtual-driver failures remain separate from
installer and COM failures.

The probe records disk capacity before cleanup, after cleanup, and after the
ISO access. It also records the actual rclone VFS cache size. Windows'
`Mount-DiskImage` cannot attach an ISO through a WinFsp-backed path on the
hosted runner, and WinCDEmu 4.1 cannot complete its unattended driver install on
Windows Server 2025. With ImDisk, the user-mode `devio` process owns the remote
file handle while the kernel driver receives block reads through shared memory.
The official standalone `devio.exe` URL and SHA-256 are pinned. The optical
volume is detached before `devio` and rclone are stopped.

Required repository secret:

- `RCLONE_CONFIG_B64`: base64-encoded rclone configuration containing a
  `gdrive:` remote. The decoded file exists only for the duration of the job.

## Disposable hosted installation smoke

`.github/workflows/windows-hosted-solidworks.yml` is a manual integration test,
not a release pipeline or a declaration that Windows Server is an officially
supported SOLIDWORKS workstation. It mirrors the proven DockerSW order where it
also applies to native Windows:

1. stream the official ISO and selectively extract the required installer
   directories;
2. install the VC++ prerequisite, Login Manager, and core MSI;
3. import `sw2025_network_serials_licensing.reg` immediately before the main
   MSI performs AppSearch;
4. apply the private test-only program overlay;
5. start the private FlexNet server and wait for `lmutil lmstat` to succeed;
6. use the current SWCLI checkout for a real model, render, and STEP export.

The Wine `win32u.so` and Wine-Mono patches from DockerSW are intentionally not
used on native Windows. Only SWCLI-created model/export evidence and disk/cache
measurements are uploaded. The workflow never uploads official installation
media, installed SOLIDWORKS files, private overlays, registry files, FlexNet
files, or installer/license logs. All private inputs and the rclone credential
are removed in an unconditional cleanup step; the hosted VM is then discarded
by GitHub.

## Native SOLIDWORKS E2E

`.github/workflows/windows-solidworks.yml` targets a self-hosted runner with
these labels:

```text
self-hosted, windows, x64, solidworks-2025
```

The runner must be started interactively by a dedicated logged-in user, not as
a Windows service in Session 0. The smoke test discovers the registered
SOLIDWORKS installation, waits for complete startup, creates and verifies a
100 x 50 x 20 mm box, renders an 800 x 600 isometric BMP, exports STEP, closes
the document, and exits SOLIDWORKS. JSON results and artifacts are retained for
14 days.

Because SWCLI is public, this runner workflow is manual-only initially. Do not
enable it for fork pull requests. After the runner is isolated and proven, it
can be enabled for protected `main` pushes, scheduled runs, and releases.

## Installation cache boundary

Do not store an installed SOLIDWORKS tree in `actions/cache`. A working native
installation includes registry state, COM registration, shared components,
services, and licensing state in addition to files. Preserve it with the
self-hosted runner disk or a Parallels golden snapshot. The ISO may remain on
Google Drive: rclone VFS caching can fetch only the ranges read by the selected
MSI features while bounding local cache usage.
