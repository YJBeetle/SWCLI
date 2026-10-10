"""Native file naming on the worker's existing document, without export semantics."""

from __future__ import annotations

import ntpath
from pathlib import Path
from typing import Any, Dict

from .windows import _com_value, _describe_document, _error
from .windows_documents import _bitmask_names, _SAVE_ERRORS


def save_as_native_windows(output: str, *, document: Any) -> Dict[str, Any]:
    """Rename a native document to a new file; do not copy/save references."""

    path = Path(output).expanduser().resolve()
    result: Dict[str, Any] = {
        "ok": False,
        "action": "document.save-as",
        "output": str(path),
    }
    reserved = False
    verified_file = False
    try:
        kinds = {".sldprt": 1, ".sldasm": 2, ".slddrw": 3}
        suffix = path.suffix.casefold()
        if suffix not in kinds:
            result["error"] = {
                "type": "InvalidArgument",
                "message": "native save-as requires a .SLDPRT, .SLDASM or .SLDDRW output",
            }
            return result
        if not path.parent.is_dir():
            result["error"] = {
                "type": "ParentDirectoryNotFound",
                "message": f"output directory does not exist: {path.parent}",
            }
            return result
        if path.exists():
            result["error"] = {
                "type": "OutputExists",
                "message": "save-as requires a new target; use document save for an existing document filename",
            }
            return result
        before = _describe_document(document)
        result["document_before"] = before
        if before["type"] not in kinds.values():
            result["error"] = {
                "type": "UnsupportedDocumentType",
                "message": "native save-as supports part, assembly and drawing documents only",
            }
            return result
        if before["type"] != kinds[suffix]:
            result["error"] = {
                "type": "InvalidArgument",
                "message": "native output extension must match the selected document type",
            }
            return result
        if (
            _com_value(_com_value(document, "SketchManager"), "ActiveSketch")
            is not None
        ):
            result["error"] = {
                "type": "SketchEditInProgress",
                "message": "finish sketch editing before native save-as",
            }
            return result
        # Reserve the new destination exclusively so an existing target cannot
        # be overwritten between the preflight check and the native call. Native
        # save-as changes the live document name, so export's temp+replace path
        # would leave the COM document pointing at the discarded temporary name.
        with path.open("xb"):
            pass
        reserved = True
        document.ClearSelection2(True)
        error_code = int(document.SaveAs3(str(path), 0, 1))
        result["api_saved"] = error_code == 0
        result["save_errors"] = error_code
        result["save_error_names"] = _bitmask_names(error_code, _SAVE_ERRORS)
        # Scalar ModelDoc2.SaveAs3 has no warning output; do not invent zero.
        result["save_warnings"] = None
        result["document"] = _describe_document(document)
        if error_code != 0:
            result["error"] = {
                "type": "SaveFailed",
                "message": "SOLIDWORKS failed to save the selected native document",
            }
            return result
        size = path.stat().st_size
        # Native SOLIDWORKS formats are version-dependent. Do not assume the
        # legacy compound-file header: current parts use a different container.
        # Reopening with SOLIDWORKS is a separate, stronger verification step.
        result["file_verification"] = {
            "non_empty": size > 0,
            "minimum_size_valid": size >= 512,
        }
        if size < 512:
            result["error"] = {
                "type": "NativeSaveVerificationFailed",
                "message": "saved document is empty or smaller than the minimum native file size",
            }
            return result
        verified_file = True
        result["artifact"] = {
            "kind": "native-document",
            "format": suffix[1:].upper(),
            "path": str(path),
            "size_bytes": size,
        }
        after = result["document"]
        if ntpath.normcase(ntpath.normpath(after["path"])) != ntpath.normcase(
            ntpath.normpath(str(path))
        ):
            result["error"] = {
                "type": "NativeSavePathMismatch",
                "message": "SOLIDWORKS did not adopt the requested native document filename",
            }
            return result
        if after["modified"]:
            result["error"] = {
                "type": "DocumentStillModified",
                "message": "SOLIDWORKS left the document modified after native save-as",
            }
            return result
        result["ok"] = True
        return result
    except FileExistsError:
        result["error"] = {
            "type": "OutputExists",
            "message": "save-as target was created before it could be reserved",
        }
        return result
    except Exception as exc:
        result["error"] = _error(exc)
        return result
    finally:
        if reserved and not verified_file:
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                result.setdefault("warnings", []).append(
                    {
                        "code": "native-output-cleanup-failed",
                        "message": str(exc),
                        "path": str(path),
                    }
                )
