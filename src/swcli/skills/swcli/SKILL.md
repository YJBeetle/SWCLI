---
name: swcli
description: Use SWCLI to inspect, model, render and export SOLIDWORKS documents through a running swclid daemon. Use when a task calls for SWCLI CAD automation, not for developing its Python implementation or installing Wine/SOLIDWORKS.
---

# SWCLI

Use the typed CLI as the CAD control plane. Do not replace it with generated
COM/Python scripts, GUI clicks, or an imagined SDK/MCP interface.

Read [the usage guide](references/usage.md) when preparing a modeling/export
workflow or connecting to an unfamiliar host. The guide travels with this
skill; it does not depend on the developer's machine or repository checkout.

## Working rules

- First run `sw-cli version --json`, `sw-cli daemon status --json` and
  `sw-cli capabilities --json`. The running daemon's operation schemas, result
  schemas and request contexts are authoritative. Do not assume an operation
  exists because a newer README mentions it.
- Use `--json` and check the process exit code as well as the response. Successful
  daemon management and CAD results have different envelopes; a connection
  failure is not an empty document list.
- Choose a session and explicit document IDs for multi-document work. Omitting
  `--document` means the session's current document, not the visible front tab.
- Read document state before modifying it. Use a lease and the observed update
  stamp for cooperating writers; zero is a valid stamp. These guards are not
  filesystem locks or protection from human edits.
- Use explicit units and object handles returned by the daemon. Do not guess
  localized feature/plane names or infer a handle from a filename or tree index.
- If `sketch.list` is advertised, discover fresh live sketch handles after
  opening/reopening a part, then inspect the returned IDs. Never reuse IDs
  from a closed document or assume listing also discovers dimensions.
- If `dimension.discover-diameter` is advertised, recover the observable unique
  single-circle diameter using a fresh exact sketch ID. Unobservable is not
  absent; do not guess by name or create a replacement dimension on failure.
- For hosts advertising driving dimensions, use their returned dimension handles
  and inspect parameter ownership before editing. A diameter is not a radius;
  edits target the current configuration and must not override equations or
  design tables. See the usage guide's parameterized-circle workflow.
- For supported rectangles, positioning and size are separate: `sketch.fix-center`
  is explicit; `sketch.dimension-rectangle` does not anchor the center implicitly.
  Inspect/edit the returned width/height roles, not guessed native dimensions.
  See the usage guide's parameterized-rectangle workflow and discovery limits.
- If feature observation/depth editing is advertised, use returned exact feature
  handles, not tree names. Inspection is read-only, not edit eligibility.
  `feature.set-depth` has narrow profile/scope/control guards; equal depth still
  performs native selection access and can advance the update stamp. Read the
  usage guide's depth-editing boundary before editing or handling a failure.
- Verify native state and geometry after a change. A failed operation can leave
  partial geometry; inspect before retrying. Do not claim automatic rollback,
  full constraint solving, or exact measurements from approximate body boxes.
- For CI acceptance use `document export --strict`. Do not suppress source
  saving/rebuilding problems just to obtain a green pipeline.
- Treat remote paths as paths on the execution host. A remote connection does
  not upload local files, and `--allow-remote` does not provide authentication.
- Starting/restarting/stopping a daemon changes the host lifecycle. Obtain the
  necessary user authority and never terminate another user's interactive host.
  Visible Windows tests use `daemon start --visible` or `daemon serve --visible`.

Keep actual design choices and acceptance criteria with the user's task. This
skill explains execution, not mechanical-design approval or permission to save,
overwrite, close, publish, or alter unrelated documents.
