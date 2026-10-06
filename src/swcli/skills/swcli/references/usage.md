# Agent usage guide

This guide is for AI systems **using** SWCLI, rather than maintaining its source.
It is distributed with the skill and Python package. Use the running daemon's
capabilities to resolve version differences; pre-release interfaces can change.

## Connect and discover

```bash
sw-cli version --json
sw-cli daemon status --json
sw-cli capabilities --json
```

The client runs on Windows, macOS or Linux. Only swclid's STA worker performs
SOLIDWORKS COM operations. Typed commands never start a daemon implicitly or
fall back to direct COM. For an authorized local Windows test:

```powershell
sw-cli daemon start --visible --json
```

The default start requires an exclusive host; explicitly use `--attach-existing`
only when sharing an existing interactive instance is intended. Attach mode
does not create a host if none exists and does not take ownership of it.
DockerSW starts its own service; do not launch a second Windows worker there.

Use `--endpoint HOST:PORT` or `SWCLI_ENDPOINT` for another endpoint. The current
transport has no authentication. Do not expose it to untrusted networks. Use
an authenticated tunnel or a trusted boundary. Native save/open/output paths
belong to the server. DockerSW's Linux entry point translates mounted Linux
paths for Wine; this is not a general remote file-transfer facility.

Capabilities publishes `operations`, `operation_schemas` and (on supported
versions) `operation_result_schemas`. Check the requested operation and its
`x-swcli-context` before assembling a request. `--help` is available locally.
If the host lacks a requested operation, report that limitation rather than
inventing a command or silently choosing a mesh/GUI workaround.

## Select documents and coordinate writers

```bash
sw-cli --session bracket document open model.SLDPRT --json
sw-cli --session bracket document list --json
sw-cli --session bracket document inspect --document d-ab12cd --json
sw-cli --session bracket document status --document d-ab12cd --json
```

Replace example IDs with real returned handles. Open/create sets the requesting
session's current document. `document use ID` changes that current handle.
`--document ID` and `--document active` select a document for one call without
changing current. Temporary foreground activation restores the previous tab.
Different session names isolate current-document state, not SOLIDWORKS itself.

Document IDs are worker-local and expire on close or worker replacement. Sketch
IDs are additionally scoped to their document; they are not persistent native
references or names. Reopening a file does not promise the same IDs.

```bash
sw-cli --session bracket document lease acquire --document d-ab12cd --ttl-seconds 60 --json
# Use the returned token, and the stamp from a recent document observation.
sw-cli --session bracket document rebuild --document d-ab12cd --lease l-ab12cd34ef56 --if-update-stamp 0 --json
sw-cli --session bracket document lease release l-ab12cd34ef56 --json
```

Reuse the same session with the token. Renew if work approaches expiry and
release after the guarded work; a crashed holder blocks cooperating writers
until TTL expiry. Leases are per daemon, not distributed/file locks. Reads and
human GUI actions are not prevented. A stamp conflict means re-inspect and
re-plan; do not blindly replace the stamp to force the original action.

## Model and verify

On development versions advertising these operations:

```bash
sw-cli --session bracket document create --type part --json
sw-cli --session bracket sketch rectangle --plane front --width-mm 100 --height-mm 50 --json
sw-cli --session bracket document inspect --detail structure --json
sw-cli --session bracket document diagnose --json
```

The rectangle is a fresh sketch using millimeters in sketch-local coordinates.
Its result verifies native edges after leaving edit mode, but does not add
driving dimensions or guarantee full definition. Preserve its sketch ID for
later supported feature commands; do not substitute a feature name. Hosts
advertising `feature.extrude` accept `sw-cli feature extrude SKETCH_ID
--depth-mm 20 --json`; it requires an unabsorbed 2D sketch in the selected part.
`--reverse` and `--no-merge` are explicit optional choices. Hosts advertising
`sketch.circle` accept `sw-cli sketch circle --plane front --radius-mm 8 --json`
with optional local center coordinates. Radius means radius, not diameter;
the closed sketch result verifies a single complete native circle. Its handle
can also be passed to `feature extrude`. A new
document is unsaved: do not assume `document save` names it or that export saves
the native source. Hosts advertising `document.save-as` accept:

```bash
sw-cli --session bracket document save-as new-part.SLDPRT --json
sw-cli --session bracket document close --json
sw-cli --session bracket document open new-part.SLDPRT --read-only --json
sw-cli --session bracket document inspect --detail structure --json
sw-cli --session bracket document diagnose --json
```

Save-as currently supports parts and rejects existing targets; there is no
overwrite or copy mode. Renaming preserves the live document/lease/sketch IDs,
but close/reopen creates a new document handle and drops the old handles. Its
file-size/native-state checks are not a full integrity proof; reopen and verify
the geometry. Saving is allowed only when the task authorizes source changes.
Use only the save-as/feature operations the host advertises.

Inspect/diagnose have additional structure and feature evidence; status reports
document state, not an invented `export_ready` flag. `modified` means the native
save flag is set; `needs_rebuild` is a separate native state. Neither should be
silently resolved by saving/rebuilding if the task is only to validate committed
CI sources. Rebuild diagnostics, requested dimensions and geometry checks form
the acceptance loop; an API returning success alone is insufficient.

Hosts advertising `document.measure` support `sw-cli document measure --json`
for all solid bodies of a part. It reports kernel-derived mm³ volume, mm² area
and the volume-weighted center in part-model millimeters without selection or
rebuild changes. It is a read, available even while another session holds a
lease. Totals sum bodies rather than unioning overlapping geometry, and area
includes each body's contact/internal faces. It does not report real material
mass; approximate boxes remain a different kind of evidence.

Hosts advertising `feature.cut-extrude` accept a live sketch ID and positive
`--depth-mm`, with the same normal/default and `--reverse` convention as bosses.
It cuts all intersected solids and requires native-definition/rebuild checks
plus measured volume reduction; this is blind depth, not through-all. It does
not choose a body from GUI selection or roll back a failed partial feature.
Create a profile that intersects existing solid material and verify the actual
removed volume/shape against the task, not merely `ok: true`.

## Export and recover

```bash
sw-cli --session bracket document export output.STEP --document d-ab12cd --strict --json
```

Normal export is permissive and reports warnings when the source needs saving,
needs rebuilding or changes during export. Strict export rejects those source
states and post-export changes. Both modes verify a temporary artifact before
replacing the final path; overwrite requires explicit `--overwrite` authority.
Filename routing (which sources/formats CI wants) is the caller's policy, not
an SWCLI export rule. Surface the failing source and structured reason.

Observe exit codes and `error.type`/`error.code`; JSON alone is not proof of
success. If an operation fails, inspect native state before another mutation:
there is no general transaction rollback. After external host death, stale
document handles cannot be used and business commands do not silently restart
SOLIDWORKS. Report `HostDisconnected` and recover with an authorized daemon
restart. Shared-host timeouts require inspection and explicit recovery as well.

Request IDs protect nearby transport retries: reuse the same explicit
`--request-id` only for the same semantic request. The daemon replays the first
terminal result, including failure; a genuinely new retry needs a new ID.
This bounded in-memory cache is lost on daemon restart, not a durable
exactly-once log. Unknown outcomes require inspection, not blind retries.
