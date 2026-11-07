# Product roadmap

Capabilities from the running daemon remain authoritative. Historical increment
plans and their acceptance boundaries are preserved in [roadmap history](roadmap-history.md).
Release details belong in [versioned release notes](releases/).

## SOLIDWORKS version baseline

- Current development and acceptance target **SOLIDWORKS 2025**. Other major
  versions are outside the current workstream: do not add compatibility paths,
  run version-matrix validation, or advertise support for them without a new
  concrete requirement.
- Consider other versions only when there is an explicit user need. An API's
  introduction version does not establish a SWCLI supported-version floor.
- Record the tested service pack and native revision for each release and
  feature. Current new-feature proofs commonly use 2025 SP5 / revision 33.5.0;
  that does not qualify every 2025 service pack or every Windows/Wine host.
- Release notes must identify verified hosts and feature-specific restrictions.
  See [release compatibility declarations](tag-releases.md#compatibility-declarations).

## Implemented tooling

- CLI and MCP share explicit daemon lifecycle management; no implicit SW startup.
- MCP exposes short tool names, schema discovery, bounded image/file attachments
  and optional workspace upload/download tools.
- Windows tray supports status, protected shutdown and hiding the icon; Wine
  defaults to no tray. Background startup and status probes avoid consoles.
- Certificate-verified TLS and token-file authentication protect daemon transport.
  Workspace transfers use bounded chunks, hashes, atomic publication and explicit
  overwrite/resume. Shared tokens are not multi-user authorization.
- The typed Python SDK, published in 0.2.4, is generated from operation schemas
  and preserves sessions, leases, CAS, native refusals and uncertain outcomes.
- Native Windows tag CI gates publication of original packages. DockerSW/MacSW
  validate their own delivery independently.

## Tooling priorities

- Finish 0.2.3 publication independently of the already published 0.2.4.
- Keep ordinary and recovery publication on the same artifact-source checks,
  including publish-only retries. Do not replace successful CAD gates with mocks.
- Keep SDK, MCP and skills aligned when the operation catalog changes.
- Consider batch orchestration with per-item receipts and stop-on-failure.
  This is a future design, not a native transaction or rollback guarantee.
- Independent SW instances remain deferred and low priority because of their
  memory cost and unproven isolation. Existing-host guards remain in place.

## SOLIDWORKS API workstream

Document option coverage (including fonts and drafting standards), stronger
entity/topology references, assembly and drawing editing belong to the separate
native API workstream. Add capabilities only with request/result schemas,
context guards and appropriate real Windows verification.

Editable native models from supported OpenSCAD descriptions remain a long-term
application direction, not a reason to add arbitrary COM or Python execution
into the public protocol.

## Acceptance boundaries

Unit/type checks, native functional tests and published assets are separate
claims. A failed operation can leave partial geometry; do not imply automatic
rollback or repeat a native write merely to recover delivery. Keep previous
version evidence unchanged. A Wine-specific issue does not block Windows
publication unless traced to shared SWCLI code.

## Current bounded Document Properties batch

The existing series includes overall annotation font (seven writable fields), grid/virtual-sharp/plane display (ten model fields, five drawing fields), and 36 GB-to-named-standard round trips on the verified native 2025 SP5 host. See [batch scope](design/document-preferences-batch.md) and [page inventory](design/document-properties-coverage.md). These groups do not complete the whole Document Properties UI. Units, table defaults, STEP, assembly mates and modern API migration remain under separate evidence review. Finish this existing series before version freeze and owner publication approval; do not open another expansion.
