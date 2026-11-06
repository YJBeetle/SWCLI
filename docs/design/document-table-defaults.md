# Bounded document table defaults

This branch implements five non-font document defaults. It does not create,
insert, enumerate or edit an actual BOM/general table. Public reads use the
selected document's `IModelDocExtension`, without activation or application
preference changes. Public writes currently fail closed with
`DocumentTableCalibrationRequired`: the accepted version/type profile set is
empty. Internal candidate calibration is not public acceptance.

| Field | API preference symbol | Type | Document types |
| --- | --- | --- | --- |
| `all.use_template_settings` | `swDetailingTablesUseTemplateSettings` | Toggle | part, assembly, drawing |
| `bom.box_border` | `swDetailingBillOfMaterialBorderLineWeight` | Integer | part, assembly, drawing |
| `bom.grid_border` | `swDetailingBillOfMaterialGridLineWeight` | Integer | part, assembly, drawing |
| `general.box_border` | `swDetailingGeneralTableBorderLineWeight` | Integer | drawing only |
| `general.grid_border` | `swDetailingGeneralTableGridLineWeight` | Integer | drawing only |

All calls use `swDetailingNoOptionSpecified` and the corresponding
`IModelDocExtension.GetUserPreferenceInteger/Toggle` or
`SetUserPreferenceInteger/Toggle`. Preference IDs are resolved by exact symbol
name from the owning installation's `swconst.tlb`, using the directory returned
by `ISldWorks.GetExecutablePath` (read once through the existing pywin32 property/method adapter). Missing/duplicate symbols or unexpected line
weight constants fail closed. No guessed IDs, application preferences, registry
writes or caller-supplied COM members are accepted.

The official documentation distinguishes document-level General defaults
(drawing-only) from BOM defaults (all document types). This is the applicability
boundary even if an API getter on another document type returns an integer.
Inapplicable fields are returned as `{"unavailable":"document_type"}` without a
native getter. Other fields return `{"value":...,"native_value":...}`. Unknown
line-weight integers remain readable as `value: "other"`, preserving the raw
integer. Writable border values are bounded to `thin`, `normal`, `thick`.

## Protocol, CLI, SDK and MCP

- `document.table-options`: selected-document read; optional `document_id` and
  `expected_update_stamp`; no lease or temporary activation.
- `document.table-option-set`: `field`, `value`, and complete `expected_options`
  snapshot; **required** `document_id`, `expected_update_stamp`, and `lease_id`.
- CLI: `swcli document table-options --document d-... --json` and
  `swcli document table-option-set bom.box_border thick --document d-... --lease l-... --if-update-stamp 7 --if-options-json '<complete options object>' --json`.
- SDK: `client.document.table_options(...)` and
  `client.document.table_option_set(field=..., value=..., expected_options=..., document_id=..., expected_update_stamp=..., lease_id=...)`.
- MCP: generic operation execution exposes the same catalog/request/result
  schemas. There is no force/calibration parameter or environment gate bypass.

Admission data is scoped to exact `RevisionNumber`, document type, field and
`(before raw value, after raw value)` transition in
`document_table_profiles.py`. A verified target may also admit its unchanged
pair for no-op observation. A known revision does not authorize every catalog
value or an untested reverse transition. Declared `macos-wine` and `linux-wine`
daemons reject these writes before worker dispatch; native Windows evidence
does not open Wine support. At this stage the data remains empty.

The `expected_options` argument is the entire `options` object returned by the
read, including all raw values and unavailable entries. Validation rejects
missing, extra, mistyped or inconsistent entries. The adapter compares the whole
snapshot before one setter; drift in an unrelated scalar rejects the edit.
A same-value request is a read-only no-op after the CAS and state checks.

Before mutation, the implementation verifies writable/non-view-only status,
normal drawing-sheet or inactive model-sketch context, exact document identity,
configuration, update stamp, open-document membership and foreground identity.
Readback checks the requested value, all unrequested table fields and editing
context. A background edit also preserves its foreground peer's dirty flag,
update stamp, configuration and identity. It marks the target dirty at most once,
then performs a final observation that may not alter the stamp or dirty flag.

Every failure returns `mutation.attempted` and `mutation.may_have_changed`.
A Boolean setter return is retained as `native_returned`. Once a setter is
entered, both mutation flags are true even if the call raises, returns false,
or fails round-trip/context checks. There are no setter retries, automatic
rollback writes or host restarts. Callers must inspect the selected document
following a partial failure.

The official `SetUserPreferenceToggle` help describes the return as the enabled
state, while the baseline annotation adapter records a successful disable as
`True` on its calibrated host. This new table field is not assumed to share that
behavior: a `False` return is retained and fails closed without retry. Internal
calibration must resolve that field-specific ambiguity before public promotion.

## Evidence and remaining boundary

Portable tests verify the protocol/CLI/schema wiring, CAS, applicability,
lease/update-stamp rejection, readonly/view-only/sketch guards, context drift,
unknown enums, side effects, partial mutations and calibration control flow.
They do not prove native SOLIDWORKS behavior.

The branch-only `CI` dispatch input `table_defaults_calibration` defaults to
false and requires `table_defaults_head` to equal this branch's exact SHA.
`table_defaults_mode` selects `internal` (default) or `public`. Both use the
dedicated `swcli-table-defaults-calibration` concurrency group and skip unrelated
portable/package/full native jobs in that manual run. Internal mode runs only
the candidate calibration on a fresh GitHub Windows runner. It keeps the
existing event policy (no pull-request secret execution). One owned host serves
part, assembly and explicit-template drawing fixtures. It checks each supported
scalar, no-op, stale full CAS, geometry/feature health, new-file save/reopen and
read-only rejection. Failure stops the remaining plan; the wrapper limits calls
to 600 seconds and the group to 1800 seconds and preserves original evidence.

The internal report retains `full_acceptance_eligible: false`. A green internal
run must first pass independent checks of its original ZIP/GitHub artifact
SHA256, exact head, paired/nested native traces, getter/setter counts, original
and saved fixture hashes, write/no-op/CAS receipts, host cleanup and persisted
values. The auditor derives only observed raw transitions; it does not open the
whole scalar catalog.

Public mode requires pinned successful internal run/artifact provenance and
re-audits the downloaded original report, traces and fixtures before private
runtime setup. Read permission for that artifact is scoped to this manual,
exact-branch/head job. It starts one owned hidden daemon and uses public CLI
requests for selected-document edits, lease/stamp/full-snapshot conflicts,
no-ops, distinct save-as and fresh-handle read-only reopen. The part keeps its
independent analytic volume, area and centroid. Typed SDK and MCP bridge reads
and no-op writes use the same real daemon. Per-request native trace proofs
require exactly one setter for a changed field, zero for no-op/refusal, complete
readback ordering and no application preference setters. The wrapper confirms
owned daemon shutdown after the empty-document check.

A successful scoped public gate is recorded separately from the internal run;
it is not a full-modeling or release gate. Profiles and evidence still require
coordinator review before main integration. No release or main merge is
performed here.

Out of scope: fonts/text formats, layers, padding, zero quantity, leading or
trailing zeros, quantity header strings, BOM update rules, other table types,
existing table objects, Excel-based BOMs and templates outside owned fixtures.

## Official API sources checked 2026-11-07

- [Tables document properties](https://help.solidworks.com/2025/English/SolidWorks/sldworks/HIDD_Options_General_Tables_New.htm): document scope and template-setting behavior.
- [BOM document properties](https://help.solidworks.com/2025/english/SolidWorks/sldworks/HIDD_Options_bom_tables.htm): available for all document types.
- [General-table document properties](https://help.solidworks.com/2025/english/SolidWorks/Sldworks/HIDD_Options_gen_table.htm): available only for drawings.
- [BOM API preference mapping](https://help.solidworks.com/2025/english/api/swconst/DP_Tables-BillOfMaterials.htm) and [General API preference mapping](https://help.solidworks.com/2025/english/api/swconst/DP_Tables-General.htm): exact integer preference and option symbols.
- [Tables API preference mapping](https://help.solidworks.com/2024/english/api/swconst/DP_Tables.htm): exact template-settings toggle mapping (2024 page verified; 2025 design help confirms behavior).
- [Line-weight enumeration](https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swLineWeights_e.html): readable values and bounded writable subset.
- [GetExecutablePath](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~GetExecutablePath.html): installation directory semantics.
- [System options and document properties](https://help.solidworks.com/2025/english/api/sldworksapiprogguide/overview/System_Options_and_Document_Properties.htm): application versus document API ownership.

- [SetUserPreferenceToggle return semantics](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~SetUserPreferenceToggle.html): Boolean state wording; deliberately unresolved for new table fields pending native evidence.
