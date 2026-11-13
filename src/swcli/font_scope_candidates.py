"""Finite next-branch probes; never a public capability or protocol switch.

These are document defaults, not object fonts. Only old default readback/save
was calibrated; subtype/table/cell inheritance still needs separate evidence.
"""
from .font_snapshot import FONT_WRITABLE_FIELDS

NEXT_FONT_SCOPES = ("dimensions", "tables")
NEXT_FONT_WRITE_PROFILES = {
    scope: {"runtime": "native-windows", "solidworks_revision": "33.5.0",
            "document_types": (1, 2, 3), "fields": FONT_WRITABLE_FIELDS}
    for scope in NEXT_FONT_SCOPES
}

# Read witnesses for documented table-type fan-out. This finite initial set is
# not an assertion that every table subtype or cell inheritance is covered.
NEXT_FONT_LINKED_READS = {
    "dimensions": {},
    "tables": {
        "bom": ("swDetailingBillOfMaterialTextFormat", "swDetailingNoOptionSpecified"),
        "general": ("swDetailingGeneralTableTextFormat", "swDetailingNoOptionSpecified"),
        "hole": ("swDetailingHoleTableTextFormat", "swDetailingNoOptionSpecified"),
        "revision": ("swDetailingRevisionTableTextFormat", "swDetailingNoOptionSpecified"),
        "title_block": ("swDetailingTitleBlockTableTextFormat", "swDetailingNoOptionSpecified"),
    },
}
