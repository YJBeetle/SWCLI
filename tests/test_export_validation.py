import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
from zipfile import ZIP_DEFLATED, ZipFile

from swcli.hosts import export_validation as validation


def binary_stl():
    return b"solid binary".ljust(80, b"\x00") + struct.pack("<I12fH", 1, *([0.0] * 12), 0)


def ascii_stl():
    return (b"solid triangle\nfacet normal 0 0 1\nouter loop\n"
            b"vertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\n"
            b"endloop\nendfacet\nendsolid triangle\n")


def amf():
    return (b'<amf unit="millimeter"><object id="0"><mesh><vertices>'
            b'<vertex><coordinates><x>0</x><y>0</y><z>0</z></coordinates></vertex>'
            b'<vertex><coordinates><x>1</x><y>0</y><z>0</z></coordinates></vertex>'
            b'<vertex><coordinates><x>0</x><y>1</y><z>0</z></coordinates></vertex>'
            b'</vertices><volume><triangle><v1>0</v1><v2>1</v2><v3>2</v3>'
            b'</triangle></volume></mesh></object></amf>')


def archive(members):
    stream = io.BytesIO()
    with ZipFile(stream, "w") as output:
        for name, payload in members.items():
            output.writestr(name, payload)
    return stream.getvalue()


def three_mf_members():
    return {
        "[Content_Types].xml": (
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
            '</Types>'
        ),
        "_rels/.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="r1" Target="/3D/object.model" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
            '</Relationships>'
        ),
        "3D/object.model": (
            '<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
            '<resources><object id="1" type="model"><mesh><vertices>'
            '<vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/>'
            '</vertices><triangles><triangle v1="0" v2="1" v3="2"/></triangles>'
            '</mesh></object></resources><build><item objectid="1"/></build></model>'
        ),
    }


def glb_model():
    return {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": 36}],
        "bufferViews": [{"buffer": 0, "byteLength": 36}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
    }


def glb(model=None):
    metadata = json.dumps(glb_model() if model is None else model).encode("utf-8")
    metadata += b" " * (-len(metadata) % 4)
    chunks = struct.pack("<I4s", len(metadata), b"JSON") + metadata
    chunks += struct.pack("<I4s", 36, b"BIN\x00") + b"\x00" * 36
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


class ExportValidationTests(unittest.TestCase):
    def valid(self, format, payload):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ("artifact." + format.lower())
            path.write_bytes(payload)
            return validation.export_file_valid(format, path)

    def test_valid_binary_and_ascii_stl(self):
        self.assertTrue(self.valid("STL", binary_stl()))
        self.assertTrue(self.valid("STL", ascii_stl()))

    def test_stl_rejects_empty_truncated_and_incomplete_facets(self):
        for payload in (b"", b"solid empty\nendsolid empty", binary_stl()[:-1],
                        binary_stl() + b"trailing", ascii_stl().replace(b"vertex 0 1 0\n", b""),
                        ascii_stl().replace(b"1 0 0", b"nan 0 0"),
                        ascii_stl() + b"garbage", b"solid " + b"x" * 16385):
            with self.subTest(payload=payload[:30]):
                self.assertFalse(self.valid("STL", payload))

    def test_binary_stl_rejects_nonfinite_float(self):
        payload = bytearray(binary_stl())
        struct.pack_into("<f", payload, 84, float("inf"))
        self.assertFalse(self.valid("STL", payload))

    def test_valid_amf_raw_and_compressed(self):
        self.assertTrue(self.valid("AMF", amf()))
        self.assertTrue(self.valid("AMF", archive({"object.amf": amf()})))
        self.assertTrue(self.valid("AMF", amf().decode().encode("utf-16")))

    def test_amf_rejects_missing_geometry_entities_and_multiple_models(self):
        for payload in (b"<amf/>", amf().replace(b"<triangle>", b"<not-a-triangle>")
                        .replace(b"</triangle>", b"</not-a-triangle>"),
                        b'<!DOCTYPE amf [<!ENTITY x "test">]>' + amf(),
                        archive({"a.amf": amf(), "b.amf": amf()}),
                        archive({"nothing.txt": "not an AMF"})):
            with self.subTest(payload=payload[:30]):
                self.assertFalse(self.valid("AMF", payload))

    def test_xml_entities_cannot_use_utf16_to_bypass_guard(self):
        payload = ('<!DOCTYPE amf [<!ENTITY x "test">]>' + amf().decode()).encode("utf-16")
        self.assertFalse(self.valid("AMF", payload))

    def test_valid_three_mf_model_and_component_build(self):
        members = three_mf_members()
        self.assertTrue(self.valid("3MF", archive(members)))
        members["3D/object.model"] = members["3D/object.model"].replace(
            '</resources>', '<object id="2"><components><component objectid="1"/></components></object></resources>'
        ).replace('<item objectid="1"/>', '<item objectid="2"/>')
        self.assertTrue(self.valid("3MF", archive(members)))

    def test_three_mf_checks_package_relationship_and_geometry(self):
        for name, old, new in (
            ("_rels/.rels", "3D/object.model", "missing.model"),
            ("_rels/.rels", 'Id="r1"', 'Id="r1" TargetMode="External"'),
            ("[Content_Types].xml", 'Extension="model"', 'Extension="txt"'),
            ("3D/object.model", '<triangle v1="0" v2="1" v3="2"/>', ''),
            ("3D/object.model", 'objectid="1"', 'objectid="99"'),
            ("3D/object.model", '<build><item objectid="1"/></build>', '<build/>'),
        ):
            members = three_mf_members()
            members[name] = members[name].replace(old, new)
            with self.subTest(name=name, old=old):
                self.assertFalse(self.valid("3MF", archive(members)))
        self.assertFalse(self.valid("3MF", b"PK\x03\x04not a zip"))
        self.assertFalse(self.valid("3MF", archive({"README": "no model"})))

    def test_metadata_and_archive_limits_are_enforced(self):
        with mock.patch.object(validation, "MAX_METADATA_BYTES", 8):
            self.assertFalse(self.valid("AMF", amf()))
            self.assertFalse(self.valid("3MF", archive(three_mf_members())))
            self.assertFalse(self.valid("GLB", glb()))
        with mock.patch.object(validation, "MAX_ARCHIVE_MEMBERS", 2):
            self.assertFalse(self.valid("3MF", archive(three_mf_members())))
        with mock.patch.object(validation, "MAX_ARTIFACT_BYTES", 1):
            self.assertFalse(self.valid("STL", binary_stl()))
            self.assertTrue(self.valid("PDF", b"%PDF-1.7"))
            self.assertTrue(self.valid("DWG", b"AC1032"))
            self.assertTrue(self.valid("STEP", b"ISO-10303-21;"))

    def test_duplicate_members_are_rejected(self):
        stream = io.BytesIO()
        with ZipFile(stream, "w") as output:
            output.writestr("a.amf", amf())
            with self.assertWarns(UserWarning):
                output.writestr("a.amf", amf())
        self.assertFalse(self.valid("AMF", stream.getvalue()))

    def test_damaged_deflated_metadata_returns_false_not_decompression_exception(self):
        stream = io.BytesIO()
        with ZipFile(stream, "w", compression=ZIP_DEFLATED) as output:
            output.writestr("object.amf", amf())
        payload = bytearray(stream.getvalue())
        # ZIP local header followed by name/extra fields, then raw DEFLATE.
        name_length, extra_length = struct.unpack_from("<HH", payload, 26)
        compressed_offset = 30 + name_length + extra_length
        # The raw DEFLATE block type 3 is invalid, provoking zlib.error.
        payload[compressed_offset] = (payload[compressed_offset] & ~7) | 7
        self.assertFalse(self.valid("AMF", bytes(payload)))

    def test_valid_glb(self):
        self.assertTrue(self.valid("GLB", glb()))

    def test_glb_requires_valid_container_asset_and_nonempty_mesh(self):
        self.assertFalse(self.valid("GLB", glb()[:-1]))
        self.assertFalse(self.valid("GLB", glb() + b"trailing"))
        for mutate in (
            lambda model: model.update(meshes=[]),
            lambda model: model["meshes"][0].update(primitives=[]),
            lambda model: model["meshes"][0].update(primitives=[None]),
            lambda model: model["meshes"][0].update(primitives=[{}]),
            lambda model: model["asset"].update(version="1.0"),
            lambda model: model.update(asset=[]),
        ):
            model = glb_model()
            mutate(model)
            self.assertFalse(self.valid("GLB", glb(model)))

    def test_glb_does_not_reject_alternative_geometry_encodings(self):
        model = glb_model()
        del model["accessors"][0]["bufferView"]
        model["accessors"][0]["sparse"] = {"count": 3}
        model["meshes"][0]["primitives"][0]["extensions"] = {
            "KHR_draco_mesh_compression": {"bufferView": 0, "attributes": {"POSITION": 0}}
        }
        self.assertTrue(self.valid("GLB", glb(model)))
        payload = glb(model)
        # Optional unknown extension chunks must not be mistaken for damage.
        extended = bytearray(payload + struct.pack("<I4s", 4, b"EXTN") + b"data")
        struct.pack_into("<I", extended, 8, len(extended))
        self.assertTrue(self.valid("GLB", bytes(extended)))

    def test_glb_rejects_duplicate_json_and_incomplete_chunks(self):
        for chunk in (struct.pack("<I4s", 4, b"JSON") + b"{}  ",
                      struct.pack("<I4s", 100, b"BIN\x00") + b"short"):
            payload = bytearray(glb() + chunk)
            struct.pack_into("<I", payload, 8, len(payload))
            self.assertFalse(self.valid("GLB", bytes(payload)))

    def test_legacy_signatures_and_unknown_format(self):
        for format, payload in (("PDF", b"%PDF-1.7"), ("DWG", b"AC1032"),
                                ("STEP", b"ISO-10303-21;"), ("STP", b"ISO-10303-21;")):
            self.assertTrue(self.valid(format, payload))
        self.assertFalse(self.valid("OBJ", b"v 0 0 0"))
        self.assertFalse(validation.export_file_valid("STL", Path("missing.stl")))
