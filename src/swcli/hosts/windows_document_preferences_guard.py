"""Fail-closed native-host and peer guards for the three document preference pairs."""
import ctypes
from ctypes import wintypes
import sys
from .windows import _com_value
from .windows_feature_inspection import _same
from .windows_custom_properties import _state, _require_writable
from .native_trace import native_call
from .windows_document_annotations import _edit_context, _verify_context
from ..document_drafting_standard import CALIBRATED_DRAFTING_WINDOWS_REVISIONS


def require_native_windows():
    message = 'document preferences require a proven native Windows runtime'
    if sys.platform != 'win32': raise ValueError(message)
    try:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        module = kernel.GetModuleHandleW
        module.argtypes = [wintypes.LPCWSTR]; module.restype = wintypes.HMODULE
        proc = kernel.GetProcAddress
        proc.argtypes = [wintypes.HMODULE, wintypes.LPCSTR]; proc.restype = ctypes.c_void_p
        handle = module('ntdll.dll')
        if not handle or not proc(handle, b'NtClose'): raise ValueError(message)
        ctypes.set_last_error(0)
        wine = proc(handle, b'wine_get_version')
        error = ctypes.get_last_error()
        if wine or error != 127: raise ValueError(message)
    except (AttributeError, OSError) as error:
        raise ValueError(message) from error


def require_calibrated_native_host(app):
    require_native_windows()
    revision = _com_value(app, 'RevisionNumber')
    if type(revision) is not str or revision not in CALIBRATED_DRAFTING_WINDOWS_REVISIONS:
        raise ValueError('document preferences require calibration for this native host revision')


def identity(document):
    title, path = _com_value(document, 'GetTitle'), _com_value(document, 'GetPathName')
    extension = _com_value(document, 'Extension')
    if type(title) is not str or not title or type(path) is not str or extension is None:
        raise RuntimeError('document identity is unreadable')
    return title, path, extension


def capture_foreground(app, document):
    foreground = _com_value(app, 'ActiveDoc')
    target = identity(document)
    peer = None
    if foreground is not None and not _same(app, foreground, document):
        peer = (_state(foreground), identity(foreground), _edit_context(foreground),
                _com_value(foreground, 'IsOpenedReadOnly'), _com_value(foreground, 'IsOpenedViewOnly'))
        if any(type(value) is not bool for value in peer[3:]): raise RuntimeError('foreground peer permissions unreadable')
    guard = (foreground, target, peer)
    verify_foreground(app, document, guard)
    return guard


def verify_foreground(app, document, guard):
    foreground, target, peer = guard
    if not _same(app, foreground, _com_value(app, 'ActiveDoc')): raise RuntimeError('foreground changed')
    observed = identity(document)
    if observed[:2] != target[:2] or not _same(app, observed[2], target[2]): raise RuntimeError('target identity changed')
    if peer is not None:
        state, prior, context, readonly, viewonly = peer
        observed = identity(foreground)
        if (_state(foreground) != state or observed[:2] != prior[:2]
                or not _same(app, observed[2], prior[2])
                or _com_value(foreground, 'IsOpenedReadOnly') is not readonly
                or _com_value(foreground, 'IsOpenedViewOnly') is not viewonly):
            raise RuntimeError('foreground peer state/identity changed')
        _verify_context(app, foreground, context)
    if not _same(app, foreground, _com_value(app, 'ActiveDoc')): raise RuntimeError('foreground changed during verification')


def verify_metadata_state(app, document, before, foreground, *, changed, require_writable=False):
    verify_foreground(app, document, foreground)
    after = _state(document)
    stable = (after[0], after[3]) == (before[0], before[3]) if changed else after == before
    if not stable: raise RuntimeError('document state changed during metadata operation')
    verify_foreground(app, document, foreground)
    if changed and not after[2]:
        if require_writable: _require_writable(document)
        verify_foreground(app, document, foreground)
        native_call('document-metadata', 'IModelDoc2.SetSaveFlag', lambda: document.SetSaveFlag())
        final = _state(document)
        verify_foreground(app, document, foreground)
        if not final[2] or (final[0], final[3]) != (before[0], before[3]):
            raise RuntimeError('metadata write did not preserve context and mark dirty')
    verify_foreground(app, document, foreground)
