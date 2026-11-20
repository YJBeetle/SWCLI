"""One SW2025 IModelDocExtension.SaveAs3 call with explicit COM arguments."""

from typing import Any, Dict

from .native_trace import native_call
from .windows import _com_value

SAVE_AS_API = "IModelDocExtension.SaveAs3"
_UNWRITTEN = -2147483648


def save_as3(document: Any, output: str, *, receipt: Dict[str, Any], stage: str = "save-as") -> bool:
    """Retain actual outputs and attempted state, including on a COM exception.

    DumbDispatch keeps the explicit BYREF VARIANTs intact instead of applying
    generated wrapper output rewriting. Flagging the method prevents a dynamic
    property-get probe. No other save interface is invoked after a failure.
    """
    import pythoncom
    from win32com.client import VARIANT
    from win32com.client.dynamic import DumbDispatch

    for key in ("api_saved", "save_errors", "save_warnings"):
        receipt.pop(key, None)
    receipt["save_attempted"] = False
    extension = DumbDispatch(_com_value(document, "Extension"))
    extension._FlagAsMethod("SaveAs3")
    export_data = VARIANT(pythoncom.VT_DISPATCH, None)
    advanced_options = VARIANT(pythoncom.VT_DISPATCH, None)
    errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, _UNWRITTEN)
    warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, _UNWRITTEN)
    receipt["save_attempted"] = True
    try:
        returned = native_call(stage, SAVE_AS_API, lambda: extension.SaveAs3(
            str(output), 0, 1, export_data, advanced_options, errors, warnings))
        if type(returned) is not bool:
            raise RuntimeError("IModelDocExtension.SaveAs3 returned a non-boolean result")
        receipt["api_saved"] = returned
    finally:
        # Preserve written output codes even when the COM call itself raises.
        for name, output_code in (("save_errors", errors), ("save_warnings", warnings)):
            value = output_code.value
            if type(value) is int and value != _UNWRITTEN:
                receipt[name] = value
    if any(type(code.value) is not int or code.value == _UNWRITTEN for code in (errors, warnings)):
        raise RuntimeError("IModelDocExtension.SaveAs3 did not write both output codes")
    return returned
