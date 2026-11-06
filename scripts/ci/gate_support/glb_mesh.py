"""Strict diagnostic GLB mesh inspection, including actual optional Draco decode.

This is evidence tooling, not an exporter or a public tessellation guarantee.
Only self-contained GLB 2.0 triangle primitives with supported accessors qualify.
"""
import hashlib
import json
import math
import struct


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate GLB JSON key")
        result[key] = value
    return result


def inspect_glb(path, *, draco_decoder=None):
    content = path.read_bytes()
    require(len(content) >= 20, "truncated GLB header")
    magic, version, size = struct.unpack_from("<4sII", content)
    require(magic == b"glTF" and version == 2 and size == len(content), "invalid GLB header")
    offset, chunks = 12, []
    while offset < size:
        require(offset + 8 <= size, "truncated GLB chunk header")
        length, kind = struct.unpack_from("<II", content, offset)
        offset += 8
        require(length % 4 == 0 and offset + length <= size, "invalid GLB chunk length")
        chunks.append((kind, content[offset:offset + length])); offset += length
    require([kind for kind, _ in chunks] == [0x4e4f534a, 0x004e4942], "expected JSON and BIN GLB chunks")
    tree = json.loads(chunks[0][1], object_pairs_hook=_unique,
                      parse_constant=lambda token: require(False, "nonfinite GLB JSON"))
    binary = chunks[1][1]
    require(tree["asset"]["version"] == "2.0", "unsupported glTF version")
    require(len(tree.get("buffers", [])) == 1 and "uri" not in tree["buffers"][0]
            and 0 <= len(binary) - tree["buffers"][0]["byteLength"] <= 3, "external or invalid GLB buffer")
    binary = binary[:tree["buffers"][0]["byteLength"]]
    require(not (set(tree.get("extensionsRequired", [])) - {"KHR_draco_mesh_compression", "KHR_materials_pbrSpecularGlossiness", "KHR_materials_unlit"}),
            "unsupported required GLB extension")

    def view(index):
        value = tree["bufferViews"][index]
        start, length = value.get("byteOffset", 0), value["byteLength"]
        require(value.get("buffer", 0) == 0 and type(start) is int and type(length) is int
                and start >= 0 and length >= 0 and start + length <= len(binary)
                and not value.get("extensions"), "invalid/unsupported GLB buffer view")
        return value, binary[start:start + length]

    def accessor(index, semantic):
        value = tree["accessors"][index]
        require(not value.get("sparse") and not value.get("normalized"), "unsupported sparse/normalized accessor")
        count = value["count"]
        require(type(count) is int and count > 0, "invalid GLB accessor count")
        code = value["componentType"]
        if semantic == "indices":
            require(value["type"] == "SCALAR" and code in (5121, 5123, 5125), "invalid GLB index accessor")
            fmt = {5121:"B", 5123:"H", 5125:"I"}[code]
        else:
            require(value["type"] == "VEC3" and code == 5126, "unsupported GLB vector accessor")
            fmt = "fff"
        spec, data = view(value["bufferView"])
        width = struct.calcsize("<" + fmt)
        stride, start = spec.get("byteStride", width), value.get("byteOffset", 0)
        require(type(stride) is int and type(start) is int and stride >= width and start >= 0
                and start + (count - 1) * stride + width <= len(data), "GLB accessor exceeds buffer")
        return [struct.unpack_from("<" + fmt, data, start + row * stride) for row in range(count)]

    rows = []
    for mesh_index, mesh in enumerate(tree.get("meshes", [])):
        for primitive in mesh["primitives"]:
            mode = primitive.get("mode", 4)
            require(mode in (4, 5, 6), "non-triangle GLB primitive unsupported")
            require(not primitive.get("targets"), "morph-target GLB unsupported")
            attributes = primitive["attributes"]
            require("POSITION" in attributes, "GLB primitive lacks positions")
            compressed = primitive.get("extensions", {}).get("KHR_draco_mesh_compression")
            if compressed:
                if draco_decoder is None:
                    import DracoPy
                    draco_decoder = DracoPy.decode
                _, data = view(compressed["bufferView"])
                decoded = draco_decoder(data)
                # Draco attribute IDs come from the extension; never assume 0/1.
                def attribute(semantic):
                    identifier = compressed["attributes"][semantic]
                    found = decoded.get_attribute_by_unique_id(identifier)
                    require(found is not None, "missing decoded Draco attribute")
                    return found["data"].tolist()
                points = attribute("POSITION")
                normals = attribute("NORMAL") if "NORMAL" in attributes else []
                require(mode == 4, "Draco triangle strips/fans unsupported")
                faces = decoded.faces.tolist()
                indices = [index for face in faces for index in face]
                require(all(len(face) == 3 for face in faces), "Draco decode did not return triangles")
            else:
                points = accessor(attributes["POSITION"], "POSITION")
                normals = accessor(attributes["NORMAL"], "NORMAL") if "NORMAL" in attributes else []
                indices = ([row[0] for row in accessor(primitive["indices"], "indices")]
                           if "indices" in primitive else list(range(len(points))))
            require(points and all(len(p) == 3 and all(math.isfinite(v) for v in p) for p in points), "invalid GLB positions")
            require(not normals or len(normals) == len(points) and all(len(n) == 3 and all(math.isfinite(v) for v in n) for n in normals), "invalid GLB normals")
            require(len(points) == tree["accessors"][attributes["POSITION"]]["count"], "decoded position count disagrees with accessor")
            if normals:
                require(len(normals) == tree["accessors"][attributes["NORMAL"]]["count"], "decoded normal count disagrees with accessor")
            require(indices and all(type(i) is int and 0 <= i < len(points) for i in indices), "GLB index out of bounds")
            if "indices" in primitive:
                require(len(indices) == tree["accessors"][primitive["indices"]]["count"], "decoded index count disagrees with accessor")
            require(len(indices) % 3 == 0 if mode == 4 else len(indices) >= 3, "invalid triangle index count")
            triangles = len(indices) // 3 if mode == 4 else len(indices) - 2
            rows.append(dict(mesh=mesh_index, mode=mode, draco_decoded=bool(compressed), indices=len(indices),
                positions=len(points), normals=len(normals), triangles=triangles,
                bounds_local=[list(map(min, zip(*points))), list(map(max, zip(*points)))],
                decoded_sha256=hashlib.sha256(json.dumps([points,normals,indices], separators=(",",":"), allow_nan=False).encode()).hexdigest()))
    require(rows and sum(row["triangles"] for row in rows) > 0, "GLB contains no decoded triangles")
    return dict(sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content), mesh_count=len(tree["meshes"]),
        primitives=rows, triangles=sum(row["triangles"] for row in rows),
        positions=sum(row["positions"] for row in rows), normals=sum(row["normals"] for row in rows),
        extensions_used=tree.get("extensionsUsed", []), extensions_required=tree.get("extensionsRequired", []),
        materials=tree.get("materials", []), camera_count=len(tree.get("cameras", [])),
        animation_count=len(tree.get("animations", [])), scene_extensions=tree.get("extensions", {}))
