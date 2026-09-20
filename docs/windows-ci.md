# Windows CI design

SWCLI separates portable checks from tests that require a real native
SOLIDWORKS installation.

## Hosted CI

`.github/workflows/ci.yml` runs the unit suite on Windows 2025 with Python 3.9
and 3.14, parses every Windows CI PowerShell script, verifies the installed CLI
and protocol schemas, and builds and checks both distributions on Linux. These
jobs do not run Wine or require SOLIDWORKS and are safe for pull requests. Wine
execution is intentionally left to integration projects such as DockerSW and
MacSW because their patched runtimes define whether SOLIDWORKS is usable, not
the host operating system alone.

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

`.github/workflows/windows-hosted-solidworks.yml` runs on trusted `main` pushes
and can also be started manually. It is an integration test, not a release
pipeline or a declaration that Windows Server is an officially supported
SOLIDWORKS workstation. It mirrors the proven DockerSW order where it also
applies to native Windows:

1. stream the complete official ISO and expose it through ImDisk as a read-only
   optical volume, without selectively extracting an assumed dependency set;
2. install only the official Login Manager MSI and core MSI, explicitly
   targeting `C:\Program Files\SOLIDWORKS` for the main program; Login Manager
   keeps its own `Common Files\SOLIDWORKS Shared` layout;
3. import `sw2025_network_serials_licensing.reg` immediately before the main
   MSI performs AppSearch;
4. apply the private test-only program overlay;
5. start the private FlexNet server and wait for `lmutil lmstat` to succeed;
6. install the current checkout with its Windows dependency extra;
7. start the resident daemon with `sw-cli daemon serve`, capture desktop/window
   diagnostics around first startup, then use typed CLI requests against its
   single COM worker for a real model, structural inspection, diagnosis,
   deterministic render, and verified STEP export;
8. request graceful daemon shutdown and upload the generated native part,
   render, export, JSON responses, and desktop/window diagnostics as evidence.

The Wine `win32u.so` and Wine-Mono patches from DockerSW are intentionally not
used on native Windows. Only SWCLI-created model/export evidence and disk/cache
measurements are uploaded. The workflow never uploads official installation
media, installed SOLIDWORKS files, private overlays, registry files, FlexNet
files, or license-server logs. On failure, the two MSI verbose logs are uploaded
for 14 days before cleanup, matching DockerSW's diagnostic boundary; those logs
can contain installer properties and are therefore treated as private CI
evidence. Desktop screenshots and visible-window metadata from the first-start
smoke are retained with the SWCLI-generated evidence so modal startup failures
remain diagnosable when COM never becomes ready. All other private inputs and
the rclone credential are removed in an unconditional cleanup step; the hosted
VM is then discarded by GitHub.

## Installation cache boundary

The hosted workflow restores and saves a versioned repository Actions cache.
On a miss, it streams the ISO, installs the two MSI packages, stops Fast Start,
exports the required SOLIDWORKS registry keys, and saves the clean installation
before applying the program overlay. The cache also contains the private test
overlay, FlexNet files, and licensing registry input so an exact hit can skip
rclone, WinFsp, ImDisk, ISO access, and both MSI packages entirely. These
private inputs remain confined to the repository cache: they are never uploaded
as artifacts or published as release contents. The workflow is intentionally
not enabled for pull requests; trusted push and manual runs use GitHub's default
cache-write access.

On a hit, the workflow restores the program and shared directories, template
data, the clean registry snapshot, and the private test inputs. Windows
Installer state cannot be reconstructed safely from copied Login Manager files,
so its small official MSI and its external CAB media are also cached with their
relative layout and silently reapplied; the large core MSI remains skipped.
The workflow also skips the multi-minute aggressive runner cleanup because the
initial free space is sufficient for restoring the approximately 7 GB
installation. Cache restoration is never sufficient evidence on its own: the
same real SWCLI model, render, and export smoke still has to pass before the run
is successful. Installer logs, mounted media, rclone credentials, and generated
smoke outputs remain outside the installation cache.
