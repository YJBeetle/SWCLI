"""Minimal native assembly creation and saved-part insertion, not mate solving."""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .native_trace import native_call
from .windows import _com_value, _describe_document, _error
from .windows_parts import _resolve_document_template


def create_assembly_windows_with_handle(
    *, app: Any, template: Optional[str] = None
) -> Tuple[Dict[str, Any], Optional[Any]]:
    result: Dict[str, Any] = {"ok": False, "action": "document.create"}
    document = None
    if sys.platform != "win32":
        result["error"] = {
            "type": "UnsupportedPlatform",
            "message": "native Windows document creation requires Windows",
        }
        return result, None
    try:
        resolved = _resolve_document_template(app, template, kind="assembly")
        result["template"] = {k: v for k, v in resolved.items() if k != "error"}
        if not resolved["ok"]:
            result["error"] = resolved["error"]
            return result, None
        document = native_call(
            "assembly-create", "SldWorks.NewDocument",
            lambda: app.NewDocument(resolved["path"], 0, 0.0, 0.0),
        )
        if document is None:
            result["error"] = {
                "type": "NewDocumentFailed",
                "message": "SOLIDWORKS could not create an assembly from the resolved template",
            }
            return result, None
        result["created"] = True
        result["document"] = _describe_document(document)
        if result["document"]["type"] != 2:
            result["error"] = {
                "type": "UnexpectedDocumentType",
                "message": "the resolved assembly template did not produce an assembly document",
            }
            return result, document
        result["ok"] = True
    except Exception as exc:
        result["error"] = _error(exc)
    # A handle acquired before failure still belongs in the daemon registry.
    return result, document


def add_part_component_windows(
    *, app: Any, document: Any, path: str, configuration: str = "",
    x_mm: float = 0.0, y_mm: float = 0.0, z_mm: float = 0.0,
) -> Dict[str, Any]:
    """Add a previously opened, saved PRT; never save or modify its source."""
    result: Dict[str, Any] = {"ok": False, "action": "assembly.add-component"}

    def fail(code: str, message: str) -> Dict[str, Any]:
        result["error"] = {"type": code, "message": message}
        return result

    try:
        if not all(math.isfinite(v) for v in (x_mm, y_mm, z_mm)):
            return fail("InvalidArgument", "component coordinates must be finite millimeters")
        source_path = Path(path).expanduser().resolve()
        if source_path.suffix.casefold() != ".sldprt":
            return fail("UnsupportedComponentType", "component path must use the .SLDPRT extension")
        if not source_path.is_file() or source_path.stat().st_size == 0:
            return fail("ComponentFileUnavailable", "component must be an existing nonempty saved PRT")
        if int(_com_value(document, "GetType")) != 2:
            return fail("UnsupportedDocumentType", "component insertion requires an assembly document")
        try:
            read_only = _com_value(document, "IsOpenedReadOnly")
            view_only = _com_value(document, "IsOpenedViewOnly")
        except Exception as exc:
            result["error"] = {
                "type": "DocumentStateUnavailable",
                "message": "cannot observe assembly read-only/view-only state",
                "cause": _error(exc),
            }
            return result
        if not isinstance(read_only, bool) or not isinstance(view_only, bool):
            return fail("DocumentStateUnavailable", "assembly read-only/view-only flags must be native booleans")
        if read_only:
            return fail("DocumentReadOnly", "cannot insert into a read-only assembly")
        if view_only:
            return fail("DocumentViewOnly", "cannot insert into a view-only assembly")
        # An assembly editing itself can return its root IComponent2. Neither
        # a non-null component nor a null one proves in-context editing state.
        try:
            edit_target = native_call(
                "component-preflight", "AssemblyDoc.GetEditTarget",
                lambda: _com_value(document, "GetEditTarget"),
            )
            if edit_target is None:
                return fail("DocumentStateUnavailable", "native assembly edit target is unavailable")
            edit_target_equality = native_call(
                "component-preflight", "SldWorks.IsSame(edit-target)",
                lambda: app.IsSame(edit_target, document),
            )
            if type(edit_target_equality) is not int or edit_target_equality not in (0, 1):
                return fail("DocumentStateUnavailable", "cannot determine native assembly edit target identity")
            if edit_target_equality == 0:
                return fail("ComponentEditInProgress", "finish in-context component editing before insertion")
            edit_component = native_call(
                "component-preflight", "AssemblyDoc.GetEditTargetComponent",
                lambda: _com_value(document, "GetEditTargetComponent"),
            )
            is_root = None if edit_component is None else native_call(
                "component-preflight", "Component2.IsRoot",
                lambda: _com_value(edit_component, "IsRoot"),
            )
        except Exception as exc:
            result["error"] = {
                "type": "DocumentStateUnavailable",
                "message": "cannot observe native assembly editing state",
                "cause": _error(exc),
            }
            return result
        if edit_component is not None and not isinstance(is_root, bool):
            return fail("DocumentStateUnavailable", "native component root flag must be a boolean")
        if edit_component is not None and not is_root:
            return fail("ComponentEditInProgress", "finish in-context component editing before insertion")
        source = app.GetOpenDocumentByName(str(source_path))
        if source is None:
            return fail("ComponentNotLoaded", "open the saved PRT with document open before inserting it")
        if int(_com_value(source, "GetType")) != 1:
            return fail("UnsupportedComponentType", "loaded component must be a part document")
        if Path(str(_com_value(source, "GetPathName"))).resolve() != source_path:
            return fail("ComponentPathMismatch", "the loaded component does not match the requested saved path")
        try:
            source_modified = _com_value(source, "GetSaveFlag")
        except Exception as exc:
            result["error"] = {
                "type": "ComponentStateUnavailable",
                "message": "cannot observe component modified state",
                "cause": _error(exc),
            }
            return result
        if not isinstance(source_modified, bool):
            return fail("ComponentStateUnavailable", "component modified flag must be a native boolean")
        if source_modified:
            return fail("ComponentModified", "save the component's unsaved modifications before insertion")
        if configuration and source.GetConfigurationByName(configuration) is None:
            return fail("ConfigurationNotFound", "the requested component configuration does not exist")
        before = native_call(
            "component-preflight", "AssemblyDoc.GetComponents",
            lambda: document.GetComponents(True),
        )
        if before is not None and not isinstance(before, (tuple, list)):
            return fail("AssemblyObservationUnavailable", "native component list is unreadable")
        before = tuple(before or ())
        component = native_call(
            "component-insert", "AssemblyDoc.AddComponent5",
            lambda: document.AddComponent5(
                str(source_path), 0, "", bool(configuration), configuration,
                x_mm / 1000.0, y_mm / 1000.0, z_mm / 1000.0,
            ),
        )
        if component is None:
            return fail("ComponentInsertionFailed", "SOLIDWORKS did not return an inserted component")
        # Insertion is not transactional. Preserve observations even when native
        # verification fails; do not hide failure with a second insertion.
        result["inserted"] = True
        result["component"] = {
            "name": str(_com_value(component, "Name2")),
            "path": str(_com_value(component, "GetPathName")),
            "configuration": str(_com_value(component, "ReferencedConfiguration")),
        }
        after = native_call(
            "component-verify", "AssemblyDoc.GetComponents",
            lambda: document.GetComponents(True),
        )
        if after is not None and not isinstance(after, (tuple, list)):
            return fail("AssemblyObservationUnavailable", "inserted component list is unreadable")
        after = tuple(after or ())
        result["component_count_before"] = len(before)
        result["component_count_after"] = len(after)
        result["placement"] = {
            "unit": "millimeter", "method": "native-approximate-component-center",
            "requested_center": {"x": x_mm, "y": y_mm, "z": z_mm},
        }
        result["document"] = _describe_document(document)
        if (
            len(after) != len(before) + 1
            or not any(int(app.IsSame(item, component)) == 1 for item in after)
            or not result["component"]["name"]
            or Path(result["component"]["path"]).resolve() != source_path
            or (configuration and result["component"]["configuration"] != configuration)
        ):
            return fail("ComponentVerificationFailed", "inserted component identity, path, configuration or count did not match")
        result["ok"] = True
    except Exception as exc:
        result["error"] = _error(exc)
    return result
