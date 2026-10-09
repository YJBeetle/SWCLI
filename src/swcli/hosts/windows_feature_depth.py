"""Internal depth-edit preflight; not a public setter or edit authority.

This first guard deliberately refuses multi-configuration parts and any part
containing equations/design tables. Narrowing those controls requires separate
native ownership/scope proof, not guessing a depth dimension by name.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .native_trace import native_call
from .windows import _com_value
from .windows_feature_inspection import (
    _FeatureError,
    _boolean,
    _integer,
    _observe,
    _read_exact_extrusion,
    _state,
    _string,
)

_CURRENT_CONFIGURATION = 1


def _empty_variant():
    import pythoncom
    from win32com.client import VARIANT

    return VARIANT(pythoncom.VT_EMPTY, None)


def _running_command(app: Any) -> Dict[str, Any]:
    import pythoncom
    from win32com.client import VARIANT

    unset = "__swcli_command_output_unset__"
    command_id = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, -2147483648)
    title = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, unset)
    active = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, True)
    native_call(
        "feature-depth-preflight",
        "SldWorks.GetRunningCommandInfo",
        lambda: app.GetRunningCommandInfo(command_id, title, active),
    )
    ui_active = _boolean(active.value, "command UI active")
    id_unset = command_id.value == -2147483648
    title_unset = title.value is None or title.value == unset
    if ui_active and (id_unset or title_unset):
        raise _FeatureError(
            "FeatureObservationUnavailable", "native command outputs are unreadable"
        )
    if not title_unset and not isinstance(title.value, str):
        raise _FeatureError(
            "FeatureObservationUnavailable", "native command title is unreadable"
        )
    # Native SW2025 explicitly writes ui_active=False and command_id=-3 while
    # leaving PMTitle untouched at idle. Do not invent a title/ID, or treat
    # untouched outputs as idle proof: active starts True and must become False.
    return {
        "command_id": None if id_unset else _integer(command_id.value, "command ID"),
        "title": None if title_unset else title.value,
        "ui_active": ui_active,
    }


def _controls(app: Any, document: Any, feature: Any) -> Dict[str, Any]:
    names = _com_value(document, "GetConfigurationNames")
    count = _integer(
        _com_value(document, "GetConfigurationCount"), "configuration count"
    )
    if (
        not isinstance(names, (list, tuple))
        or not 1 <= count <= 10000
        or len(names) != count
        or any(not isinstance(name, str) or not name.strip() for name in names)
        or len(set(names)) != count
    ):
        raise _FeatureError(
            "FeatureObservationUnavailable", "native configuration list is incomplete"
        )
    current = _state(app, document)[0]["configuration"]
    if current not in names:
        raise _FeatureError(
            "FeatureObservationUnavailable",
            "current configuration is not in native list",
        )
    equation_manager = _com_value(document, "GetEquationMgr")
    if equation_manager is None:
        raise _FeatureError(
            "FeatureObservationUnavailable", "native equation manager is unavailable"
        )
    equation_count = _integer(
        _com_value(equation_manager, "GetCount"), "equation count"
    )
    if not 0 <= equation_count <= 10000:
        raise _FeatureError(
            "FeatureObservationUnavailable", "native equation count is invalid"
        )
    suppression = native_call(
        "feature-depth-preflight",
        "Feature.IsSuppressed2",
        lambda: feature.IsSuppressed2(_CURRENT_CONFIGURATION, _empty_variant()),
    )
    if (
        not isinstance(suppression, (tuple, list))
        or len(suppression) != 1
        or type(suppression[0]) is not bool
    ):
        raise _FeatureError(
            "FeatureObservationUnavailable",
            "current-configuration suppression is unreadable",
        )
    return {
        "configuration": _string(current, "configuration"),
        "configurations": list(names),
        "equation_count": equation_count,
        "has_design_table": _boolean(
            _com_value(_com_value(document, "Extension"), "HasDesignTable"),
            "HasDesignTable",
        ),
        "read_only": _boolean(
            _com_value(document, "IsOpenedReadOnly"), "IsOpenedReadOnly"
        ),
        "view_only": _boolean(
            _com_value(document, "IsOpenedViewOnly"), "IsOpenedViewOnly"
        ),
        "suppressed": suppression[0],
        "frozen": _boolean(_com_value(feature, "IsFrozen"), "IsFrozen"),
        "rolled_back": _boolean(_com_value(feature, "IsRolledBack"), "IsRolledBack"),
        "command": _running_command(app),
    }


def _require_depth_scope(definition: Dict[str, Any], controls: Dict[str, Any]) -> None:
    if controls["read_only"] or controls["view_only"]:
        raise _FeatureError(
            "DocumentNotWritable", "depth editing requires a writable part"
        )
    if controls["command"]["ui_active"]:
        raise _FeatureError(
            "NativeCommandInProgress",
            "finish the existing command/PropertyManager before editing depth",
        )
    if controls["suppressed"] or controls["frozen"] or controls["rolled_back"]:
        raise _FeatureError(
            "FeatureProtectedState",
            "do not unsuppress, unfreeze or roll forward a protected feature",
        )
    if controls["has_design_table"] or controls["equation_count"]:
        raise _FeatureError(
            "FeatureControlScopeUnsupported",
            "the first depth slice refuses any part with equations/design tables; it does not infer parameter ownership",
        )
    if len(controls["configurations"]) != 1:
        raise _FeatureError(
            "FeatureConfigurationScopeUnsupported",
            "multi-configuration depth changes require separate native scope proof",
        )
    if (
        definition["depth_mm"] <= 0
        or definition["end_condition"] != 0
        or definition["both_directions"]
        or definition["thin"]
        or definition["from_type"] != 0
        or definition["forward_draft"]
        or definition["reverse_draft"]
    ):
        raise _FeatureError(
            "UnsupportedDepthDefinition",
            "only positive-depth, single-direction solid blind extrusions from the sketch plane are in scope",
        )


def prepare_extrusion_depth_edit_windows_with_definition(
    *, app: Any, document: Any, feature: Any
) -> Tuple[Dict[str, Any], Optional[Any]]:
    """Observe preliminary controls without selection access or native mutation.

    The eventual setter must also own/verify profile, body/configuration scope,
    selection-access restoration, rebuild and native readback. This result is
    deliberately not advertised as a public editing capability.
    """

    def read():
        state = _state(app, document)[0]
        if state["editing"]:
            raise _FeatureError(
                "SketchEditInProgress", "finish the existing sketch edit"
            )
        payload, native_definition = _read_exact_extrusion(app, document, feature)
        controls = _controls(app, document, feature)
        _require_depth_scope(payload["definition"], controls)
        # Protected state and definition must remain stable during the guard;
        # neither a single truthy COM value nor an old snapshot grants a write.
        repeated, _ = _read_exact_extrusion(app, document, feature)
        repeated_controls = _controls(app, document, feature)
        if repeated != payload or repeated_controls != controls:
            raise _FeatureError(
                "FeatureObservationUnavailable",
                "feature definition or controls changed during preflight",
            )
        payload["controls"] = controls
        return payload, [native_definition]

    result, handles = _observe(
        action="feature.depth-preflight", app=app, document=document, read=read
    )
    return result, handles[0] if handles else None
