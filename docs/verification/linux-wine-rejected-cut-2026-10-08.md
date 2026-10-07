# Linux/Wine rejected-cut sequence investigation — 2026-10-08

This is development diagnostic evidence, not an a5 release gate pass or a
confirmed Wine source defect. The public native Windows sequence passed;
the Linux/Wine sequence remains under investigation.

## Environment and experimental boundary

- Trusted `workspaceroot`: Ubuntu 22.04.5, x86_64, Wine 11.16,
  SOLIDWORKS 2025 SP5 (`33.5.0`), Podman.
- Isolated diagnostic image `localhost/swcli-a5-probe:20261008`, based on
  `ghcr.io/yjbeetle/sw-executable:sha-9b73e84`. Its SWCLI snapshot `966a8be`
  has no runtime `src/` differences from `64e97eb`; later changes are test/docs
  changes. This is not verification of the new hosted CI candidate image.
- Each `fresh-*` case starts a new container/writable Wine prefix from the
  same image. The preceding diagnostic container is stopped and archived,
  never reused as an input. No restart, native retry or assertion weakening
  occurs inside a case. One daemon-owned COM host executes the whole case.
- The helper uses only public CLI operations, generated unsaved parts and
  exact document IDs. It preserves checkpoint JSON, elapsed times, stderr,
  native Wine SEH output and final document/host observations. It does not
  touch user models, attach a debugger or change licensing settings.
- The diagnostic helper's process exit alone is not the verdict: its JSON
  `target_passed`, recorded errors and cleanup state must be inspected.

Evidence root on the test host:
`/tmp/swcli-wine-20261008.UV2nYN/evidence-context-20261008`.
One parameterized `probe-context.py` and `run-fresh.sh` serve all cases.

## Minimal public sequence

Using one explicit session and returned document/sketch IDs:

1. Require a connected owned host and an empty document list.
2. `document create`; front-plane rectangle 40×30 mm; extrude 10 mm.
3. Front-plane radius-2 mm circle centered at x=1000 mm.
4. `feature cut-extrude <outside-sketch> --depth-mm 10` must return
   `CutExtrusionFailed`, without cleanup warnings.
5. Document/sketch inspection must succeed with `editing=false`; measurement
   must still report one solid and 12000 mm³.
6. Either retain that document, or close it and require an empty list before
   creating a fresh foreground part.
7. Create a front-plane radius-8 mm circle centered at (3,4) mm in the selected
   target; require final native geometry verification and `editing=false`.
8. Close only case-owned documents, require an empty list and inspect health.

The matched no-cut control omits only step 4. There are no exports, dimensions,
leases or external paths in this smaller sequence. Thus those features are
not necessary inputs to this reproduction.

## Completed fresh-prefix controls

| Case | Resident mode | Target after rejected cut | Result |
| --- | --- | --- | --- |
| `fresh-hidden-foreground-no-cut` | Hidden | Close base, fresh foreground part; cut omitted | Passed; target circle 1.236 s |
| `fresh-hidden-foreground-cut` | Hidden | Close base, fresh foreground part | Failed at InsertSketch after 59.077 s, `0x800703E6` |
| `fresh-visible-foreground-cut` | Visible | Close base, fresh foreground part | Passed; target circle 16.511 s |
| `fresh-hidden-same-cut` | Hidden | Keep base, add circle in that same part | Passed; target circle 0.915 s |

All four completed with empty cleanup errors and zero remaining documents.
Their original native PIDs respectively remained **612, 608, 608, 616**,
connected with `worker_alive=true`. PID values belong to independent Wine
prefixes: matching numeric PIDs across cases do not mean the same process.

In the failing foreground case, the rejected cut itself completed in 0.621 s;
closing the base, checking an empty list and creating the next part all
succeeded. New-document creation took 1.707 s. The failure occurs specifically
at `sketch-enter / InsertSketch`, before circle geometry creation. Returned
editing state was false and the host was not restarted. This extends the
earlier background-document reproduction: background activation is not required.

The native stderr file `fresh-hidden-foreground-cut/native-runtime-stderr/`
`swclid-start-error.h3nZOv` contains a caught `c0000005` read access violation
at `0x45ae70f0`, attempting address `0xb38`. The previously captured module map
places this address range in `sldappu.dll`. This is an observed native exception,
not a first-chance call stack or proof that Wine's implementation caused it.

## Interpretation and remaining work

- The same-document pass argues against treating any rejected cut as an
  immediately unusable COM host. Closing/replacing the document still needs
  isolation from an interval with no open documents.
- The visible control changes **both** residency and visibility, not just
  rendering: current SWCLI uses `UserControl=true, Visible=true` versus
  `UserControlBackground=true, Visible=false`. The official
  [UserControl](https://help.solidworks.com/2023/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~UserControl.html)
  and [UserControlBackground](https://help.solidworks.com/2022/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~UserControlBackground.html)
  descriptions explain this distinction. One visible pass does not establish
  a general fix, and the visible calls were substantially slower.
- A prior case reused an old container after a manual daemon restart and
  timed out during new-document creation; subsequent startup failed. That
  confounded result is retained as `hidden-foreground-v2`, but is not used as
  a fresh-prefix cut-trigger proof.
- Next controls should retain the base while creating another part, repeat
  the fresh hidden failure, and separate empty-document/close behavior from
  host mode. Any proposed runtime change must pass the full shared sequence
  without native retries or hidden host replacement.

For earlier CI and Windows evidence, see
[the a5 verification record](a5-2026-10-07.md).
