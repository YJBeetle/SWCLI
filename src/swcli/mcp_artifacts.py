"""MCP presentation of daemon-supplied artifact bytes; never reads a host path."""

import base64
from copy import deepcopy
import hashlib
import io
import json
from pathlib import PureWindowsPath
from urllib.parse import quote
import uuid
import warnings

from .artifact_content import MAX_ARTIFACT_BYTES, MAX_BASE64_CHARS

MEDIA_TYPES = {"PDF": "application/pdf", "GLB": "model/gltf-binary",
               "STL": "model/stl", "3MF": "model/3mf"}
MAX_IMAGE_PIXELS = 16 * 1024 * 1024


def png_preview(data):
    from PIL import Image
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data), formats=["BMP"]) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValueError("render exceeds the preview pixel limit")
            with image.convert("RGB") as rgb:
                output = io.BytesIO()
                rgb.save(output, format="PNG")
        result = output.getvalue()
    if len(result) > MAX_ARTIFACT_BYTES:
        raise ValueError("PNG preview exceeds the attachment limit")
    return result


def tool_result(payload, operation=None):
    from mcp import types
    metadata = deepcopy(payload)
    attachments = []
    result = metadata.get("result")
    artifact = result.get("artifact") if isinstance(result, dict) else None
    if (operation in ("document.render", "document.export") and payload.get("success")
            and isinstance(artifact, dict)):
        transfer = artifact.get("content")
        if not isinstance(transfer, dict):
            transfer = {"status": "unsupported", "limit_bytes": MAX_ARTIFACT_BYTES}
            artifact["content"] = transfer
        encoded = transfer.pop("data_base64", None)
        if transfer.get("status") == "ready":
            try:
                if not isinstance(encoded, str) or len(encoded) > MAX_BASE64_CHARS:
                    raise ValueError("artifact content is missing or exceeds the encoded limit")
                data = base64.b64decode(encoded, validate=True)
                size = artifact.get("size_bytes")
                if (not isinstance(size, int) or isinstance(size, bool) or size < 1
                        or len(data) != size or len(data) > MAX_ARTIFACT_BYTES
                        or hashlib.sha256(data).hexdigest() != transfer.get("sha256")):
                    raise ValueError("artifact bytes differ from size/hash metadata")
                if operation == "document.render":
                    if artifact.get("kind") != "image" or artifact.get("media_type") != "image/bmp":
                        raise ValueError("unsupported render artifact type")
                    preview = png_preview(data)
                    attachments.append(types.ImageContent(type="image", mimeType="image/png",
                        data=base64.b64encode(preview).decode("ascii")))
                    transfer.update(preview_media_type="image/png", preview_size_bytes=len(preview),
                                    preview_sha256=hashlib.sha256(preview).hexdigest())
                else:
                    if artifact.get("kind") != "cad-export":
                        raise ValueError("unsupported export artifact type")
                    name = PureWindowsPath(artifact.get("path", "export")).name or "export"
                    uri = "swcli-artifact://" + uuid.uuid4().hex + "/" + quote(name, safe="")
                    mime = MEDIA_TYPES.get(artifact.get("format"), "application/octet-stream")
                    attachments.append(types.EmbeddedResource(type="resource",
                        resource=types.BlobResourceContents(uri=uri, mimeType=mime, blob=encoded)))
                    transfer.update(uri=uri, media_type=mime)
                transfer["status"] = "attached"
            except Exception as exc:
                transfer.update(status="unavailable", error={"code": type(exc).__name__, "message": str(exc)})
    # CAD success/refusal stays intact. Attachment failures are separate metadata:
    # never suggest repeating a successful export/mutation to recover a delivery.
    text = types.TextContent(type="text", text=json.dumps(metadata, ensure_ascii=False))
    return types.CallToolResult(content=[text, *attachments], structuredContent=metadata,
                                isError=not payload.get("success", False))
