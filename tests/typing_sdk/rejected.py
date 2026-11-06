from swcli.sdk import Client
from swcli.sdk.models import DocumentListParameters

client = Client()
client.document.open(path=42)  # E: arg-type
client.document.open(path="part.SLDPRT", document_id="d-ab12cd")  # E: call-arg
client.document.units_set(length_unit="yard")  # E: arg-type
client.document.lease.renew()  # E: call-arg
wrong_type: str = client.document.inspect().require_result()["document"]["modified"]  # E: assignment
client.feature.extrude(sketch_id="s-ab12cd", depth_mm="ten")  # E: arg-type
client.sketch.polygon(plane="front", vertices_mm=[{"x": 0.0}])  # E: typeddict-item
bad_empty_parameters: DocumentListParameters = {"unexpected": True}  # E: typeddict-unknown-key

from swcli.sdk.models import (
    DocumentAnnotationFontResultFont, DocumentAnnotationFontSetParameters,
    DocumentDisplayOptionSetParameters, DocumentDraftingStandardSetParametersExpectedSnapshotVariant1,
)


def refuse_preferences(font: DocumentAnnotationFontResultFont, snapshot: DocumentDraftingStandardSetParametersExpectedSnapshotVariant1) -> None:
    client.document.annotation_font_set(field="bold", value="true", expected_font=font, expected_update_stamp=0, lease_id="l-ab12cd34ef56")  # E: call-overload
    client.document.annotation_font_set(field="typeface", value=14, expected_font=font, expected_update_stamp=0, lease_id="l-ab12cd34ef56")  # E: call-overload
    client.document.annotation_font_set(field="height_points", value=14.5, expected_font=font, expected_update_stamp=0, lease_id="l-ab12cd34ef56")  # E: call-overload
    client.document.annotation_font_set(field="backwards", value=True, expected_font=font, expected_update_stamp=0, lease_id="l-ab12cd34ef56")  # E: call-overload
    client.document.annotation_font_set(field="bold", value=True, expected_font=font, lease_id="l-ab12cd34ef56")  # E: call-overload
    client.document.display_option_set(field="grid.display", value=1, expected_value=True, expected_update_stamp=0, lease_id="l-ab12cd34ef56")  # E: call-overload
    client.document.display_option_set(field="grid.major_spacing_mm", value=1.0, expected_value="1", expected_update_stamp=0, lease_id="l-ab12cd34ef56")  # E: call-overload
    client.document.display_option_set(field="virtual_sharp.style", value="other", expected_value="plus", expected_update_stamp=0, lease_id="l-ab12cd34ef56")  # E: call-overload
    client.document.display_option_set(field="plane.transparency", value=12.5, expected_value=95, expected_update_stamp=0, lease_id="l-ab12cd34ef56")  # E: call-overload
    client.document.display_option_set(field="grid.display", value=True, expected_value=False, expected_update_stamp=0)  # E: call-overload
    client.document.drafting_standard_set(value="other", expected_snapshot=snapshot, expected_update_stamp=0, lease_id="l-ab12cd34ef56")  # E: arg-type
    client.document.drafting_standard_set(value="iso", expected_snapshot={}, expected_update_stamp=0, lease_id="l-ab12cd34ef56")  # E: arg-type
    invalid_font: DocumentAnnotationFontSetParameters = {"field": "bold", "value": "true", "expected_font": font}  # E: assignment
    invalid_display: DocumentDisplayOptionSetParameters = {"field": "grid.display", "value": "true", "expected_value": False}  # E: assignment
    invalid_display_result: str = client.document.display_options().require_result()["options"]["grid.display"]["value"]  # E: assignment
    invalid_normalization: str = client.document.annotation_font_set(field="bold", value=True, expected_font=font, expected_update_stamp=0, lease_id="l-ab12cd34ef56").require_result()["native_normalizations"][0]["after"]  # E: assignment
    invalid_coverage: int = snapshot["observed_defaults"]["coverage"]["display"][0]  # E: assignment
