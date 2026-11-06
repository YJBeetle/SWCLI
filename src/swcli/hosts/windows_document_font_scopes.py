"""Four scoped defaults, strict CAS, and internal-only native write calibration.

Public setters always fail closed until subtype/inheritance/public-gate evidence
is reviewed. No environment variable or protocol parameter enables writing.
"""

from functools import lru_cache
from pathlib import Path

from ..document_font_scopes import FONT_SCOPES, validate_font_scopes, validate_font_edit
from ..font_snapshot import (FONT_MEMBERS, font_snapshot, font_requested_value_matches,
                             font_native_normalizations)
from .native_trace import native_call
from .windows import _com_value, _error, _discover_com_registration
from .windows_custom_properties import _require_writable, _state, _verify_metadata_state
from .windows_document_annotations import _edit_context, _verify_context, _writable_context


class DocumentFontScopeConflict(RuntimeError):
    """Any field in any observed font scope changed before the mutation."""


class DocumentFontScopeNotCalibrated(RuntimeError):
    """Public writing is closed pending native and inheritance evidence."""


def read_font_constants(pythoncom, path):
    """Resolve symbolic IDs from the official swconst type library, never guess."""
    wanted = {name for pair in FONT_SCOPES.values() for name in pair}
    found = {}
    library = pythoncom.LoadTypeLib(str(path))
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attributes = info.GetTypeAttr()
        if attributes.typekind != pythoncom.TKIND_ENUM:
            continue
        for offset in range(attributes.cVars):
            descriptor = info.GetVarDesc(offset)
            name = info.GetDocumentation(descriptor[0])[0]
            if name in wanted:
                if name in found or type(descriptor.value) is not int:
                    raise RuntimeError("duplicate or unreadable official font enum")
                found[name] = descriptor.value
    if found.keys() != wanted:
        raise RuntimeError("official swconst type library lacks required font enums")
    return found


@lru_cache(maxsize=1)
def _installed_constants():
    import pythoncom
    import winreg
    registration = _discover_com_registration(winreg)
    executable = registration.get("local_server")
    if not executable or registration.get("local_server_exists") is not True:
        raise RuntimeError("registered SOLIDWORKS installation is unavailable")
    library = Path(executable).parent / "swconst.tlb"
    if not library.is_file():
        raise RuntimeError("registered SOLIDWORKS swconst.tlb is unavailable")
    return read_font_constants(pythoncom, library)


def _read_member(font, member):
    def read():
        value = getattr(font, member)
        return value() if callable(value) else value
    return native_call("document-font-scopes", "ITextFormat." + member + ".get", read)


def _read_fonts(document, constants):
    extension = _com_value(document, "Extension")
    objects, fonts, native = {}, {}, {}
    for scope, (preference, option) in FONT_SCOPES.items():
        obj = native_call("document-font-scopes", "IModelDocExtension.GetUserPreferenceTextFormat",
                          lambda: extension.GetUserPreferenceTextFormat(constants[preference], constants[option]))
        if obj is None:
            raise RuntimeError("native font scope unavailable: " + scope)
        objects[scope] = obj
        native[scope] = {member: _read_member(obj, member) for member in FONT_MEMBERS.values()}
        fonts[scope] = font_snapshot(native[scope])
    return objects, fonts, native


def _verify_identity(app, document, foreground, edit, state, identity, *, changed=False):
    if (_com_value(document, "GetPathName"), _com_value(document, "GetTitle")) != identity:
        raise RuntimeError("document font operation changed document identity")
    _verify_context(app, document, edit)
    _verify_metadata_state(app, document, state, foreground, changed=changed)


def read_document_font_scopes_windows(*, app, document):
    result = {"ok": False, "action": "document.font-scopes"}
    try:
        foreground, edit, state = _com_value(app, "ActiveDoc"), _edit_context(document), _state(document)
        identity = (_com_value(document, "GetPathName"), _com_value(document, "GetTitle"))
        _, fonts, _ = _read_fonts(document, _installed_constants())
        _verify_identity(app, document, foreground, edit, state, identity)
        result.update(ok=True, fonts=fonts)
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def set_document_font_scope_windows(*, app, document, scope, field, value, expected_fonts):
    """Public fail-closed boundary. Internal worker uses a separate function."""
    result = {"ok": False, "action": "document.font-scope-set",
              "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        validate_font_edit(scope, field, value, expected_fonts)
        _require_writable(document)
        raise DocumentFontScopeNotCalibrated("scoped font writes require native persistence and inheritance acceptance")
    except Exception as exc:
        result["error"] = _error(exc)
    return result


def _calibrate_set_document_font_scope(*, app, document, scope, field, value, expected_fonts):
    """Internal experiment only; caller MUST use the normal guarded dispatcher.

    Never exported as a protocol switch. Property assignment may mutate a live
    object, so the partial-mutation receipt starts before the first assignment.
    """
    result = {"ok": False, "action": "document.font-scope-set",
              "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        validate_font_edit(scope, field, value, expected_fonts)
        foreground, edit = _com_value(app, "ActiveDoc"), _edit_context(document)
        _require_writable(document)
        state = _state(document)
        identity = (_com_value(document, "GetPathName"), _com_value(document, "GetTitle"))
        constants = _installed_constants()
        _verify_identity(app, document, foreground, edit, state, identity)
        objects, before, native_before = _read_fonts(document, constants)
        result.update(scope=scope, field=field, before=before)
        if before != expected_fonts:
            raise DocumentFontScopeConflict("document font scopes no longer match the complete expected snapshot")
        _verify_identity(app, document, foreground, edit, state, identity)
        if font_requested_value_matches(before[scope], field, value):
            result.update(ok=True, changed=False, fonts=before)
            return result
        if not _writable_context(app, edit):
            raise ValueError("font editing requires a normal sheet or no active model sketch")
        member = FONT_MEMBERS[field]
        native_value = value / 1000.0 if field == "height_mm" else value
        _require_writable(document)
        _verify_identity(app, document, foreground, edit, state, identity)
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        native_call("document-font-scopes", "ITextFormat." + member + ".set",
                    lambda: setattr(objects[scope], member, native_value))
        _require_writable(document)
        property_state = _state(document)
        if (property_state[0], property_state[3]) != (state[0], state[3]):
            raise RuntimeError("font property assignment changed the document configuration")
        _verify_identity(app, document, foreground, edit, property_state, identity)
        preference, option = FONT_SCOPES[scope]
        returned = native_call("document-font-scopes", "IModelDocExtension.SetUserPreferenceTextFormat",
                               lambda: document.Extension.SetUserPreferenceTextFormat(
                                   constants[preference], constants[option], objects[scope]))
        if returned is not True:
            raise RuntimeError("native font scope setter did not return success")
        post = _state(document)
        _, after, native_after = _read_fonts(document, constants)
        result["observed_fonts"] = after
        _verify_identity(app, document, foreground, edit, post, identity)
        if not font_requested_value_matches(after[scope], field, value):
            raise RuntimeError("native font scope did not read back the requested value and mode")
        font_native_normalizations(native_before[scope], native_after[scope], member)
        if any(native_after[key] != native_before[key] for key in FONT_SCOPES if key != scope):
            raise RuntimeError("native font setter changed an unrequested scope")
        _require_writable(document)
        _verify_identity(app, document, foreground, edit, state, identity, changed=True)
        post = _state(document)
        _, final, native_final = _read_fonts(document, constants)
        if final != after or native_final != native_after:
            raise RuntimeError("font scopes changed while marking the document for saving")
        _verify_identity(app, document, foreground, edit, post, identity)
        result.update(ok=True, changed=True, fonts=after)
    except Exception as exc:
        result["error"] = _error(exc)
    return result
