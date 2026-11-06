"""Finite overall-standard catalog and explicitly bounded observed defaults."""

from .document_annotation_fonts import ANNOTATION_FONT_MEMBERS
from .document_annotations import ANNOTATION_FIELDS
from .document_display_options import display_fields_for_document

DRAFTING_STANDARD_PREFERENCE = 13  # swDetailingDimensionStandard
DRAFTING_STANDARD_OPTION = 0  # swDetailingNoOptionSpecified
DRAFTING_STANDARDS = {
    "ansi": 1, "iso": 2, "din": 3, "jis": 4, "bsi": 5, "gost": 6, "gb": 7,
    "custom": 8,
}
NAMED_DRAFTING_STANDARDS = tuple(name for name in DRAFTING_STANDARDS if name != "custom")
DRAFTING_DEFAULTS_PROFILE = "drafting-defaults-v1"
# Each future entry must be (document_type, source_native, target_native, profile).
# Public operations are wired; no changed transition is enabled before native calibration.
CALIBRATED_DRAFTING_TRANSITIONS = ()
# Native Windows only; exact RevisionNumber strings need independent evidence.
CALIBRATED_DRAFTING_WINDOWS_REVISIONS = ()
# Exact swUserPreferenceOption_e values from read-r1's installed official TLB.
# The four preference/option API pairings are documented in the official DP pages.
BASE_STANDARD_OPTIONS = {
    "geometric_tolerance": {"symbol": "swDetailingGeometricTolerance", "option": 103},
    "detail_view": {"symbol": "swDetailingDetailView", "option": 301},
    "auxiliary_view": {"symbol": "swDetailingAuxiliaryView", "option": 303},
    "section_view": {"symbol": "swDetailingSectionView", "option": 302},
}
LENGTH_UNIT_NATIVE_FIELDS = (
    "length_unit", "fraction_base", "fraction_value", "significant_digits", "round_to_fraction",
)


def drafting_standard_observation(native_value):
    if type(native_value) is not int or not -(2 ** 31) <= native_value < 2 ** 31:
        raise ValueError("native document drafting standard is not an Int32")
    return {
        "value": next((name for name, code in DRAFTING_STANDARDS.items()
                       if code == native_value), "other"),
        "native_value": native_value,
    }


def validate_drafting_standard(value):
    if type(value) is not str or value not in NAMED_DRAFTING_STANDARDS:
        raise ValueError("select a supported named document drafting standard")
    return value


def drafting_defaults_coverage(kind):
    """Pure catalog for the finite profile; not all document properties."""
    return {
        "annotations": list(ANNOTATION_FIELDS),
        "annotation_font_preference": 19,
        "annotation_font_option": 0,
        "annotation_font_members": list(ANNOTATION_FONT_MEMBERS.values()),
        "length_units_native_fields": list(LENGTH_UNIT_NATIVE_FIELDS),
        "display": list(display_fields_for_document(kind)),
        "base_standards": {name: {"preference": DRAFTING_STANDARD_PREFERENCE,
                                  "option": spec["option"]}
                           for name, spec in BASE_STANDARD_OPTIONS.items()},
    }
