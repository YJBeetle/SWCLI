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
