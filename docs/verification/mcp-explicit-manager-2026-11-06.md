# Explicit MCP lifecycle and host launcher verification — 2026-11-06

This supersedes the lazy-start policy in the earlier prototype receipt, without
rewriting its historical evidence. It is local development validation, not the
complete SOLIDWORKS matrix or a new published 0.1.0a16 artifact.

The adapter exposes five tools: read-only status, explicit daemon start/stop,
live capabilities and typed execution. Both CLI and MCP use the same manager;
`daemon status --details --json` adds a runtime snapshot while basic health
remains compatible. Unknown process origin is not inferred from visibility,
and unavailable inventory is not reported as an empty list. An old daemon's
startup visibility is explicitly distinguished from current window observation.

Launcher configuration selects the explicit absolute path before the environment
variable, then native Windows fallback. POSIX clients need the host's launcher;
Wine/Python/prefix discovery is not performed in SWCLI. Delegated Windows calls
cannot recurse into the host wrapper. POSIX launch sessions and the tested
same-user Windows task broker keep resident hosts outside MCP teardown.

## Original Windows evidence

The official MCP 1.30.0 SDK launched the isolated installed candidate on native
Windows with SOLIDWORKS 2025 SP5 (33.5.0). Before/after process inventories were
empty. Initialization, discovery, offline status and refused offline capability
queries created no SW. One explicit start created hidden, daemon-owned PID 6756
(native readiness wait 5.436 seconds). Current top-level-window observations
confirmed hidden state; a second start with visible requested reused that host
without changing visibility.

The public execute tool created one test-owned unsaved part. Explicit stop
returned `ActiveDocument` and left the same host connected. Closing only that
fixture allowed further work. Disconnecting the SDK left the same daemon/SW
running, and CLI detailed status reported the same PID. A new MCP connection
explicitly stopped it, remained responsive to ping, and final SW inventory was
empty. No failed native operation was retried. Raw receipt and stderr/daemon
logs remain in `C:\Workspace\SWCLI-mcp-20261106\explicit-manager` and the local
`/private/tmp/swcli-mcp-explicit-proof` copy; their hashes are in the
[verification receipt](mcp-explicit-manager-2026-11-06.json).

## Portable and package checks

- 1595 tests: 1574 passed, 21 Windows-only checks skipped on macOS; includes
  official SDK stdio lifecycle/progress and two-client isolation tests.
- Priority, literal argv/no shell, delegation, missing/invalid launchers,
  remote-start refusal, unknown transport outcomes, no status-triggered startup,
  legacy health fallback, ownership and window observation boundaries passed.
- Private wheel's 72 package/resource files match the tested source byte for
  byte. Strict Twine, sdist contents, isolated installed CLI/schema/skill resource
  checks and `pip check` passed. Existing release assets were not replaced.
- Skills now describe explicit startup, startup latency, host selection,
  structured results and shared-endpoint shutdown guards. Skill validation passed.

DockerSW/MacSW wrapper routing is separately verified with fake runtimes; this
is not evidence of native Wine activation or App deployment. The visible-user-SW
plus independent hidden-instance guard remains in place. Tray UI remains planned.
