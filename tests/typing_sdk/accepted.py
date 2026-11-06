from pathlib import Path
from swcli.sdk import Client, FileReceipt, Response, TLSConfig
from swcli.sdk.models import DocumentInspectResult


def inspect_design(client: Client) -> int:
    reply: Response[DocumentInspectResult] = client.document.inspect(
        document_id="d-ab12cd", expected_update_stamp=0, request_id="inspect-same-id")
    state = reply.require_result()["document"]
    stamp = state["update_stamp"]
    if stamp is None:
        raise ValueError("No update stamp")
    return stamp


def workflows(client: Client) -> FileReceipt:
    client.document.open(path=r"C:\Workspace\part.SLDPRT", read_only=True)
    client.document.units_set(length_unit="mm", decimal_places=3, document_id="d-ab12cd",
                              expected_update_stamp=0, lease_id="l-ab12cd34ef56")
    client.document.lease.renew(lease_id="l-ab12cd34ef56", ttl_seconds=60)
    client.sketch.polygon(plane="front", vertices_mm=[{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 0.0, "y": 1.0}])
    client.document.render(output="preview.bmp", include_content=True)
    client.feature.extrude(sketch_id="s-ab12cd", depth_mm=10.0)
    client.workspace.download_begin(path="models/part.SLDPRT")
    return client.files.download("models/part.SLDPRT", "received/part.SLDPRT")


def configured() -> Client:
    return Client(tls=TLSConfig(token_file=Path("token.txt"), ca_file="ca.pem", server_name="cad.internal"),
                  client_workspace=Path("client-files"))


from typing import Union
from swcli.sdk.models import (
    DocumentAnnotationFontResult, DocumentAnnotationFontResultFont,
    DocumentAnnotationFontSetParameters, DocumentAnnotationFontSetResult,
    DocumentDisplayOptionSetParameters, DocumentDisplayOptionSetResult,
    DocumentDisplayOptionsResult, DocumentDraftingStandardResult,
    DocumentDraftingStandardSetParametersExpectedSnapshotVariant1,
    DocumentDraftingStandardSetParametersExpectedSnapshotVariant2,
    DocumentDraftingStandardSetParametersExpectedSnapshotVariant3,
    DocumentDraftingStandardSetResult,
)


def document_preferences(client: Client, font: DocumentAnnotationFontResultFont,
                         snapshot: Union[DocumentDraftingStandardSetParametersExpectedSnapshotVariant1,
                                         DocumentDraftingStandardSetParametersExpectedSnapshotVariant2,
                                         DocumentDraftingStandardSetParametersExpectedSnapshotVariant3]) -> None:
    read_font: Response[DocumentAnnotationFontResult] = client.document.annotation_font(document_id="d-ab12cd")
    read_display: Response[DocumentDisplayOptionsResult] = client.document.display_options(expected_update_stamp=0)
    read_standard: Response[DocumentDraftingStandardResult] = client.document.drafting_standard()
    font_set: Response[DocumentAnnotationFontSetResult] = client.document.annotation_font_set(field="typeface", value="Arial", expected_font=font, expected_update_stamp=0, lease_id="l-ab12cd34ef56")
    client.document.annotation_font_set(field="height_mm", value=4.5, expected_font=font, expected_update_stamp=0, lease_id="l-ab12cd34ef56")
    client.document.annotation_font_set(field="height_points", value=14, expected_font=font, expected_update_stamp=0, lease_id="l-ab12cd34ef56")
    client.document.annotation_font_set(field="bold", value=False, expected_font=font, expected_update_stamp=0, lease_id="l-ab12cd34ef56")
    client.document.annotation_font_set(field="italic", value=True, expected_font=font, expected_update_stamp=0, lease_id="l-ab12cd34ef56")
    client.document.annotation_font_set(field="underline", value=True, expected_font=font, expected_update_stamp=0, lease_id="l-ab12cd34ef56")
    client.document.annotation_font_set(field="strikeout", value=False, expected_font=font, expected_update_stamp=0, lease_id="l-ab12cd34ef56")
    display_set: Response[DocumentDisplayOptionSetResult] = client.document.display_option_set(field="grid.display", value=False, expected_value=True, expected_update_stamp=0, lease_id="l-ab12cd34ef56")
    client.document.display_option_set(field="grid.major_spacing_mm", value=25.0, expected_value=100, expected_update_stamp=0, lease_id="l-ab12cd34ef56")
    client.document.display_option_set(field="grid.minor_lines_per_major", value=4, expected_value=1, expected_update_stamp=0, lease_id="l-ab12cd34ef56")
    client.document.display_option_set(field="virtual_sharp.style", value="plus", expected_value="witness", expected_update_stamp=0, lease_id="l-ab12cd34ef56")
    client.document.display_option_set(field="plane.front_face_color", value=33023, expected_value=0, expected_update_stamp=0, lease_id="l-ab12cd34ef56")
    standard_set: Response[DocumentDraftingStandardSetResult] = client.document.drafting_standard_set(value="iso", expected_snapshot=snapshot, expected_update_stamp=0, lease_id="l-ab12cd34ef56")
    point_size: int = read_font.require_result()["native_font"]["CharHeightInPts"]
    grid_enabled: bool = read_display.require_result()["options"]["grid.display"]["value"]
    font_request: DocumentAnnotationFontSetParameters = {"field": "height_points", "value": point_size, "expected_font": font}
    display_request: DocumentDisplayOptionSetParameters = {"field": "grid.display", "value": grid_enabled, "expected_value": False}
    mode: str = font_set.require_result()["font"]["height_mode"]
    initial_grid: bool = display_set.require_result()["before"]["grid.display"]["native_value"]
    profile: str = read_standard.require_result()["observed_defaults"]["profile"]
    standard_set.require_result()["before"]["observed_defaults"]["annotation_font"]["font"]["height_points"]
