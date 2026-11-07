"""Document annotation font snapshot and single-field write catalog.

The font read/write operations are wired into the CLI and daemon. This batch's
native and public acceptance remains in progress; font subtype independence
and complete persistence evidence have not been established.
"""

from math import isclose, isfinite


ANNOTATION_FONT_PREFERENCE = {"preference": 19, "option": 0}
# Native names are retained alongside the normalized, JSON-compatible snapshot.
ANNOTATION_FONT_MEMBERS = {
    "typeface": "TypeFaceName", "height_mm": "CharHeight",
    "height_points": "CharHeightInPts", "height_mode": "IsHeightSpecifiedInPts",
    "bold": "Bold", "italic": "Italic", "underline": "Underline", "strikeout": "Strikeout",
    "backwards": "BackWards", "upside_down": "UpsideDown", "vertical": "Vertical",
    "width_factor": "WidthFactor", "char_spacing_factor": "CharSpacingFactor",
    "escapement": "Escapement", "line_spacing": "LineSpacing",
    "line_length": "LineLength", "oblique_angle": "ObliqueAngle",
}
ANNOTATION_FONT_WRITABLE_FIELDS = (
    "typeface", "height_mm", "height_points", "bold", "italic", "underline", "strikeout",
)
_BOOL_FIELDS = frozenset(("bold", "italic", "underline", "strikeout", "backwards", "upside_down", "vertical"))
_DOUBLE_FIELDS = frozenset(("height_mm", "width_factor", "char_spacing_factor", "escapement",
                            "line_spacing", "line_length", "oblique_angle"))
_HEIGHT_FIELDS = frozenset(("height_mm", "height_points", "height_mode"))


def _finite_number(value):
    try:
        return type(value) in (int, float) and isfinite(value)
    except OverflowError:
        return False


def validate_annotation_font_value(field, value):
    if field not in ANNOTATION_FONT_WRITABLE_FIELDS:
        raise ValueError("unsupported document annotation font field")
    if field in _BOOL_FIELDS:
        valid = type(value) is bool
    elif field == "typeface":
        valid = (type(value) is str and bool(value.strip()) and value == value.strip()
                 and not any(ord(character) < 32 or ord(character) == 127 for character in value))
    elif field == "height_points":
        valid = type(value) is int and 0 < value <= 2147483647
    else:
        valid = _finite_number(value) and value > 0 and value / 1000.0 > 0
    if not valid:
        raise ValueError(f"unsupported value for document annotation font field {field}")
    return value


def validate_annotation_font_snapshot(font):
    """Reject incomplete, extra, wrongly typed or non-finite CAS observations."""
    if type(font) is not dict or font.keys() != ANNOTATION_FONT_MEMBERS.keys():
        raise ValueError("expected annotation font must contain the complete 17-field snapshot")
    for field, value in font.items():
        if field in _BOOL_FIELDS:
            valid = type(value) is bool
        elif field in _DOUBLE_FIELDS:
            valid = _finite_number(value)
            if field == "height_mm":
                valid = valid and value > 0 and value / 1000.0 > 0
        elif field == "height_points":
            # The alternate representation may be truncated, including zero.
            valid = type(value) is int and 0 <= value <= 2147483647
        elif field == "height_mode":
            valid = type(value) is str and value in ("millimeters", "points")
        else:
            valid = type(value) is str
        if not valid:
            raise ValueError(f"invalid annotation font snapshot field {field}")
    if font["height_mode"] == "points" and font["height_points"] <= 0:
        raise ValueError("annotation font point height must be positive in points mode")
    return font


def annotation_font_snapshot(native):
    if type(native) is not dict or native.keys() != set(ANNOTATION_FONT_MEMBERS.values()):
        raise ValueError("native annotation font snapshot is incomplete")
    if type(native["IsHeightSpecifiedInPts"]) is not bool:
        raise ValueError("native annotation font height mode is unreadable")
    # Validate before multiplying: bool must never become a plausible height.
    if not _finite_number(native["CharHeight"]):
        raise ValueError("native annotation font height is unreadable")
    font = {field: native[member] for field, member in ANNOTATION_FONT_MEMBERS.items()}
    font["height_mm"] = native["CharHeight"] * 1000.0
    font["height_mode"] = "points" if native["IsHeightSpecifiedInPts"] else "millimeters"
    return validate_annotation_font_snapshot(font)


def annotation_font_matches(actual, expected):
    """Exact full-snapshot CAS; no float tolerance can hide an intervening edit."""
    validate_annotation_font_snapshot(actual)
    validate_annotation_font_snapshot(expected)
    return actual == expected


def annotation_font_requested_value_matches(font, field, value):
    if field == "height_mm":
        return (font["height_mode"] == "millimeters"
                and isclose(font[field], value, rel_tol=1e-12, abs_tol=1e-12))
    if field == "height_points":
        return font["height_mode"] == "points" and font[field] == value
    return type(font[field]) is type(value) and font[field] == value


def annotation_font_unrequested_fields_match(before, after, field):
    validate_annotation_font_snapshot(before)
    validate_annotation_font_snapshot(after)
    if field not in ANNOTATION_FONT_WRITABLE_FIELDS:
        raise ValueError("unsupported document annotation font field")
    if field in _HEIGHT_FIELDS:
        allowed = _HEIGHT_FIELDS
    else:
        if after["height_mode"] != before["height_mode"]:
            return False
        inactive = "height_mm" if before["height_mode"] == "points" else "height_points"
        allowed = {field, inactive}
    return all(type(after[key]) is type(before[key]) and after[key] == before[key]
               for key in before if key not in allowed)


def annotation_font_native_normalizations(before, after, member):
    """Validate native side effects and report only inactive-height changes.

    Inputs are complete 17-member native snapshots. The requested target value
    must be verified separately. For non-height writes, mode and active height
    remain exactly unchanged; all other members except the target and inactive
    height are also exact. Height writes may change the height triplet and
    preserve the other 14 members. This helper also serves a pre-final-Set Get
    that may still observe the old height mode. The final requested-value
    matcher must independently require the target value and explicit mode.

    No conversion/rounding formula is inferred. A normalization records native
    observations, not an explanation of font metrics or persistence proof.
    """
    annotation_font_snapshot(before)
    annotation_font_snapshot(after)
    writable_members = {ANNOTATION_FONT_MEMBERS[field] for field in ANNOTATION_FONT_WRITABLE_FIELDS}
    if type(member) is not str or member not in writable_members:
        raise ValueError("unsupported native annotation font member")
    height_members = {"CharHeight", "CharHeightInPts", "IsHeightSpecifiedInPts"}
    if member in ("CharHeight", "CharHeightInPts"):
        allowed = height_members
    else:
        if after["IsHeightSpecifiedInPts"] is not before["IsHeightSpecifiedInPts"]:
            raise ValueError("native annotation font setter changed an unrequested height mode")
        inactive = "CharHeight" if before["IsHeightSpecifiedInPts"] else "CharHeightInPts"
        allowed = {member, inactive}
    if any(type(after[key]) is not type(before[key]) or after[key] != before[key]
           for key in before if key not in allowed):
        raise ValueError("native annotation font setter changed an unrequested field or active height")
    inactive = "CharHeight" if after["IsHeightSpecifiedInPts"] else "CharHeightInPts"
    if type(after[inactive]) is type(before[inactive]) and after[inactive] == before[inactive]:
        return []
    return [{"member": inactive, "before": before[inactive], "after": after[inactive],
             "reason": "inactive-height-representation"}]
