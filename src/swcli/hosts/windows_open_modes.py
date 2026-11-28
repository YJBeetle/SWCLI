"""Open an explicit SOLIDWORKS mode and report read-only native observations."""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

from .native_trace import native_call
from .windows import _com_value, _dispatch, _error


_OWNED_HOST = ContextVar("open_modes_owned_host", default=False)


class OpenModeError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@contextmanager
def open_modes_host_scope(owned):
    token = _OWNED_HOST.set(owned)
    try:
        yield
    finally:
        _OWNED_HOST.reset(token)


def _bool(value, member):
    if type(value) is not bool:
        raise RuntimeError(f"unreadable SOLIDWORKS {member}")
    return value


@lru_cache(maxsize=4)
def _large_settings_enum(path):
    import pythoncom

    library = pythoncom.LoadTypeLib(path)
    for index in range(library.GetTypeInfoCount()):
        info = library.GetTypeInfo(index)
        attributes = info.GetTypeAttr()
        if (attributes.typekind == pythoncom.TKIND_ENUM
                and info.GetDocumentation(-1)[0] == "swUserPreferenceToggle_e"):
            for offset in range(attributes.cVars):
                descriptor = info.GetVarDesc(offset)
                if info.GetDocumentation(descriptor[0])[0] == "swLargeAsmModeEnabled":
                    if type(descriptor.value) is int:
                        return descriptor.value
    raise RuntimeError("official swconst lacks swLargeAsmModeEnabled")


def _large_settings_key(app):
    install = Path(_com_value(app, "GetExecutablePath"))
    folder = install.parent if install.suffix.lower() == ".exe" else install
    return _large_settings_enum(str(folder / "swconst.tlb"))


@contextmanager
def _large_settings(app, value, result):
    if value is None:
        yield
        return

    if not _OWNED_HOST.get():
        raise OpenModeError("OwnedHostRequired", "large assembly settings require a daemon-owned host")
    key = _large_settings_key(app)

    def read():
        value = native_call("document-open", "GetUserPreferenceToggle.swLargeAsmModeEnabled",
                            lambda: app.GetUserPreferenceToggle(key))
        return _bool(value, "swLargeAsmModeEnabled")

    def write(target):
        # ISldWorks.SetUserPreferenceToggle returns void. Use the native readback.
        native_call("document-open", "SetUserPreferenceToggle.swLargeAsmModeEnabled",
                    lambda: app.SetUserPreferenceToggle(key, target))
        if read() is not target:
            raise RuntimeError("SOLIDWORKS did not accept the large assembly preference")

    before = read()
    state = {"before": before, "restored": False}
    result["open_mode"]["large_assembly_settings"] = state
    attempted = before is not value
    try:
        if attempted:
            write(value)
        state["during_open"] = value
        yield
    finally:
        try:
            if attempted:
                write(before)
            state["after_open"] = read()
            if state["after_open"] is not before:
                raise RuntimeError("large assembly preference changed during open")
            state["restored"] = True
        except Exception as exc:
            # Keep the business fault, if any. The daemon quarantines a host
            # whose requested preference could not be restored.
            error = _error(exc)
            result["preference_restore_errors"] = [error]


def _actual_from_counts(lightweight, resolved):
    if lightweight:
        return "mixed" if resolved else "lightweight"
    return "resolved" if resolved else "unknown"


def _observe_assembly(document, observed):
    state = _com_value(document, "GetLargeDesignReviewState")
    if type(state) is not int or state not in (0, 1, 2):
        raise RuntimeError("unknown SOLIDWORKS Large Design Review state")
    observed["large_design_review_state"] = state
    if state:
        return "large-design-review"

    components = native_call("document-open", "IAssemblyDoc.GetComponents",
                             lambda: document.GetComponents(False)) or ()
    suppressed = resolved = lightweight = 0
    for component in components:
        state = _com_value(component, "GetSuppression2")
        if type(state) is not int or state not in (0, 1, 2, 3, 4):
            raise RuntimeError("unreadable component suppression state")
        if state == 0:
            suppressed += 1
        elif state in (1, 4):
            lightweight += 1
        else:
            resolved += 1
    observed.update(lightweight_count=lightweight, resolved_count=resolved, suppressed_count=suppressed)
    return _actual_from_counts(lightweight, resolved)


def _observe_drawing(document, observed):
    detailing = _bool(_com_value(document, "IsDetailingMode"), "IsDetailingMode")
    observed["detailing_mode"] = detailing
    if detailing:
        return "detailing"
    if observed["view_only"]:
        return "unknown"

    lightweight = resolved = unloaded = 0
    for group in _com_value(document, "GetViews") or ():
        for raw_view in group[1:]:
            view = _dispatch(raw_view)
            if _bool(_com_value(view, "IsLightweight"), "IView.IsLightweight"):
                lightweight += 1
            elif _bool(_com_value(view, "IsModelLoaded"), "IView.IsModelLoaded"):
                resolved += 1
            else:
                unloaded += 1
    observed.update(lightweight_count=lightweight, resolved_count=resolved, unloaded_count=unloaded)
    return "unknown" if unloaded else _actual_from_counts(lightweight, resolved)



def _observe(document, document_type, result):
    observed = result["open_mode"]
    try:
        observed["view_only"] = _bool(_com_value(document, "IsOpenedViewOnly"), "IsOpenedViewOnly")
        observed["actual_read_only"] = _bool(_com_value(document, "IsOpenedReadOnly"), "IsOpenedReadOnly")
        if document_type == 1:
            actual = "quick-view" if observed["view_only"] else "resolved"
        elif document_type == 2:
            actual = _observe_assembly(document, observed)
        else:
            actual = _observe_drawing(document, observed)
        observed["actual"] = actual
        if actual != "unknown":
            observed["matches_request"] = actual == observed["requested"]
        if document_type == 2 and actual != "large-design-review":
            options = observed["options"]
            if "load_hidden_components" in options:
                observed["has_unloaded_components"] = _bool(
                    _com_value(document, "HasUnloadedComponents"), "HasUnloadedComponents")
            if "use_speedpak" in options:
                components = native_call("document-open", "IAssemblyDoc.GetComponents",
                                         lambda: document.GetComponents(False)) or ()
                observed["speedpak_count"] = sum(
                    _bool(_com_value(component, "IsSpeedPak"), "IComponent2.IsSpeedPak")
                    for component in components
                )
    except Exception as exc:
        observed["observation_error"] = _error(exc)


def open_explicit_document(app, path, document_type, mode, options, read_only, configuration, result):
    result["open_mode"] = {
        "requested": mode, "actual": "unknown", "matches_request": None, "options": dict(options),
    }
    already_open = native_call("document-open", "GetOpenDocumentByName",
                               lambda: app.GetOpenDocumentByName(str(path)))
    if already_open is not None:
        raise OpenModeError("DocumentAlreadyOpen", "close the document before requesting an explicit open mode")

    spec = native_call("document-open", "GetOpenDocSpec", lambda: app.GetOpenDocSpec(str(path)))
    if spec is None:
        raise OpenModeError("OpenFailed", "SOLIDWORKS returned no document specification")

    flags = {"DocumentType": document_type, "ReadOnly": read_only, "Silent": True}
    if configuration:
        flags["ConfigurationName"] = configuration
    if document_type in (2, 3):
        flags.update(UseLightWeightDefault=False, LightWeight=mode == "lightweight")
    if document_type == 1:
        flags["Selective"] = mode == "quick-view"
        flags["ViewOnly"] = mode == "quick-view"
    if document_type == 2:
        flags["ViewOnly"] = mode == "large-design-review"
    if document_type == 3:
        flags["DetailingMode"] = mode == "detailing"
    if "load_hidden_components" in options:
        # Despite the property name, True loads hidden components.
        flags["IgnoreHiddenComponents"] = options["load_hidden_components"]
    if "use_speedpak" in options:
        flags["UseSpeedPak"] = options["use_speedpak"]
    for name, value in flags.items():
        native_call("document-open", "IDocumentSpecification." + name,
                    lambda: setattr(spec, name, value))

    with _large_settings(app, options.get("use_large_assembly_settings"), result):
        document = native_call("document-open", "SldWorks.OpenDoc7", lambda: app.OpenDoc7(spec))
        result["api_errors"] = int(_com_value(spec, "Error"))
        result["api_warnings"] = int(_com_value(spec, "Warning"))
        if document is not None:
            _observe(document, document_type, result)
    return document
