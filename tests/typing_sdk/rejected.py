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
