"""Nine document unit preferences with whole-profile CAS and finite write domains."""
from typing import Any
from ..document_unit_profile import (FIELDS, LINKAGE, CALIBRATED_UNIT_WRITES, snapshot,
    validate_snapshot, target, typed_key, fingerprint, require_scalar_source, verify_scalar_after)
from .native_trace import native_call
from .windows import _com_value, _error
from .windows_custom_properties import _state, _require_writable, _verify_metadata_state
from .windows_document_annotations import _edit_context, _verify_context, _writable_context
from .windows_feature_inspection import _same

class DocumentUnitProfileConflict(RuntimeError):
    """The complete source profile differs from the caller's observation."""

class UnitProfileCalibrationRequired(ValueError):
    """No independently calibrated native write domain is enabled."""


def _read_snapshot(document, kind):
    extension = _com_value(document, "Extension")
    raw = {f: native_call("document-unit-profile", "IModelDocExtension.GetUserPreferenceInteger",
              lambda s=s: extension.GetUserPreferenceInteger(s["id"], 0)) for f, s in FIELDS.items()}
    def units():
        member = getattr(document, "GetUnits")
        return member() if callable(member) else member
    units = native_call("document-unit-profile", "IModelDoc2.GetUnits", units)
    linkage = {n: native_call("document-unit-profile", "IModelDocExtension.GetUserPreference" + family,
                   lambda family=family, preference=preference: getattr(extension, "GetUserPreference" + family)(preference, 0))
               for n, (family, preference) in LINKAGE.items()}
    return snapshot(kind, raw, units, linkage)


def _identity(document):
    identity=(_com_value(document,'GetTitle'),_com_value(document,'GetPathName'))
    if any(type(value) is not str for value in identity) or not identity[0]:
        raise RuntimeError('native unit document identity is unreadable')
    return identity


def _foreground_snapshot(app,document):
    foreground=_com_value(app,'ActiveDoc')
    peer=foreground is not None and not _same(app,foreground,document)
    return dict(document=foreground,target_identity=_identity(document),
                state=_state(foreground) if peer else None,
                identity=_identity(foreground) if peer else None)


def _guard(app, document, state, foreground, edit, *, writable):
    active=foreground['document']
    _verify_context(app, document, edit)
    _verify_metadata_state(app, document, state, active, changed=False)
    if _identity(document)!=foreground['target_identity']:
        raise RuntimeError('unit operation changed target document identity')
    opened=_com_value(app,'GetDocuments')
    if type(opened) not in (list,tuple) or not any(_same(app,document,item) for item in opened):
        raise RuntimeError('unit target document is no longer open')
    if foreground['state'] is not None:
        if (not any(_same(app,active,item) for item in opened)
                or _state(active)!=foreground['state'] or _identity(active)!=foreground['identity']):
            raise RuntimeError('unit operation changed foreground peer state or identity')
    if writable: _require_writable(document)


def read_document_unit_profile_windows(*, app: Any, document: Any):
    result = {"ok": False, "action": "document.unit-profile"}
    try:
        state, foreground, edit = _state(document), _foreground_snapshot(app,document), _edit_context(document)
        value = _read_snapshot(document, state[0])
        _guard(app, document, state, foreground, edit, writable=False)
        result.update(ok=True, unit_profile=value)
    except Exception as error: result["error"] = _error(error)
    return result


def _edit(app, document, field, value, expected_snapshot, *, calibration=False):
    result = {"ok": False, "action": "document.unit-profile-set", "mutation": {"attempted": False, "may_have_changed": False}}
    try:
        native_target = target(field, value)
        expected = validate_snapshot(expected_snapshot)
        _require_writable(document)
        state, foreground, edit = _state(document), _foreground_snapshot(app,document), _edit_context(document)
        before = _read_snapshot(document, state[0]); result.update(field=field, before=before)
        if typed_key(before) != typed_key(expected): raise DocumentUnitProfileConflict("complete unit profile no longer matches expected snapshot")
        _guard(app, document, state, foreground, edit, writable=True)
        if before["values"][field]["native_value"] == native_target:
            result.update(ok=True, changed=False, unit_profile=before); return result
        if not _writable_context(app, edit): raise ValueError("unit editing requires normal sheet/model edit context")
        if field != "system" or not calibration: require_scalar_source(before, field)
        domain = (state[0], fingerprint(before), field, native_target)
        if not calibration and domain not in CALIBRATED_UNIT_WRITES:
            raise UnitProfileCalibrationRequired("this exact source/target/document-type write awaits native CI calibration")
        extension = _com_value(document, "Extension")
        _guard(app, document, state, foreground, edit, writable=True)
        result["mutation"] = {"attempted": True, "may_have_changed": True}
        returned = native_call("document-unit-profile", "IModelDocExtension.SetUserPreferenceInteger",
                               lambda: extension.SetUserPreferenceInteger(FIELDS[field]["id"], 0, native_target))
        result["native_return_value"] = returned
        if returned is not True: raise RuntimeError("native unit setter did not return True; no retry")
        post = _state(document)
        if state[2] and not post[2]:
            raise RuntimeError("native unit setter cleared an existing dirty flag")
        after = _read_snapshot(document, state[0]); result["observed"] = after
        _guard(app, document, post, foreground, edit, writable=True)
        if field == "system":
            if after["values"][field]["native_value"] != native_target: raise RuntimeError("native unit system did not round-trip")
        else: verify_scalar_after(before, after, field, native_target)
        if (post[0], post[3]) != (state[0], state[3]): raise RuntimeError("unit setter changed document context")
        # Mark once only after checking against the original context and the
        # known post-setter state. Never adopt drift introduced by getter calls.
        _guard(app, document, post, foreground, edit, writable=True)
        if not post[2]:
            native_call("document-unit-profile", "IModelDoc2.SetSaveFlag", lambda: document.SetSaveFlag())
        marked = _state(document)
        if not marked[2] or (marked[0], marked[3]) != (state[0], state[3]): raise RuntimeError("unit write did not preserve context and mark dirty")
        _guard(app, document, marked, foreground, edit, writable=True)
        final = _read_snapshot(document, state[0])
        _guard(app, document, marked, foreground, edit, writable=True)
        if typed_key(final) != typed_key(after): raise RuntimeError("unit profile drifted while marking dirty")
        result.update(ok=True, changed=True, unit_profile=after)
    except Exception as error: result["error"] = _error(error)
    return result


def set_document_unit_profile_windows(*, app: Any, document: Any, field, value, expected_snapshot):
    return _edit(app, document, field, value, expected_snapshot)


def _calibrate_unit_profile(app, document, field, value, expected_snapshot):
    """Private CI diagnostic only. Never registered or selectable by public params."""
    return _edit(app, document, field, value, expected_snapshot, calibration=True)
