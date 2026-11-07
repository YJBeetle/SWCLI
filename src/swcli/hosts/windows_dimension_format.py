"""Document-only dimension display operations, with complete-value CAS."""

import ctypes
import sys

from ..document_dimension_format import (
    DIMENSION_FORMAT_FIELDS, CALIBRATED_DOCUMENT_TYPES, CALIBRATED_HOST_REVISIONS, POSITIONS, native_value, validate_format,
)
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _require_writable, _state, _verify_metadata_state
from .windows_document_annotations import _edit_context, _verify_context, _writable_context, _read_options
from .windows_document_units import _read_units
from .windows_feature_inspection import _same


class DocumentDimensionFormatConflict(RuntimeError):
    """The complete display snapshot differs from the caller's observation."""


class DimensionFormatNotCalibrated(RuntimeError):
    """New native display writes remain closed until public acceptance."""


def _native_windows():
    if sys.platform != "win32":
        return False
    try:
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True)
        module = kernel.GetModuleHandleW
        module.argtypes = [wintypes.LPCWSTR]
        module.restype = wintypes.HMODULE
        lookup = kernel.GetProcAddress
        lookup.argtypes = [wintypes.HMODULE, wintypes.LPCSTR]
        lookup.restype = ctypes.c_void_p
        ntdll = module("ntdll.dll")
        if not ntdll or not lookup(ntdll, b"NtClose"):
            return False
        ctypes.set_last_error(0)
        wine = lookup(ntdll, b"wine_get_version")
        error = ctypes.get_last_error()
        return not wine and error == 127  # ERROR_PROC_NOT_FOUND
    except Exception:
        return False


def _read_format(document):
    extension = _com_value(document, "Extension")
    values = {}
    for field, spec in DIMENSION_FORMAT_FIELDS.items():
        method = "GetUserPreference" + spec["kind"]
        value = native_call("document-dimension-format", "IModelDocExtension." + method,
                            lambda spec=spec, method=method: getattr(extension, method)(
                                spec["preference"], spec["option"]))
        expected = int if spec["kind"] == "Integer" else bool
        if type(value) is not expected:
            raise RuntimeError("unreadable native dimension display field " + field)
        values[field] = value
    return values


def _identity(document):
    title, path = _com_value(document, "GetTitle"), _com_value(document, "GetPathName")
    extension = _com_value(document, "Extension")
    if type(title) is not str or not title or type(path) is not str or extension is None:
        raise RuntimeError("native document identity is unreadable")
    return title, path, extension


def _foreground_snapshot(app, document, foreground):
    if foreground is None or _same(app, document, foreground):
        return None
    return _state(foreground), _identity(foreground)


def _verify(app, document, state, foreground, edit, identity, foreground_snapshot, *, changed=False):
    current = _identity(document)
    if current[:2] != identity[:2] or not _same(app, current[2], identity[2]):
        raise RuntimeError("document identity changed during dimension display operation")
    if foreground_snapshot is not None:
        peer_state, peer_identity = foreground_snapshot
        current_peer = _identity(foreground)
        if (_state(foreground) != peer_state or current_peer[:2] != peer_identity[:2]
                or not _same(app, current_peer[2], peer_identity[2])):
            raise RuntimeError("foreground document state or identity changed during dimension display operation")
    _verify_context(app, document, edit)
    _verify_metadata_state(app, document, state, foreground, changed=changed)


def read_dimension_format_windows(*, app, document):
    result = {"ok": False, "action": "document.dimension-format"}
    try:
        state, foreground = _state(document), _com_value(app, "ActiveDoc")
        edit, identity = _edit_context(document), _identity(document)
        foreground_snapshot = _foreground_snapshot(app, document, foreground)
        values = _read_format(document)
        _verify(app, document, state, foreground, edit, identity, foreground_snapshot)
        result.update(ok=True, format=values)
    except Exception as error:
        result["error"] = _error(error)
    return result


def set_dimension_format_windows(*, app, document, field, value, expected_format,
                                 _calibration=False):
    # _calibration is private to the owned fixture harness; never a wire field.
    result = {"ok": False, "action": "document.dimension-format-set", "field": field,
              "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        desired_value = native_value(field, value)
        validate_format(expected_format)
        _require_writable(document)
        state, foreground = _state(document), _com_value(app, "ActiveDoc")
        edit, identity = _edit_context(document), _identity(document)
        foreground_snapshot = _foreground_snapshot(app, document, foreground)
        before = _read_format(document)
        result["before"] = before
        if before != expected_format:
            raise DocumentDimensionFormatConflict("dimension display snapshot no longer matches expected_format")
        _verify(app, document, state, foreground, edit, identity, foreground_snapshot)
        if before[field] == desired_value:
            result.update(ok=True, format=before, changed=False)
            return result
        if before["dual_position"] not in POSITIONS.values():
            raise ValueError("the native dimension position is outside the calibrated profile")
        if not _writable_context(app, edit):
            raise ValueError("dimension display editing requires a normal sheet or no active model sketch")
        if not _calibration and (state[0] not in CALIBRATED_DOCUMENT_TYPES
                or _com_value(app, "RevisionNumber") not in CALIBRATED_HOST_REVISIONS
                or not _native_windows()):
            raise DimensionFormatNotCalibrated("dimension display writes lack installed public acceptance; native setter disabled")
        # Preserve independently owned units and existing annotation/zero fields.
        units, annotations = _read_units(document), _read_options(document)
        _verify(app, document, state, foreground, edit, identity, foreground_snapshot)
        if _read_format(document) != before:
            raise DocumentDimensionFormatConflict("dimension display changed before native setter")
        _require_writable(document)
        _verify(app, document, state, foreground, edit, identity, foreground_snapshot)
        desired = {**before, field: desired_value}
        spec = DIMENSION_FORMAT_FIELDS[field]
        method = "SetUserPreference" + spec["kind"]
        extension = identity[2]
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        returned = native_call("document-dimension-format", "IModelDocExtension." + method,
                               lambda: getattr(extension, method)(spec["preference"], spec["option"], desired_value))
        if type(returned) is bool:
            result["native_return"] = returned
        # Existing Windows 2025 annotation calibration returns True even for
        # Toggle(False). Fail closed on False; never retry or roll back.
        if returned is not True:
            raise RuntimeError("dimension display setter did not return success")
        post = _state(document)
        if state[2] and not post[2]:
            raise RuntimeError("dimension display setter cleared an existing dirty flag")
        _require_writable(document)
        after = _read_format(document)
        result["format"] = after
        if after != desired:
            raise RuntimeError("dimension display readback differs from the complete requested profile")
        if _read_units(document) != units:
            raise RuntimeError("dimension display setter changed protected document units")
        if _read_options(document) != annotations:
            raise RuntimeError("dimension display setter changed protected annotation/zero fields")
        _verify(app, document, post, foreground, edit, identity, foreground_snapshot)
        _verify(app, document, state, foreground, edit, identity, foreground_snapshot, changed=True)
        post = _state(document)
        if _read_format(document) != after or _read_units(document) != units or _read_options(document) != annotations:
            raise RuntimeError("dimension display changed while marking document for saving")
        _verify(app, document, post, foreground, edit, identity, foreground_snapshot)
        result.update(ok=True, format=after, changed=True)
    except Exception as error:
        result["error"] = _error(error)
    return result
