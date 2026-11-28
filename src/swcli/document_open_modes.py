"""Public opening modes and the combinations supported by document.open."""

from pathlib import PureWindowsPath


MODES_BY_EXTENSION = {
    ".sldprt": ("resolved", "quick-view"),
    ".slddrw": ("resolved", "lightweight", "detailing"),
    ".sldasm": ("resolved", "lightweight", "large-design-review"),
}
OPEN_MODES = ("resolved", "lightweight", "large-design-review", "detailing", "quick-view")
ASSEMBLY_OPEN_OPTIONS = ("load_hidden_components", "use_speedpak", "use_large_assembly_settings")


def validate_open_mode(path, mode, options, *, configuration=""):
    if mode is None and not options:
        return
    extension = PureWindowsPath(path).suffix.casefold()
    if extension not in MODES_BY_EXTENSION:
        raise ValueError("explicit open modes require an SLDPRT, SLDASM or SLDDRW file")
    if mode is not None and mode not in MODES_BY_EXTENSION[extension]:
        raise ValueError(f"{extension} open mode must be one of {', '.join(MODES_BY_EXTENSION[extension])}")
    if options and (extension != ".sldasm" or mode not in ("resolved", "lightweight")):
        raise ValueError("assembly open options require an SLDASM with resolved or lightweight mode")
    if configuration and (extension == ".slddrw" or mode == "large-design-review"):
        raise ValueError("configuration cannot be combined with this explicit open mode")


def open_mode_conditions():
    """Publish extension/mode compatibility in the protocol and MCP schema."""
    extensions = {
        extension: {"pattern": r"\." + "".join(f"[{c}{c.upper()}]" for c in extension[1:]) + "$"}
        for extension in MODES_BY_EXTENSION
    }
    return [
        {
            "if": {"required": ["mode"]},
            "then": {"anyOf": [
                {"properties": {"path": extensions[extension], "mode": {"enum": list(modes)}}}
                for extension, modes in MODES_BY_EXTENSION.items()
            ]},
        },
        {
            "if": {"anyOf": [{"required": [name]} for name in ASSEMBLY_OPEN_OPTIONS]},
            "then": {"required": ["mode"], "properties": {
                "path": extensions[".sldasm"], "mode": {"enum": ["resolved", "lightweight"]},
            }},
        },
        {
            "if": {"required": ["mode", "configuration"], "anyOf": [
                {"properties": {"path": extensions[".slddrw"]}},
                {"properties": {"mode": {"const": "large-design-review"}}},
            ]},
            "then": {"properties": {"configuration": {"const": ""}}},
        },
    ]
