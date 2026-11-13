"""Read-only linked font witnesses for owned candidate diagnostics only."""
from ..font_scope_candidates import NEXT_FONT_LINKED_READS
from ..font_snapshot import FONT_MEMBERS, font_snapshot
from .native_trace import native_call
from .windows import _com_value


def read_linked_font_defaults(document, constants, scope):
    if scope not in NEXT_FONT_LINKED_READS:
        raise ValueError("unknown next font scope")
    fonts, native = {}, {}
    extension = _com_value(document, "Extension")
    for label, (preference, option) in NEXT_FONT_LINKED_READS[scope].items():
        obj = native_call("document-font-scopes-linked", "IModelDocExtension.GetUserPreferenceTextFormat",
            lambda: extension.GetUserPreferenceTextFormat(constants[preference], constants[option]))
        if obj is None:
            raise RuntimeError("linked table font unavailable: " + label)
        def read(member):
            def value():
                result = getattr(obj, member)
                return result() if callable(result) else result
            return native_call("document-font-scopes-linked", "ITextFormat." + member + ".get", value)
        native[label] = {member: read(member) for member in FONT_MEMBERS.values()}
        fonts[label] = font_snapshot(native[label])
    return {"scope": scope, "status": "read-witness-only; inheritance not accepted",
            "fonts": fonts, "native_fonts": native}
