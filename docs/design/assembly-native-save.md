# Assembly native save and reopen gate

This change extends `document save-as` to `.SLDASM` for assembly documents.
Parts still require `.SLDPRT`; drawings and mismatched extensions are rejected
before the native call. Existing targets remain protected by exclusive file
reservation. Successful responses require a clean document, the adopted target
path, zero native save errors, and an artifact of at least 512 bytes whose format
matches the document type. Size is only a truncation guard, not a native-format
parser or a plausible-size range for every assembly.

The operation renames the selected document. It does not perform Pack and Go,
copy referenced components, request saving referenced documents, or promise
self-contained delivery. References must remain accessible for reopening.
It retains the existing silent `ModelDoc2.SaveAs3(path, 0, 1)` contract;
warnings are unavailable from this scalar API and remain `null`.

The shared `scripts/ci/verify-modeling.py` gate, when sample arguments are
provided by the host, now exercises:

1. Open the installed assembly and observe its configurations and complete,
   non-empty top-level feature tree.
2. Save to a new `assembly.SLDASM` in the evidence directory, check the actual
   file size against the reported size, then exercise `document save` only on
   this new file (never the installed source).
3. Close, reopen read-only with a fresh document ID, require zero open errors,
   and compare configurations and feature names/types with the original.
4. Close again and verify that the saved file's SHA-256 is unchanged by the
   read-only reopen. Record sizes and hash in `assembly_save_reopen` evidence.

Portable regression cases cover empty/truncated assembly output, mismatched
extensions, failed reopen, and changed structure. These are harness contracts,
not native CAD proof. The existing generated-part save/reopen sequence also
executes an in-place save and checks its resulting size before close/reopen.
Both PRT and ASM sizes appear in `native_in_place_saves` evidence.
This increment has not yet been validated on a real host;
it must not be included in the existing a8 runtime receipts as though it passed.
The gate does not claim component-level geometry, mate behavior, external
reference portability, or assembly insertion validation.

## Drawing in-place save and reopen

The optional drawing case uses existing public `document save` (`Save3`), not
drawing `save-as`. Supply both `--sample-drawing` (the installed source's absolute
Windows/UNC path visible to the daemon) and `--sample-drawing-local` (the same
file's client-visible filesystem path). For example, for a host whose selected
official fixture is staged at `C:\samples\ReferenceDrawing.SLDDRW`:

```bash
python scripts/ci/verify-modeling.py \
  --output-dir /ci-evidence --host-output-dir 'Z:\ci-evidence' \
  --cli-command /usr/local/bin/sw-cli \
  --sample-drawing 'C:\samples\ReferenceDrawing.SLDDRW' \
  --sample-drawing-local '/opt/wineprefix/drive_c/samples/ReferenceDrawing.SLDDRW'
```

The host adapter must choose an existing official sample and map both paths to
the same file; the example does not assert that every installation contains that
location. References must remain accessible after copying the drawing into the
evidence directory. This is not Pack and Go and does not copy referenced models.

The gate opens the installed source read-only to record a complete, non-empty
top-level feature tree, then closes it. It exclusively creates a byte-for-byte
`drawing.SLDDRW` copy in the evidence directory, opens the copy writable, compares
the baseline tree, and calls `document save` only on that copy. It checks the
actual post-save size (at least 512 bytes), closes, reopens read-only under a
fresh document ID, compares the feature names/types, and closes again. The saved
artifact must remain hash-identical during read-only reopen. The installed
source's before/after SHA-256 is checked even when the case fails.

Every open requires zero API errors. All API warnings are recorded and rejected
except the known read-only warning `2` on explicitly read-only opens; a missing
reference warning is not silently accepted. Sizes appear in
`native_in_place_saves`; drawing-specific hashes, open statuses and checks appear
in `drawing_save_reopen`.

Portable cases exercise save/reopen failures, truncation, changed/truncated
feature trees, unexpected warnings, artifact/source mutation, and protection of
existing output. These are harness tests, not real SOLIDWORKS proof. This case
does not validate individual sheet/view geometry or complete reference semantics:
the current public `inspect` surface supplies only the top-level feature tree.
The drawing case has not yet been validated on a native host.
