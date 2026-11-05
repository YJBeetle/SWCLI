"""Read and edit the file's native SOLIDWORKS Summary Information."""

from typing import Any, Optional

from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _state, _verify_metadata_state, _require_writable


EDITABLE_SUMMARY_FIELDS = {"title": 0, "subject": 1, "author": 2, "keywords": 3, "comment": 4}
SUMMARY_FIELDS = {**EDITABLE_SUMMARY_FIELDS, "saved_by": 5, "created_at": 8, "saved_at": 9}


def _summary_text(field: str, value: str) -> str:
    # SOLIDWORKS rewrites comment line endings as CRLF on save.
    return value.replace("\r\n", "\n") if field == "comment" else value


def _dispatch(document: Any) -> tuple:
    dispatch = document._oleobj_
    dispid = native_call("document-summary", "GetIDsOfNames(SummaryInfo)",
                         lambda: dispatch.GetIDsOfNames("SummaryInfo"))
    return dispatch, dispid


def _read(dispatch: Any, dispid: int, field: str) -> str:
    import pythoncom

    value = native_call("document-summary", "IModelDoc2.SummaryInfo.get",
                        lambda: dispatch.Invoke(dispid, 0, pythoncom.DISPATCH_PROPERTYGET,
                                                True, SUMMARY_FIELDS[field]))
    if not isinstance(value, str):
        raise RuntimeError(f"native summary field {field} did not return text")
    return _summary_text(field, value)


def read_document_summary_windows(*, app: Any, document: Any) -> dict:
    result = {"ok": False, "action": "document.summary"}
    try:
        state = _state(document)
        foreground = _com_value(app, "ActiveDoc")
        dispatch, dispid = _dispatch(document)
        fields = {field: _read(dispatch, dispid, field) for field in SUMMARY_FIELDS}
        path = _com_value(document, "GetPathName")
        history = native_call("document-summary", "ISldWorks.VersionHistory",
                              lambda: app.VersionHistory(path)) if path else ()
        if not isinstance(history, (tuple, list)) or any(not isinstance(item, str) for item in history):
            raise RuntimeError("native saved version history is unreadable")
        _verify_metadata_state(app, document, state, foreground, changed=False)
        result.update(ok=True, fields=fields, saved_version_history=list(history))
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def set_document_summary_windows(
    *, app: Any, document: Any, field: str, value: str, expected_value: Optional[str]
) -> dict:
    result = {"ok": False, "action": "document.summary-set", "field": field,
              "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        import pythoncom

        index = EDITABLE_SUMMARY_FIELDS[field]
        _require_writable(document)
        state = _state(document)
        foreground = _com_value(app, "ActiveDoc")
        dispatch, dispid = _dispatch(document)
        before = _read(dispatch, dispid, field)
        result["before_value"] = before
        if expected_value is not None and before != _summary_text(field, expected_value):
            raise ValueError(f"summary field {field} no longer matches the expected value")
        value = _summary_text(field, value)
        changed = before != value
        _verify_metadata_state(app, document, state, foreground, changed=False)
        if changed:
            result["mutation"] = {"attempted": True, "may_have_changed": True}
            native_call("document-summary", "IModelDoc2.SummaryInfo.put",
                        lambda: dispatch.Invoke(dispid, 0, pythoncom.DISPATCH_PROPERTYPUT,
                                                False, index, value))
            after = _read(dispatch, dispid, field)
            if after != value:
                raise RuntimeError("native summary field did not round-trip the requested value")
            _verify_metadata_state(app, document, state, foreground, changed=True)
        result.update(ok=True, changed=changed, value=value)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
