# Bounded persistent face/edge references

Development branch: `codex/swcli-topology-references`. No release/version change.
Native evidence is tracked separately in `WORK_HANDOFF.md`; portable tests alone
do not establish installed Windows acceptance.

## Public contract

- `entity.reference-create`: `entity_id`, optional `kind` (`face` default, `edge`).
- `entity.reference-resolve`: `reference` (opaque `swref1.` envelope, at most 262144 characters).
- Both use the existing optional `document_id` / `expected_update_stamp` context,
  forbid `lease_id`, and execute read-only in the existing resident COM worker.
  Another session's write lease does not forbid these reads. A reference grants
  no mutation authority; later writes retain all existing guards.
- CLI: `swcli entity reference-create e-xxxxxx --kind face --document d-xxxxxx --json > face.json`,
  then `swcli entity reference-resolve --reference-file face.json --document d-yyyyyy --json`.
  `--reference TOKEN` also exists for small tokens. The JSON file is read by the
  client, supports the CLI result or a protocol response's `result`, and is never
  opened by the daemon. File reads have a 524288-byte client limit.
- SDK: `client.entity.reference_create(...)`, `client.entity.reference_resolve(...)`.
  MCP: discover the two operation schemas with `capabilities`, then use `execute`
  with the same parameters/context. No direct COM public path is introduced.

## Identity and topology policy

Scope is a canonical absolute Windows `.SLDPRT` path, exact configuration name,
part document and exactly one solid body with no surface bodies. Both complete
face and edge sets must contain 1–64 entities. Unsaved parts, another path,
configuration mismatch, unsupported/over-limit topology, malformed envelopes and
uncertain native identity fail closed without publishing an entity or reference.

Creation requires a currently live short `e-*` handle, captures the complete
face/edge reference census and immediately proves each captured identity using
`GetObjectByPersistReference3` and `ISldWorks.IsSame`. Resolution never compares
reference byte strings as entity identity: it resolves each stored reference and
requires native status **integer zero**, exact current body/kind membership and
a bijection onto the complete current face/edge sets. Count changes, absent
objects, unknown/unwritten statuses, duplicate mappings and unresolved old
census members reject the entire operation. This intentionally also rejects a
surviving target when another part of its captured topology changed.

Successful resolution publishes fresh current observation geometry and a current
short `entity_id`, `native_status: 0`, `topology_verified: true`, and
`topology_policy: complete-face-edge-bijection`. `captured_update_stamp` remains
the original snapshot stamp; `document.update_stamp` is the current stamp. An
optional caller CAS checks the current stamp before traversal. Changed stamps or
configuration still permanently retire old short IDs under existing semantics.
Closing/reopening never revives an old ID; explicit persistent resolution can
issue another current ID after independently proving native identity.

Before/after observations check configuration, update stamp, modified/edit state,
foreground identity and document path across the entire operation. Geometry or
identity failure discards all usable output. The first native error is retained;
secondary final-state failures become warnings. The new operations do not select,
activate, save, rebuild, edit, retry a failed native call, or roll back CAD state.

This is **current native identity plus complete census correspondence**, not a
claim that all geometry, adjacency or past edit history is unchanged. A rebuild
or dimensional change can retain identity. Splits/merges that prevent a complete
unique census correspondence are rejected even if native resolution picks one
face. Unobserved delete/recreate histories with an indistinguishable final native
identity cannot be inferred. Saved path scope is not an immutable document UUID;
file copies/replacements, Save As, rename/move, assemblies, components, vertices,
surface/multiple bodies and arbitrary modeling edits carry no survival guarantee.
Tokens are opaque caller data, not signatures or authorization credentials.

## Official API and native calibration

Primary references:

- [Persistent Reference IDs](https://help.solidworks.com/2025/English/api/sldworksapiprogguide/Overview/Persistent_Reference_IDs.htm): model-local IDs can persist across sessions.
- [GetPersistReference3](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~GetPersistReference3.html): byte representations may change; they are not identity comparisons.
- [GetObjectByPersistReference3](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~GetObjectByPersistReference3.html): object and BYREF status; suppressed/deleted apply to topology.
- [swPersistReferencedObjectStates_e](https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swPersistReferencedObjectStates_e.html): bitmask OK=0, invalid=1, suppressed=2, deleted=4. Combined, unknown and malformed states fail closed; the raw integer is preserved as `native_status` when available.
- [DeleteSelection2](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~DeleteSelection2.html): used only to delete generated, owned calibration cuts, without prompting. Its absorbed-feature option comes from the actual swconst library.

Manual `native_topology_targeted=true`, `native_full=false` on this exact branch
runs two separately recorded groups with 600-second native/request budgets and
1800-second group budgets. The internal group reads actual installed swconst
enums and IModelDocExtension function signatures, creates hole/notch fixtures,
checks face splitting and merging, deletion state, rebuild, native save/reopen
and actual volumes/hashes. The public group uses CLI/SDK/MCP through one daemon,
verifies background reads under another session's write lease, CAS/cross-document
rejections, face/edge save/reopen identity and rejection after public cuts and
reopening the changed native output. Each group owns one host; there are no
within-group host replacements or failed CAD operation retries. Internal evidence
and targeted public proof remain ineligible for the full release gate.

The targeted concurrency group is unique to this profile and `github.ref`;
`cancel-in-progress` stays false. The default full/release concurrency group,
package/test prerequisites, PR secret boundary and tag publication gate remain.
A conflicting full+targeted selection fails before private input preparation.
