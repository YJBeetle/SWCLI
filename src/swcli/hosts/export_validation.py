"""Bounded, portable structural checks for exported CAD artifacts.

These checks reject missing/truncated geometry and invalid containers. They do
not certify watertightness, tessellation accuracy, materials, or CAD equivalence.
No ZIP members are extracted and XML declarations of entities are rejected.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import posixpath
import struct
from urllib.parse import unquote
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile
from zlib import error as DecompressionError

MAX_ARTIFACT_BYTES = 512 * 1024 * 1024
MAX_METADATA_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 4096
_CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
_MODEL_REL = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
_MODEL_TYPE = "application/vnd.ms-package.3dmanufacturing-3dmodel+xml"


def _xml(data: bytes) -> ET.Element:
    if len(data) > MAX_METADATA_BYTES:
        raise ValueError("XML metadata exceeds verification limit")
    # Decode before checking: UTF-16/32 documents must not bypass entity guards.
    if data.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        text = data.decode("utf-32")
    elif data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16")
    else:
        text = data.decode("utf-8-sig")
    if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ValueError("XML entity declarations are not accepted")
    return ET.fromstring(text)


def _zip_member(archive: ZipFile, name: str) -> bytes:
    member = archive.getinfo(name)
    if member.file_size > MAX_METADATA_BYTES or member.flag_bits & 1:
        raise ValueError("unsupported or oversized archive metadata")
    with archive.open(member) as stream:
        data = stream.read(MAX_METADATA_BYTES + 1)
    if len(data) != member.file_size:
        raise ValueError("incomplete archive member")
    return data


def _archive_names(archive: ZipFile) -> list[str]:
    members = archive.infolist()
    names = [member.filename for member in members]
    if len(names) > MAX_ARCHIVE_MEMBERS or len(names) != len(set(names)):
        raise ValueError("excessive or duplicate ZIP members")
    return names


def _finite(values: list[str]) -> bool:
    return all(math.isfinite(float(value)) for value in values)


def _stl(path: Path, size: int) -> bool:
    with path.open("rb") as stream:
        header = stream.read(84)
        if len(header) == 84:
            count = struct.unpack_from("<I", header, 80)[0]
            if count > 0 and size == 84 + count * 50:
                for _ in range(count):
                    values = struct.unpack("<12fH", stream.read(50))
                    if not all(math.isfinite(value) for value in values[:12]):
                        return False
                return True
        stream.seek(0)
        state, triangles, vertices = "solid", 0, 0
        while True:
            raw = stream.readline(16385)
            if not raw:
                return state == "done" and triangles > 0
            if len(raw) > 16384:
                return False
            words = raw.decode("ascii").strip().split()
            if not words:
                continue
            if state == "solid" and words[0] == "solid":
                state = "facet"
            elif state == "facet" and words[0] == "endsolid":
                state = "done"
            elif state == "facet" and words[:2] == ["facet", "normal"]:
                if len(words) != 5 or not _finite(words[2:]):
                    return False
                state = "loop"
            elif state == "loop" and words == ["outer", "loop"]:
                vertices, state = 0, "vertex"
            elif state == "vertex" and words[0] == "vertex":
                if len(words) != 4 or not _finite(words[1:]) or vertices >= 3:
                    return False
                vertices += 1
            elif state == "vertex" and words == ["endloop"] and vertices == 3:
                state = "endfacet"
            elif state == "endfacet" and words == ["endfacet"]:
                triangles, state = triangles + 1, "facet"
            else:
                return False


def _mesh(mesh: ET.Element, namespace: str, *, amf: bool = False) -> bool:
    """Require a non-empty mesh; do not implement a geometry/schema engine."""
    tag = lambda name: f"{{{namespace}}}{name}" if namespace else name
    vertices = mesh.find(tag("vertices"))
    if vertices is None or len(vertices.findall(tag("vertex"))) < 3:
        return False
    if amf:
        return any(volume.find(tag("triangle")) is not None
                   for volume in mesh.findall(tag("volume")))
    collection = mesh.find(tag("triangles"))
    return collection is not None and collection.find(tag("triangle")) is not None


def _three_mf(path: Path) -> bool:
    with ZipFile(path) as archive:
        names = _archive_names(archive)
        relationships = _xml(_zip_member(archive, "_rels/.rels"))
        if relationships.tag != f"{{{_REL}}}Relationships":
            return False
        targets = [relation.attrib["Target"] for relation in relationships
                   if relation.tag == f"{{{_REL}}}Relationship"
                   and relation.get("Type") == _MODEL_REL
                   and relation.get("TargetMode", "Internal") == "Internal"]
        if len(targets) != 1:
            return False
        target = posixpath.normpath(unquote(targets[0]).lstrip("/"))
        if target.startswith("../") or target not in names:
            return False
        types = _xml(_zip_member(archive, "[Content_Types].xml"))
        if types.tag != f"{{{_TYPES}}}Types" or not any(
            item.get("ContentType") == _MODEL_TYPE and (
                item.tag == f"{{{_TYPES}}}Override" and item.get("PartName") == "/" + target
                or item.tag == f"{{{_TYPES}}}Default" and item.get("Extension") == target.rsplit(".", 1)[-1]
            ) for item in types
        ):
            return False
        model = _xml(_zip_member(archive, target))
    if model.tag != f"{{{_CORE}}}model":
        return False
    resources, build = model.find(f"{{{_CORE}}}resources"), model.find(f"{{{_CORE}}}build")
    if resources is None or build is None:
        return False
    objects = resources.findall(f"{{{_CORE}}}object")
    ids = {obj.attrib["id"] for obj in objects}
    meshes = [obj.find(f"{{{_CORE}}}mesh") for obj in objects]
    if len(ids) != len(objects) or not any(mesh is not None for mesh in meshes):
        return False
    if any(mesh is not None and not _mesh(mesh, _CORE) for mesh in meshes):
        return False
    references = [item.attrib["objectid"] for item in build.findall(f"{{{_CORE}}}item")]
    references += [component.attrib["objectid"] for obj in objects
                   for component in obj.findall(f"{{{_CORE}}}components/{{{_CORE}}}component")]
    return bool(build.findall(f"{{{_CORE}}}item")) and all(ref in ids for ref in references)


def _amf(path: Path) -> bool:
    with path.open("rb") as stream:
        zipped = stream.read(4) == b"PK\x03\x04"
    if zipped:
        with ZipFile(path) as archive:
            names = _archive_names(archive)
            models = [name for name in names if name.casefold().endswith(".amf")]
            if len(models) != 1:
                return False
            root = _xml(_zip_member(archive, models[0]))
    else:
        with path.open("rb") as stream:
            root = _xml(stream.read(MAX_METADATA_BYTES + 1))
    namespace = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""
    tag = lambda name: f"{{{namespace}}}{name}" if namespace else name
    if root.tag != tag("amf"):
        return False
    objects = root.findall(tag("object"))
    ids = {obj.attrib["id"] for obj in objects}
    meshes = [mesh for obj in objects for mesh in obj.findall(tag("mesh"))]
    return len(ids) == len(objects) and bool(meshes) and all(
        _mesh(mesh, namespace, amf=True) for mesh in meshes
    )


def _glb(path: Path, size: int) -> bool:
    with path.open("rb") as stream:
        if stream.read(8) != b"glTF\x02\x00\x00\x00":
            return False
        if struct.unpack("<I", stream.read(4))[0] != size:
            return False
        chunks = []
        model = None
        while stream.tell() < size:
            length, kind = struct.unpack("<I4s", stream.read(8))
            if length % 4 or stream.tell() + length > size:
                return False
            chunks.append((kind, length))
            if len(chunks) == 1:
                if kind != b"JSON" or length > MAX_METADATA_BYTES:
                    return False
                model = json.loads(stream.read(length))
            else:
                stream.seek(length, 1)
    if not isinstance(model, dict):
        return False
    # The GLB specification permits JSON-only files and unknown extension
    # chunks. Compressed/sparse accessors need not use ordinary bufferViews.
    if any(kind == b"JSON" for kind, _ in chunks[1:]):
        return False
    if sum(kind == b"BIN\x00" for kind, _ in chunks) > 1:
        return False
    if model.get("asset", {}).get("version") != "2.0":
        return False
    meshes = model.get("meshes")
    return isinstance(meshes, list) and any(
        isinstance(mesh, dict) and isinstance(mesh.get("primitives"), list)
        and any(isinstance(primitive, dict)
                and isinstance(primitive.get("attributes"), dict)
                and "POSITION" in primitive["attributes"]
                for primitive in mesh["primitives"])
        for mesh in meshes
    )


def export_file_valid(export_format: str, path: Path) -> bool:
    """Return structural validity, not geometry equivalence or full conformance."""
    try:
        size = path.stat().st_size
        if size <= 0:
            return False
        if export_format in {"STL", "3MF", "AMF", "GLB"} and size > MAX_ARTIFACT_BYTES:
            return False
        if export_format == "STL":
            return _stl(path, size)
        if export_format == "3MF":
            return _three_mf(path)
        if export_format == "AMF":
            return _amf(path)
        if export_format == "GLB":
            return _glb(path, size)
        with path.open("rb") as stream:
            header = stream.read(128)
        if export_format == "PDF":
            return header.startswith(b"%PDF-")
        if export_format == "DWG":
            return header.startswith(b"AC10")
        if export_format in {"STEP", "STP"}:
            return b"ISO-10303-21;" in header
        return False
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, struct.error,
            ET.ParseError, BadZipFile, DecompressionError, RuntimeError,
            NotImplementedError, OverflowError):
        return False
