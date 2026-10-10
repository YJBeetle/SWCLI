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
not native CAD proof. This increment has not yet been validated on a real host;
it must not be included in the existing a8 runtime receipts as though it passed.
The gate does not claim component-level geometry, mate behavior, external
reference portability, or assembly insertion validation.
