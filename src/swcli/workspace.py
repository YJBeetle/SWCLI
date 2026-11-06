"""Bounded supervisor-side workspace transfers, independent of COM workers."""

import base64
from collections import OrderedDict
import hashlib
import os
import secrets
import threading
import time

from .safe_workspace import CHUNK_BYTES, SafeWorkspace, file_hash, relative_parts, signature

DEFAULT_MAX_BYTES = 1024 ** 3
MAX_FILE_BYTES = 1024 ** 4
TRANSFER_TTL = 1800

_STRING = {"type": "string", "minLength": 1}
_ID = {"type": "string", "pattern": "^[0-9a-f]{48}$"}
_SIZE = {"type": "integer", "minimum": 0, "maximum": MAX_FILE_BYTES}
_HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
_CHUNK = {"type": "integer", "minimum": 1, "maximum": CHUNK_BYTES}
_DEFINITIONS = {
    "upload-begin": ({"path": _STRING, "size_bytes": _SIZE, "sha256": _HASH, "overwrite": {"type": "boolean"}}, ("path", "size_bytes", "sha256")),
    "upload-chunk": ({"transfer_id": _ID, "offset": _SIZE, "data": {"type": "string", "maxLength": 4 * ((CHUNK_BYTES + 2) // 3)}}, ("transfer_id", "offset", "data")),
    "upload-status": ({"transfer_id": _ID}, ("transfer_id",)),
    "upload-commit": ({"transfer_id": _ID}, ("transfer_id",)),
    "upload-abort": ({"transfer_id": _ID}, ("transfer_id",)),
    "download-begin": ({"path": _STRING}, ("path",)),
    "download-chunk": ({"transfer_id": _ID, "offset": _SIZE, "length": _CHUNK}, ("transfer_id", "offset", "length")),
    "download-end": ({"transfer_id": _ID}, ("transfer_id",)),
}


def definitions():
    return {"workspace." + key: value for key, value in _DEFINITIONS.items()}


def result_schema(name):
    fields = {"transfer_id": _ID, "path": _STRING, "size_bytes": _SIZE, "sha256": _HASH,
              "offset": _SIZE, "chunk_bytes": _CHUNK, "state": {"enum": ["uploading", "committed", "aborted", "failed", "downloading", "closed"]}}
    required = ["transfer_id", "path", "size_bytes", "sha256", "offset", "chunk_bytes", "state"]
    if name == "workspace.download-chunk":
        fields["data"] = {"type": "string", "maxLength": 4 * ((CHUNK_BYTES + 2) // 3)}
        required.append("data")
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://swcli.dev/schema/v1/results/{name}.schema.json",
            "title": f"SWCLI {name} result", "type": "object", "additionalProperties": False, "properties": fields, "required": required}


class WorkspaceStore:
    def __init__(self, root, max_bytes=DEFAULT_MAX_BYTES, *, clock=time.monotonic):
        if isinstance(max_bytes, bool) or not 1 <= int(max_bytes) <= MAX_FILE_BYTES:
            raise ValueError("Workspace maximum must be between 1 byte and 1 TiB")
        self.root = SafeWorkspace(root)
        self.max_bytes = int(max_bytes)
        self.clock = clock
        self.lock = threading.RLock()
        self.idle = threading.Condition(self.lock)
        self.transfers = OrderedDict()
        self.closed = False

    def describe(self):
        return {"root": str(self.root.path), "max_file_bytes": self.max_bytes, "chunk_bytes": CHUNK_BYTES,
                "active_upload_limit": 4, "active_download_limit": 8, "expires_after_seconds": TRANSFER_TTL}

    def _dispose(self, record):
        resource = record.pop("resource", None)
        if resource is not None:
            resource.close()

    def _expire(self):
        now = self.clock()
        for key, record in list(self.transfers.items()):
            if not record.get("hashing") and now - record["used"] > TRANSFER_TTL:
                self._dispose(record)
                del self.transfers[key]
        completed = [key for key, record in self.transfers.items() if record["state"] not in ("uploading", "downloading")]
        for key in completed[:-128]:
            self._dispose(self.transfers[key])
            del self.transfers[key]

    @staticmethod
    def _receipt(record):
        return {key: record[key] for key in ("transfer_id", "path", "size_bytes", "sha256", "offset", "state")} | {"chunk_bytes": CHUNK_BYTES}

    def _get(self, transfer_id, session, direction):
        record = self.transfers.get(transfer_id)
        if record is None or record["session"] != session or record["direction"] != direction:
            raise ValueError("Unknown or expired workspace transfer in this session")
        while record.get("hashing"):
            self.idle.wait()
        if self.closed:
            raise RuntimeError("Workspace is closed")
        record["used"] = self.clock()
        return record

    def execute(self, request):
        name = request["operation"].removeprefix("workspace.")
        p = request["parameters"]
        session = request.get("session_id") or "default"
        if len(session) > 256:
            raise ValueError("Workspace session ID exceeds 256 characters")
        with self.lock:
            if self.closed:
                raise RuntimeError("Workspace is closed")
            self._expire()
            if name in ("upload-begin", "download-begin"):
                return self._begin(name, p, session, request["request_id"])
            direction = "upload" if name.startswith("upload-") else "download"
            record = self._get(p["transfer_id"], session, direction)
            if name == "upload-status":
                return self._receipt(record)
            if name in ("upload-abort", "download-end"):
                self._dispose(record)
                if record["state"] not in ("committed", "aborted", "closed"):
                    record["state"] = "aborted" if direction == "upload" else "closed"
                return self._receipt(record)
            if name == "upload-commit" and record["state"] == "committed":
                return self._receipt(record)
            if record["state"] != ("uploading" if direction == "upload" else "downloading"):
                raise ValueError("Workspace transfer is not active")
            resource = record["resource"]
            stream = resource.stream if direction == "upload" else resource
            if name == "upload-chunk":
                encoded = p["data"]
                if len(encoded) > 4 * ((CHUNK_BYTES + 2) // 3):
                    raise ValueError("Upload chunk exceeds the chunk limit")
                try:
                    data = base64.b64decode(encoded, validate=True)
                except (ValueError, UnicodeError):
                    raise ValueError("Upload chunk must be valid base64") from None
                offset = p["offset"]
                if not data or len(data) > CHUNK_BYTES or offset + len(data) > record["size_bytes"]:
                    raise ValueError("Upload chunk exceeds the declared file or chunk size")
                if offset < record["offset"]:
                    stream.seek(offset)
                    if offset + len(data) > record["offset"] or stream.read(len(data)) != data:
                        raise ValueError("Replayed upload chunk does not match stored bytes")
                elif offset == record["offset"]:
                    stream.seek(offset)
                    try:
                        if stream.write(data) != len(data):
                            raise OSError("Short workspace write")
                        stream.flush()
                    except OSError:
                        record["state"] = "failed"
                        raise
                    record["offset"] += len(data)
                else:
                    raise ValueError("Upload chunk offset is not contiguous")
            elif name == "upload-commit":
                if record["offset"] != record["size_bytes"]:
                    raise ValueError("Workspace upload is incomplete")
                if signature(stream)[2] != record["size_bytes"] or self._hash(stream, record) != record["sha256"]:
                    record["state"] = "failed"
                    raise ValueError("Workspace upload size or SHA256 mismatch")
                resource.publish()
                record["state"] = "committed"
                self._dispose(record)
            elif name == "download-chunk":
                if signature(stream) != record["signature"]:
                    record["state"] = "failed"
                    raise ValueError("Workspace source changed during download")
                if not 1 <= p["length"] <= CHUNK_BYTES or not 0 <= p["offset"] <= record["size_bytes"]:
                    raise ValueError("Invalid download range")
                stream.seek(p["offset"])
                data = stream.read(min(p["length"], record["size_bytes"] - p["offset"]))
                if signature(stream) != record["signature"]:
                    record["state"] = "failed"
                    raise ValueError("Workspace source changed during download")
                result = self._receipt(record)
                result.update(offset=p["offset"], data=base64.b64encode(data).decode("ascii"))
                return result
            else:
                raise ValueError("Unknown workspace operation")
            return self._receipt(record)

    def _begin(self, name, p, session, request_id):
        path = "/".join(relative_parts(p["path"]))
        direction = name.split("-")[0]
        fingerprint = (name, path, p.get("size_bytes"), p.get("sha256"), p.get("overwrite", False))
        for existing in self.transfers.values():
            if existing["session"] == session and existing["request_id"] == request_id:
                if existing["fingerprint"] != fingerprint:
                    raise ValueError("Workspace request ID was reused with different parameters")
                while existing.get("hashing"):
                    self.idle.wait()
                existing["used"] = self.clock()
                return self._receipt(existing)
        limit = 4 if direction == "upload" else 8
        if sum(r["direction"] == direction and "resource" in r for r in self.transfers.values()) >= limit:
            raise ValueError("Workspace active transfer limit reached")
        if direction == "upload":
            if p["size_bytes"] > self.max_bytes:
                raise ValueError("Workspace file exceeds the configured maximum")
            resource = self.root.stage(path, overwrite=p.get("overwrite", False))
            size, digest = p["size_bytes"], p["sha256"]
            identity = None
        else:
            resource = self.root.open_read(path)
            try:
                identity = signature(resource)
                size = identity[2]
                if size > self.max_bytes:
                    raise ValueError("Workspace file exceeds the configured maximum")
                digest = ""
            except BaseException:
                resource.close()
                raise
        record = dict(transfer_id=secrets.token_hex(24), path=path, size_bytes=size, sha256=digest,
                      offset=0, state=direction + "ing", direction=direction, session=session,
                      request_id=request_id, fingerprint=fingerprint, used=self.clock(), resource=resource,
                      signature=identity)
        self.transfers[record["transfer_id"]] = record
        if direction == "download":
            try:
                record["sha256"] = self._hash(resource, record)
                if signature(resource) != identity:
                    raise ValueError("Workspace source changed while hashing")
            except BaseException:
                self._dispose(record)
                self.transfers.pop(record["transfer_id"], None)
                raise
        return self._receipt(record)

    def _hash(self, stream, record):
        # Reserve the transfer slot and pin its resource while other transfers
        # continue. Operations on this same transfer wait on the condition.
        record["hashing"] = True
        self.lock.release()
        try:
            return file_hash(stream)
        finally:
            self.lock.acquire()
            record["hashing"] = False
            record["used"] = self.clock()
            self.idle.notify_all()

    def close(self):
        with self.lock:
            self.closed = True
            while any(r.get("hashing") for r in self.transfers.values()):
                self.idle.wait()
            errors = []
            for record in self.transfers.values():
                try:
                    self._dispose(record)
                except OSError as exc:
                    errors.append(exc)
            self.transfers.clear()
            self.root.close()
            if errors:
                raise errors[0]
