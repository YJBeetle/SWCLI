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
mounts the SOLIDWORKS ISO and reads the core MSI. It deliberately does not
install or execute SOLIDWORKS: the standard hosted image is Windows Server and
does not provide a supported, persistent interactive desktop environment for
the SOLIDWORKS client.

The probe records disk capacity before cleanup, after cleanup, and after the
ISO access. It also records the actual rclone VFS cache size. This distinguishes
the ISO's logical size from the bytes fetched on demand.

Required repository secret:

- `RCLONE_CONFIG_B64`: base64-encoded rclone configuration containing a
  `gdrive:` remote. The decoded file exists only for the duration of the job.

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
