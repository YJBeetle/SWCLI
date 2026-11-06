"""Read and edit custom properties through the resident SOLIDWORKS host."""

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
WRITABLE_PROPERTY_TYPES = {name: code for code, name in _PROPERTY_TYPES.items()
                           if name not in ("unknown", "equation")}


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


def _verify_metadata_state(app: Any, document: Any, before: tuple, foreground: Any, *, changed: bool,
                           require_writable: bool = False) -> None:
    after = _state(document)
    stable = (after[0], after[3]) == (before[0], before[3]) if changed else after == before
    if not stable or not _same(app, foreground, _com_value(app, "ActiveDoc")):
        raise RuntimeError("document state or foreground changed during metadata operation")
    if changed and not after[2]:
        if require_writable:
            _require_writable(document)
        native_call("document-metadata", "IModelDoc2.SetSaveFlag", lambda: document.SetSaveFlag())
        final = _state(document)
        if not final[2] or (final[0], final[3]) != (before[0], before[3]) or not _same(
            app, foreground, _com_value(app, "ActiveDoc")
        ):
            raise RuntimeError("metadata write did not preserve context and mark the document for saving")


def _require_writable(document: Any) -> None:
    if (_com_value(document, "IsOpenedReadOnly") is not False
            or _com_value(document, "IsOpenedViewOnly") is not False):
        raise ValueError("the selected document is not writable")


def _property_manager(document: Any, kind: int, configuration: Optional[str]) -> Any:
    if configuration is not None:
        if kind == 3:
            raise ValueError("drawings do not have configuration properties")
        target = native_call("document-properties", "IModelDoc2.GetConfigurationByName",
                             lambda: document.GetConfigurationByName(configuration))
        if target is None or _com_value(target, "Name") != configuration:
            raise ValueError(f"configuration {configuration!r} was not found by exact name")
    extension = _com_value(document, "Extension")
    return native_call("document-properties", "IModelDocExtension.CustomPropertyManager",
                       lambda: extension.CustomPropertyManager(configuration or ""))


def read_document_properties_windows(
    *, app: Any, document: Any, name: Optional[str], configuration: Optional[str] = None
) -> dict:
    result = {"ok": False, "action": "document.properties"}
    try:
        before = _state(document)
        foreground = _com_value(app, "ActiveDoc")
        try:
            manager = _property_manager(document, before[0], configuration)
            properties = _read_properties(manager, name)
        finally:
            _verify_metadata_state(app, document, before, foreground, changed=False)
        result.update(ok=True, scope="document" if configuration is None else "configuration",
                      requested_name=name, properties=properties)
        if configuration is not None:
            result["configuration"] = configuration
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def read_property_summary_windows(*, app: Any, document: Any, name: Optional[str]) -> dict:
    result = {"ok": False, "action": "document.property-summary"}
    try:
        state = _state(document)
        if state[0] == 3:
            raise ValueError("drawings do not have configuration properties")
        foreground = _com_value(app, "ActiveDoc")
        names = _com_value(document, "GetConfigurationNames")
        if (not isinstance(names, (tuple, list)) or not 1 <= len(names) <= 1000
                or any(not isinstance(item, str) or not item.strip() for item in names)
                or len(set(names)) != len(names) or state[3] not in names):
            raise RuntimeError("native configuration name list is incomplete or exceeds 1000")
        configurations = []
        count = 0
        for configuration in names:
            manager = _property_manager(document, state[0], configuration)
            rows = _read_properties(manager, name)
            count += len(rows)
            if count > _MAX_PROPERTIES:
                raise RuntimeError("property summary exceeds 1000 rows")
            configurations.append({"configuration": configuration, "properties": rows})
            _verify_metadata_state(app, document, state, foreground, changed=False)
        result.update(ok=True, requested_name=name, configurations=configurations)
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def edit_document_property_windows(*, app: Any, document: Any, action: str, values: dict) -> dict:
    configuration = values.get("configuration")
    name = values["name"]
    result = {"ok": False, "action": action, "name": name,
              "scope": "document" if configuration is None else "configuration",
              "mutation": {"attempted": False, "may_have_changed": False}}
    if configuration is not None:
        result["configuration"] = configuration
    try:
        _require_writable(document)
        state = _state(document)
        foreground = _com_value(app, "ActiveDoc")
        manager = _property_manager(document, state[0], configuration)
        before = _read_property(manager, name)
        result["before"] = before
        if action == "document.property-add":
            if before is not None:
                raise ValueError(f"property {name!r} already exists in this scope")
            value = values["value"]
            type_code = WRITABLE_PROPERTY_TYPES[values.get("type", "text")]
            method, args = "Add3", (name, type_code, value, 0)  # OnlyIfNew
        else:
            if before is None:
                raise ValueError(f"property {name!r} is missing in this scope")
            if before["linked"]:
                raise ValueError(f"property {name!r} is linked")
            if "expected_value" in values and values["expected_value"] != before["raw_value"]:
                raise ValueError(f"property {name!r} no longer matches the expected value")
            value = values.get("value")
            type_code = before["type_code"]
            method, args = ("Delete2", (name,)) if value is None else ("Set2", (name, value))
        _verify_metadata_state(app, document, state, foreground, changed=False)
        if method == "Set2" and value == before["raw_value"]:
            result.update(ok=True, changed=False, property=before)
            return result
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        code = native_call("document-properties", f"ICustomPropertyManager.{method}",
                           lambda: getattr(manager, method)(*args))
        if type(code) is not int or code != 0:
            raise RuntimeError(f"native {method} returned {code!r}")
        after = _read_property(manager, name)
        if method == "Delete2":
            if after is not None:
                raise RuntimeError("native property is still present after deletion")
        elif after is None or (after["type_code"], after["raw_value"]) != (type_code, value):
            raise RuntimeError("native property did not round-trip the requested type and value")
        _verify_metadata_state(app, document, state, foreground, changed=True)
        result.update(ok=True, changed=True, property=after)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
