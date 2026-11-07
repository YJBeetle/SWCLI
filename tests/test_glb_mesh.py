"""Diagnostic parser proofs on real synthetic containers, not native export proof."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts/ci"))
from gate_support.glb_mesh import inspect_glb


def container(tree, binary):
    tree = deepcopy(tree)
    tree["buffers"] = [dict(byteLength=len(binary))]
    manifest = json.dumps(tree, separators=(",",":"), allow_nan=True).encode()
    manifest += b" "*(-len(manifest)%4)
    binary += b"\0"*(-len(binary)%4)
    return (struct.pack("<4sII", b"glTF", 2, 28+len(manifest)+len(binary))
        + struct.pack("<I4s", len(manifest), b"JSON")+manifest
        + struct.pack("<I4s", len(binary), b"BIN\0")+binary)


def fixture():
    binary = struct.pack("<18f3H", 0,0,0, 1,0,0, 0,1,0, 0,0,1, 0,0,1, 0,0,1, 0,1,2)
    tree = dict(asset=dict(version="2.0"), bufferViews=[dict(buffer=0,byteLength=36),
        dict(buffer=0,byteOffset=36,byteLength=36),dict(buffer=0,byteOffset=72,byteLength=6)],
        accessors=[dict(bufferView=0,componentType=5126,count=3,type="VEC3"),
            dict(bufferView=1,componentType=5126,count=3,type="VEC3"),dict(bufferView=2,componentType=5123,count=3,type="SCALAR")],
        meshes=[dict(primitives=[dict(attributes=dict(POSITION=0,NORMAL=1),indices=2)])])
    return tree,binary


class GLBMeshTests(unittest.TestCase):
    def inspect(self, data, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"mesh.glb"; path.write_bytes(data)
            return inspect_glb(path, **kwargs)

    def test_real_positions_normals_indices_and_local_bounds_are_measured(self):
        result = self.inspect(container(*fixture()))
        self.assertEqual((result["triangles"], result["positions"], result["normals"]),(1,3,3))
        self.assertEqual(result["primitives"][0]["bounds_local"], [[0,0,0],[1,1,0]])
        self.assertFalse(result["primitives"][0]["draco_decoded"])

    def test_strip_and_fan_are_counted_by_mode_not_count_divided_by_three(self):
        tree,binary=fixture()
        tree["meshes"][0]["primitives"][0].pop("indices")
        tree["accessors"][0]["count"] = 6
        tree["accessors"][1]["count"] = 6
        tree["bufferViews"][0]["byteLength"] = 72
        tree["bufferViews"][1].update(byteOffset=0,byteLength=72)
        for mode in (5,6):
            tree["meshes"][0]["primitives"][0]["mode"] = mode
            self.assertEqual(self.inspect(container(tree,binary))["triangles"], 4)

    def test_truncated_chunks_nonfinite_positions_bad_index_and_unsupported_accessors_fail(self):
        original,binary = fixture()
        defects = [lambda t: t["accessors"][0].update(count=900),
            lambda t: t["accessors"][0].update(sparse={"count":1}),
            lambda t: t["accessors"][1].update(normalized=True),
            lambda t: t["bufferViews"][0].update(byteOffset=-1),
            lambda t: t["meshes"][0]["primitives"][0].update(mode=1),
            lambda t: t.update(extensionsRequired=["EXT_meshopt_compression"])]
        for defect in defects:
            tree=deepcopy(original); defect(tree)
            with self.subTest(defect=defect), self.assertRaises((ValueError, IndexError)):
                self.inspect(container(tree,binary))
        for invalid in (container(original,binary)[:-1], container(original, struct.pack("<f",float("nan"))+binary[4:]),
                        container(original, binary[:-2]+struct.pack("<H",5))):
            with self.assertRaises(ValueError): self.inspect(invalid)

    @unittest.skipUnless(importlib.util.find_spec("DracoPy") and importlib.util.find_spec("numpy"), "optional native-gate decoder")
    def test_actual_draco_decode_uses_extension_attribute_ids_and_decoded_topology(self):
        import DracoPy
        import numpy as np
        points=np.array([[0.,0,0],[1,0,0],[0,1,0]],dtype=np.float32)
        normals=np.array([[0.,0,1]]*3,dtype=np.float64)
        faces=np.array([[0,1,2]],dtype=np.uint32)
        binary=DracoPy.encode(points,faces,normals=normals)
        decoded=DracoPy.decode(binary)
        ids={attribute["attribute_type"]:attribute["unique_id"] for attribute in decoded.attributes}
        tree,_=fixture()
        tree["bufferViews"]=[dict(buffer=0,byteLength=len(binary))]
        for accessor in tree["accessors"]: accessor.pop("bufferView")
        tree.update(extensionsUsed=["KHR_draco_mesh_compression"],extensionsRequired=["KHR_draco_mesh_compression"])
        tree["meshes"][0]["primitives"][0]["extensions"]={"KHR_draco_mesh_compression":dict(bufferView=0,
            attributes=dict(POSITION=ids[DracoPy.AttributeType.POSITION],NORMAL=ids[DracoPy.AttributeType.NORMAL]))}
        result=self.inspect(container(tree,binary))
        self.assertEqual((result["triangles"],result["positions"],result["normals"]),(1,3,3))
        self.assertTrue(result["primitives"][0]["draco_decoded"])
        tree["accessors"][2]["count"]=6
        with self.assertRaisesRegex(ValueError,"decoded index count"):
            self.inspect(container(tree,binary))
