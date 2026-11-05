# Daemon utilities contract — 2026-11-06

This finalizes the host boundary after the [explicit MCP lifecycle validation](mcp-explicit-manager-2026-11-06.md).
`SWCLI_DAEMON_UTILS` or global `--daemon-utils PATH` selects a trusted absolute
executable path. With no configured utilities, native Windows uses its built-in
launcher; POSIX reports a configuration error. This remains explicit startup.
The earlier development `SWCLI_HOST_LAUNCHER`/`--host-launcher` names and wrapper
re-entry contract are superseded before an MCP release.

The public DockerSW/MacSW `sw-cli` wrappers configure native client Python,
endpoint, path mapping and the utilities path, then forward every argument.
Python parses global/subcommand options once. The separate shell utilities
receive an explicit `start`, `serve`, `restart` or `doctor` action and execute
the actual host Windows Python through Wine. There is no second manager service,
protocol, state file or command-string evaluation. `SWCLI_DAEMON_UTILS_ACTIVE`
marks the backend hop to prevent recursion. Status and stop remain native
protocol calls and do not enter Wine merely to manage an existing endpoint.
The existing COM-instance guard and explicit attach/ownership rules are retained.

## Checks

- Final full portable suite: **1598 tests, 1577 passed, 21 platform skips**.
- MacSW's checksum-verified standalone Python 3.11: official SDK/MCP tests
  **16 passed**, manager tests **19 passed**. These test protocol transport and
  shell routing, not native Wine SOLIDWORKS activation.
- DockerSW: **33 tests passed** after replacing obsolete shell-interception
  checks with native forwarding and explicit utilities action checks. Linux
  Python 3.10 SDK dependency wheels resolved for the image's target platform.
- MacSW: fake-runtime shell tests passed for all public commands, leading
  global options, App/symlink paths, Wine preparation failure propagation,
  backend action routing and literal argument preservation. Related SWCLI
  packaging/runtime tests **31 passed** and AI contract tests **6 passed**.
- Private final candidate wheel: SHA-256 `8418853cecc8306bc0ace9e24b17092faa09f3ccaf0a3c5ab96cda8f66feedcf`.
  Its 72 package/resource files match source byte for byte. Strict Twine,
  sdist and isolated installed CLI/schema/skills verification passed.
- The earlier Windows original receipt remains evidence for native explicit
  lifecycle, hidden ownership, open-document shutdown refusal, disconnect
  retention and explicit final shutdown. All 55 packaged MCP/native backend,
  broker and runtime-observation files compared here are unchanged. Its
  candidate and receipt hashes are retained separately; this does not claim a
  new full CAD matrix or replace the released a16 assets.

MacSW bundles SDK dependencies only in native Python, using its existing
checksum-locked offline wheel manifest. The real packaging helper was executed
against a temporary fixture with those exact wheels; imports succeeded with
its actual Python 3.11, and the Windows packages contained no MCP SDK. App
build/install, native Wine activation and MacSW CI are outside this receipt.

## Windows CI assertion follow-up

[Push run 42114428267](https://github.com/YJBeetle/SWCLI/actions/runs/42114428267)
failed in the same unit assertion on Windows Python 3.9 and 3.14. The test
incorrectly expected a new POSIX session for every restart, including Windows;
the implementation correctly uses that flag only on POSIX. The test now covers
explicit Windows/macOS/Linux serve and restart expectations (six subcases),
retaining literal argv, visibility/attach forwarding and no-shell assertions.
No runtime code or native startup policy changed.

The manager suite passed 19 tests and the full local macOS/Python 3.14 suite
passed 1598 tests with 21 platform skips. No Windows VM was used for this fix;
Windows CI remains the separate native-platform result. Original failed-job
log SHA-256: `cfef278944540cc404baeee253c2d898ee3bbf6be53c8921c0524117964be94b`.
