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
    client.feature.revolve(sketch_id="s-ab12cd", expected_profile_mm=[0.0, -5.0, 10.0, 15.0],
                           axis_mm=[0.0, -5.0, 0.0, 15.0], angle_deg=360.0,
                           document_id="d-ab12cd", expected_update_stamp=12)
    client.workspace.download_begin(path="models/part.SLDPRT")
    return client.files.download("models/part.SLDPRT", "received/part.SLDPRT")


def configured() -> Client:
    return Client(tls=TLSConfig(token_file=Path("token.txt"), ca_file="ca.pem", server_name="cad.internal"),
                  client_workspace=Path("client-files"))


# Exact recipes remain typed data; every write still goes through Client.
from swcli.stl_calibrated_profiles import PROFILES
from swcli.sdk.models import DocumentExportResult


def export_qualified_stl(client: Client) -> Response[DocumentExportResult]:
    return client.document.export(output="curved.stl", stl_options=PROFILES["fine"], strict=True,
        document_id="d-ab12cd", expected_update_stamp=161, lease_id="l-ab12cd34ef56")
def observe_quality(client: Client) -> None:
    quality = client.document.image_quality(document_id="d-ab12cd").require_result()["quality"]
    client.document.image_quality_set(field="optimize_edge_length", value=False,
        expected_quality=quality, expected_update_stamp=0, lease_id="l-ab12cd34ef56")
