"""Read document-level custom properties through the resident SOLIDWORKS host."""

from typing import Any, Optional

from .native_trace import native_call
from .windows import _com_value, _error
from .windows_feature_inspection import _same


_PROPERTY_TYPES = {
    0: "unknown", 3: "integer", 5: "double", 11: "yes-no",
    30: "text", 64: "date", 105: "equation",
}
_READ_RESULTS = {0: "cached", 2: "resolved"}
_MAX_PROPERTIES = 1000


def _get_value(manager: Any, name: str) -> tuple:
    import pythoncom
    from win32com.client import VARIANT

    raw = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, None)
    evaluated = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, None)
    resolved = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, False)
    linked = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, False)
    code = native_call(
        "document-properties", "ICustomPropertyManager.Get6",
        lambda: manager.Get6(name, True, raw, evaluated, resolved, linked),
    )
    return code, raw.value, evaluated.value, resolved.value, linked.value


def _read_property(manager: Any, name: str) -> Optional[dict]:
    code, raw, evaluated, resolved, linked = _get_value(manager, name)
    if type(code) is int and code == 1:
        return None
    if (
        type(code) is not int or code not in _READ_RESULTS
        or not isinstance(raw, str) or not isinstance(evaluated, str)
        or type(resolved) is not bool or type(linked) is not bool
    ):
        raise RuntimeError("native custom property value is unreadable")
    type_code = native_call(
        "document-properties", "ICustomPropertyManager.GetType2",
        lambda: manager.GetType2(name),
    )
    if type(type_code) is not int or type_code < 0:
        raise RuntimeError("native custom property type is unreadable")
    return {
        "name": name, "type_code": type_code, "type": _PROPERTY_TYPES.get(type_code, "unknown"),
        "raw_value": raw, "evaluated_value": evaluated, "resolution": _READ_RESULTS[code],
        "was_resolved": resolved, "linked": linked,
    }


def _read_properties(manager: Any, name: Optional[str]) -> list:
    if name is not None:
        value = _read_property(manager, name)
        return [value] if value is not None else []
    count = _com_value(manager, "Count")
    if type(count) is not int or not 0 <= count <= _MAX_PROPERTIES:
        raise RuntimeError("native custom property count is unreadable or exceeds 1000")
    names = _com_value(manager, "GetNames")
    if names is None and count == 0:
        return []
    if (
        not isinstance(names, (list, tuple)) or len(names) != count
        or any(not isinstance(item, str) or not item.strip() for item in names)
        or len(set(names)) != count
    ):
        raise RuntimeError("native custom property name list is incomplete")
    values = [_read_property(manager, item) for item in names]
    if any(value is None for value in values):
        raise RuntimeError("a listed custom property disappeared during observation")
    return values


def _state(document: Any) -> tuple:
    kind = _com_value(document, "GetType")
    if type(kind) is not int or kind not in (1, 2, 3):
        raise RuntimeError("custom properties require a part, assembly or drawing")
    stamp = _com_value(document, "GetUpdateStamp")
    modified = _com_value(document, "GetSaveFlag")
    if type(stamp) is not int or type(modified) is not bool:
        raise RuntimeError("native document state is unreadable")
    configuration = None
    if kind in (1, 2):
        active = _com_value(document, "GetActiveConfiguration")
        configuration = _com_value(active, "Name")
        if not isinstance(configuration, str) or not configuration:
            raise RuntimeError("native active configuration is unreadable")
    return kind, stamp, modified, configuration


def read_document_properties_windows(*, app: Any, document: Any, name: Optional[str]) -> dict:
    result = {"ok": False, "action": "document.properties"}
    try:
        before = _state(document)
        foreground = _com_value(app, "ActiveDoc")
        try:
            extension = _com_value(document, "Extension")
            manager = native_call(
                "document-properties", "IModelDocExtension.CustomPropertyManager",
                lambda: extension.CustomPropertyManager(""),
            )
            properties = _read_properties(manager, name)
        finally:
            if _state(document) != before or not _same(app, foreground, _com_value(app, "ActiveDoc")):
                raise RuntimeError("document state or foreground changed while reading custom properties")
        result.update(ok=True, scope="document", requested_name=name, properties=properties)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
