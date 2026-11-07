"""Bounded, portable read-only reference envelopes, never edit authority."""

from __future__ import annotations

import base64
import binascii
import json
import ntpath
from typing import Any, Dict

MAX_TOKEN_CHARS = 262144
TOKEN_SCHEMA = {"type": "string", "minLength": 8, "maxLength": MAX_TOKEN_CHARS,
                "pattern": r"^swref1\.[A-Za-z0-9_-]+$"}
SCOPE_SCHEMA = {"type": "object", "additionalProperties": False,
                "required": ["document_path", "configuration"], "properties": {
                    "document_path": {"type": "string", "minLength": 1},
                    "configuration": {"type": "string", "minLength": 1}}}
POLICY = "complete-face-edge-bijection"


def document_path(value: Any) -> str:
    # Windows model paths only, including UNC; drive-relative paths are unsafe.
    if (not isinstance(value, str) or not value.strip() or "\x00" in value
            or not ntpath.isabs(value) or not ntpath.splitdrive(value)[0]
            or ntpath.splitext(value)[1].lower() != ".sldprt"):
        raise ValueError("persistent references require a saved absolute SLDPRT path")
    return ntpath.normcase(ntpath.normpath(value))


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    try:
        raw = base64.b64decode(text + "=" * (-len(text) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("malformed persistent reference encoding") from exc
    if not raw or _b64(raw) != text:
        raise ValueError("noncanonical persistent reference encoding")
    return raw


def encode_reference(payload: Dict[str, Any]) -> str:
    value = "swref1." + _b64(json.dumps(payload, ensure_ascii=True, sort_keys=True,
                                      separators=(",", ":")).encode("ascii"))
    decode_reference(value)
    return value


def decode_reference(value: Any) -> Dict[str, Any]:
    if (not isinstance(value, str) or not value.startswith("swref1.")
            or not 8 <= len(value) <= MAX_TOKEN_CHARS):
        raise ValueError("unsupported or oversized persistent reference envelope")
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate persistent reference envelope field")
            result[key] = item
        return result
    try:
        payload = json.loads(_unb64(value[7:]).decode("ascii"), object_pairs_hook=pairs)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError("malformed persistent reference envelope") from exc
    keys = {"version", "document_path", "configuration", "captured_update_stamp",
            "kind", "target_index", "faces", "edges"}
    if not isinstance(payload, dict) or set(payload) != keys:
        raise ValueError("unexpected persistent reference envelope fields")
    if type(payload["version"]) is not int or payload["version"] != 1:
        raise ValueError("unsupported persistent reference version")
    if document_path(payload["document_path"]) != payload["document_path"]:
        raise ValueError("persistent reference path is not canonical")
    if (not isinstance(payload["configuration"], str) or not payload["configuration"].strip()
            or type(payload["captured_update_stamp"]) is not int
            or payload["kind"] not in ("face", "edge")
            or type(payload["target_index"]) is not int):
        raise ValueError("invalid persistent reference scope or target")
    all_refs = []
    for field in ("faces", "edges"):
        refs = payload[field]
        if not isinstance(refs, list) or not 1 <= len(refs) <= 64:
            raise ValueError("persistent reference requires complete bounded topology")
        for ref in refs:
            if not isinstance(ref, str) or not 1 <= len(_unb64(ref)) <= 65536:
                raise ValueError("invalid native reference bytes")
        all_refs.extend(refs)
    if len(all_refs) != len(set(all_refs)):
        raise ValueError("duplicate references in complete topology envelope")
    if not 0 <= payload["target_index"] < len(payload[payload["kind"] + "s"]):
        raise ValueError("persistent reference target lies outside topology")
    return payload


def reference_result_fields(entity_schema, observation_schema):
    common = {"reference_scope": SCOPE_SCHEMA, "topology_policy": {"const": POLICY},
              "kind": {"enum": ["face", "edge"]},
              "captured_update_stamp": {"type": "integer"},
              "face_count": {"type": "integer", "minimum": 1, "maximum": 64},
              "edge_count": {"type": "integer", "minimum": 1, "maximum": 64},
              "observation": observation_schema,
              "native_status": {"type": "integer"}}
    required = ("document", "reference_scope", "topology_policy", "kind",
                "captured_update_stamp", "face_count", "edge_count", "observation")
    return {
        "entity.reference-create": ({**common, "reference": TOKEN_SCHEMA,
            "entity_id": {"type": "string", "pattern": "^e-[a-z0-9]{6}$"}},
            (*required, "reference", "entity_id")),
        "entity.reference-resolve": ({**common, "entity": entity_schema,
            "resolution": {"const": "resolved"}, "topology_verified": {"const": True}},
            (*required, "entity", "resolution", "topology_verified", "native_status")),
    }


def validate_reference_result(name, result):
    if not result["ok"]:
        return
    state = result["observation"]["after"]
    document = result["document"]
    scope = result["reference_scope"]
    if (state != result["observation"]["before"] or document["type"] != 1
            or state["update_stamp"] != document["update_stamp"]
            or state["modified"] != document["modified"]
            or scope["configuration"] != state["configuration"]
            or scope["document_path"] != document_path(document["path"])):
        raise ValueError("inconsistent persistent reference scope/state")
    if name == "entity.reference-create":
        payload = decode_reference(result["reference"])
        if (payload["document_path"] != scope["document_path"]
                or payload["configuration"] != scope["configuration"]
                or payload["kind"] != result["kind"]
                or payload["captured_update_stamp"] != result["captured_update_stamp"]
                or payload["captured_update_stamp"] != state["update_stamp"]
                or len(payload["faces"]) != result["face_count"]
                or len(payload["edges"]) != result["edge_count"]):
            raise ValueError("reference envelope disagrees with capture evidence")
    else:
        if result["native_status"] != 0 or result["entity"]["kind"] != result["kind"]:
            raise ValueError("resolved reference has non-OK native state or wrong kind")
        from .entity_contracts import validate_entity_semantics
        kind = result["kind"]
        # Reuse all analytic geometry checks for the fresh read-only descriptor.
        validate_entity_semantics("entity.inspect", {
            "ok": True, "document": document, "scope": "single-solid-part-" + kind + "s",
            "observation": result["observation"], "entity": result["entity"],
        })
