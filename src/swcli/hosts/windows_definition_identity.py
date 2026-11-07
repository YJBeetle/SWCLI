"""Opt-in read-only identity of the original GetDefinition IDispatch.

No cast, QueryInterface, feature access/selection or model mutation is performed.
A member name alone never establishes the returned interface version.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict

_INTERFACES = ("IExtrudeFeatureData2", "IRevolveFeatureData2", "ISimpleFilletFeatureData2")


def _library_identity(library: Any) -> Dict[str, Any]:
    attr = library.GetLibAttr()
    return {"guid": str(attr[0]).upper(), "lcid": attr[1], "syskind": attr[2],
            "major": attr[3], "minor": attr[4]}


def _type_identity(info: Any) -> Dict[str, Any]:
    attr = info.GetTypeAttr()
    return {"name": info.GetDocumentation(-1)[0], "iid": str(attr.iid).upper(),
            "typekind": attr.typekind}


@lru_cache(maxsize=1)
def _installed_catalog(path: str) -> Dict[str, Any]:
    import pythoncom

    source = Path(path)
    if not source.is_absolute() or not source.is_file():
        raise ValueError("installed sldworks typelib requires an existing absolute file path")
    # Microsoft documents that LoadTypeLib with a specified path does not
    # register the library. pywin32 exposes LoadTypeLib, not LoadTypeLibEx.
    library = pythoncom.LoadTypeLib(str(source))
    interfaces = []
    for index in range(library.GetTypeInfoCount()):
        name = library.GetDocumentation(index)[0]
        if name not in _INTERFACES:
            continue
        identity = _type_identity(library.GetTypeInfo(index))
        if identity["typekind"] in (pythoncom.TKIND_INTERFACE, pythoncom.TKIND_DISPATCH):
            interfaces.append(identity)
    return {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "library": _library_identity(library), "interfaces": interfaces}


def record_definition_identity(definition: Any, *, request_id: Any = None,
                               operation: Any = None, sequence: Any = None) -> None:
    """Record available identity, retaining partial evidence on diagnostic errors."""
    if os.environ.get("SWCLI_TRACE_DEFINITION_INTERFACES") != "1":
        return
    record: Dict[str, Any] = {
        "event": "swcli.native-interface", "call": "IFeature.GetDefinition",
        "request_id": request_id, "operation": operation, "sequence": sequence,
        "worker_pid": os.getpid(), "status": "unavailable",
        "returned_typeinfo_matches_v2": False,
    }
    try:
        info = definition._oleobj_.GetTypeInfo()
        record["returned_typeinfo"] = returned = _type_identity(info)
        library, index = info.GetContainingTypeLib()
        record["returned_library"] = _library_identity(library)
        record["returned_library_index"] = index
        path = os.environ.get("SWCLI_SLDWORKS_TYPELIB", r"C:\Program Files\SOLIDWORKS\sldworks.tlb")
        record["installed_typelib"] = catalog = _installed_catalog(path)
        matches = [entry["name"] for entry in catalog["interfaces"] if entry == returned]
        record["matching_official_interfaces"] = matches
        record["returned_typeinfo_matches_v2"] = bool(matches) and record["returned_library"] == catalog["library"]
        record["status"] = "matched" if record["returned_typeinfo_matches_v2"] else "unmatched"
    except Exception as exc:
        record["diagnostic_error_type"] = type(exc).__name__
    try:
        sys.stderr.write(json.dumps(record, ensure_ascii=True, allow_nan=False) + "\n")
        sys.stderr.flush()
    except Exception:
        pass
