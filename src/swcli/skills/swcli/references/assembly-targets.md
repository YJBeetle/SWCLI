# Active assembly readonly targets

Use `assembly.targets.list` and `assembly.targets.validate` only when advertised
by the running daemon. This candidate supports SOLIDWORKS 2025 revision 33.5.0,
a saved clean **readonly** ASM that is already active, and exactly two saved,
clean readonly, resolved external part instances: the first fixed and the second
floating. Each has one solid, no surface body, one configuration, and 1–64 plane
or cylinder faces. Finish sketch/component editing first.

The request never activates the ASM, changes its readonly state, or saves a
source. `AssemblyNotActive` requires an explicit user action followed by a new
request. A readonly open does not prove that every source is readonly; the daemon
checks actual native states. This API has local implementation/testing evidence;
its public native acceptance remains a separate gate from private native37.

## Observe and compare

First inspect the exact registered document ID and update stamp. `list` needs
that explicit `d-` ID, `expected_update_stamp`, and two exact component instance
names in fixed/floating order. Pass the live document lease if one exists.

```python
observed = client.assembly.targets.list(
    components=["coincident-aligned-component-1", "coincident-aligned-component-2"],
    document_id=assembly_id, expected_update_stamp=stamp,
    lease_id=lease_id,
).require_result()
target_ids = [target["target_id"] for target in observed["targets"]]
compared = client.assembly.targets.validate(
    snapshot_id=observed["snapshot_id"], target_ids=target_ids[:2],
    document_id=assembly_id, expected_update_stamp=stamp,
    lease_id=lease_id,
).require_result()
```

CLI equivalents use `assembly targets list FIXED_NAME FLOATING_NAME` and
`assembly targets validate SNAPSHOT_ID TARGET_ID [TARGET_ID ...]`, with
`--document`, `--if-update-stamp`, `--lease`, and `--json`. Validation requires a
live lease. The MCP `execute` tool accepts the same operation names, parameters,
and top-level context without a second handle namespace or automatic retry.

`at-` IDs have kind `assembly-face`; they are distinct from part face/edge `e-`
IDs. An `as-` snapshot and all its targets belong to the issuing session,
registered native ASM, and worker STA lifetime. Close/reopen or worker replacement
requires fresh discovery. A new list retires that session's previous batch.
Observed scope/native identity changes retire all existing batches; returning to
an old configuration or stamp does not revive them. The registry bounds live
sessions and lifetime issued tokens; exhaustion requires an explicit restart.

Each list issues a batch only after the complete census and final scope guard
succeed. Each validate reads all faces of both instances once, even when only two
handles are supplied. It compares the whole assembly/source/configuration/stamp,
component instance/pose/fixed/suppression, face geometry, raw references and exact
native identities. A stale/unknown/wrong-kind handle or failed native observation
never falls back to an index, reference hash, nearest face, second owner receiver,
replacement token, or another census attempt. On error, inspect/reconsider the
entire target; do not automatically refresh handles and replay intent.

## Readonly compare is not write authority

Successful `read_gate` says `scope="complete-readonly-target-census"`,
`mate_tree_compared=false`, and `write_authorized=false`. The existing mate tree
and solver definitions are outside this snapshot. No CreateMate, selection,
model write, save or reopen is performed. These tokens cannot be converted into
write tokens: reopening writable changes native document identity and invalidates
the old scope. A future writable-read mode needs its own explicit contract and
native acceptance, followed by mate-tree CAS and the separate write/save-reopen
gates. Private native37's six-face success does not establish any of those gates.
