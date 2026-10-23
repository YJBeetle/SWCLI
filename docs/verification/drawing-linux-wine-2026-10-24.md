# Drawing dependency lifetime on Linux/Wine

DockerSW CI [39984942513](https://github.com/YJBeetle/DockerSW/actions/runs/39984942513)
used SWCLI `f75ace4`. First-angle PRT view insertion, drawing save/reopen and
strict PDF/DWG export succeeded. The subsequent source inspection failed with
`DocumentNotFound`; the image was not promoted. This was not an insertion timeout.

A focused reproduction on workspaceroot used the same public drawing gate with
catalog observations added, Wine 11.16 and SOLIDWORKS 33.5.0, hidden mode. The
native catalog contained the source and drawing before drawing close; immediately
after close it contained only the unrelated foreground blocker. Reopening the
drawing reloaded the same source path under a new document ID. Its old ID was
correctly invalidated. This establishes dependency unload/reload for this case,
not a general Wine-only defect or a broken document registry.

Evidence is retained at
`/tmp/swcli-drawing-probe.J3gvza/evidence/drawings.json` on workspaceroot. The first
failed case and its cleanup error remain preserved; later probes use a new folder.

The gate now checks the full source structure before close, records each native
catalog boundary, and explicitly opens the saved source path after the deliberate
drawing reopen to acquire its current identity. Full source structure, clean and
rebuilt state, and unchanged source/child file hashes remain required. Cleanup
retires only known handles absent from the native catalog; unknown documents are
not adopted or silently closed. No geometry assertion, CAD retry or host restart
is introduced.

The corrected gate passed both `part-first-angle` and `assembly-third-angle` in
the same owned SOLIDWORKS instance on workspaceroot. The terminal record reports
`success: true`, an unchanged host PID, and `cleanup_errors: []`; source/child
hashes and complete source structures passed the original comparisons. The record
and native/PDF/DWG artifacts are in the `reconciled/` subdirectory. This is focused
Linux/Wine runtime evidence, not a claim that the entire three-platform CI passed.
