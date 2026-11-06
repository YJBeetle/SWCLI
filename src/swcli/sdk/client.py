"""Typed SDK dispatcher over the existing swclid TCP transport."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Callable, Dict, Literal, Mapping, Optional, TypedDict, Union, cast
import uuid

from jsonschema import Draft202012Validator

from .. import PROTOCOL_VERSION
from ..daemon.client import DEFAULT_ENDPOINT, call_daemon, parse_endpoint
from ..daemon.timeouts import validate_timeout
from ..file_transfer import FileTransferClient
from ..operation_schemas import OPERATION_CATALOG, validate_operation_request
from ..protocol import load_schema
from ..result_schemas import validate_operation_result
from ._generated import GeneratedAPI
from .runtime import JSONValue, ProtocolError, Response, TLSConfig, TransportError


class _FileReceiptRequired(TypedDict):
    success: Literal[True]
    direction: Literal["upload", "download"]
    transfer_id: str
    path: str
    size_bytes: int
    sha256: str


class FileReceipt(_FileReceiptRequired, total=False):
    local_path: str
    cleanup_error: str


class WorkspaceFiles:
    """High-level bounded streaming between explicitly configured roots."""
    def __init__(self, client: Client, root: Optional[Union[str, Path]]) -> None:
        self._client = client
        self._root = root

    def _transfer(self) -> FileTransferClient:
        client = self._client
        return FileTransferClient(self._root, endpoint=client.endpoint,
            session_id=client.session_id, timeout_seconds=client.timeout_seconds,
            connect_timeout_seconds=client.connect_timeout_seconds, security=client._security)

    def upload(self, source: str, destination: str, *, overwrite: bool = False,
               request_id: Optional[str] = None, resume_transfer: Optional[str] = None,
               progress: Optional[Callable[[int, int], None]] = None) -> FileReceipt:
        return cast(FileReceipt, self._transfer().upload(source, destination, overwrite=overwrite,
            request_id=request_id, resume_transfer=resume_transfer, progress=progress))

    def download(self, source: str, destination: str, *, overwrite: bool = False,
                 request_id: Optional[str] = None,
                 progress: Optional[Callable[[int, int], None]] = None) -> FileReceipt:
        return cast(FileReceipt, self._transfer().download(source, destination, overwrite=overwrite,
            request_id=request_id, progress=progress))


@lru_cache(maxsize=2)
def _envelope_validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(name))


class Client(GeneratedAPI):
    """Synchronous, connection-only SDK. Construction does not start SW or connect.

    Each instance owns a stable default session, not a SOLIDWORKS instance.
    Context and request IDs are explicit; methods never retry or refresh CAS.
    """
    def __init__(self, *, endpoint: Optional[str] = None, session_id: Optional[str] = None,
                 timeout_seconds: float = 600, connect_timeout_seconds: float = 3,
                 tls: Optional[TLSConfig] = None,
                 client_workspace: Optional[Union[str, Path]] = None) -> None:
        self.endpoint = endpoint if endpoint is not None else os.environ.get("SWCLI_ENDPOINT", DEFAULT_ENDPOINT)
        parse_endpoint(self.endpoint)
        self.session_id = (session_id if session_id is not None
                           else os.environ.get("SWCLI_SESSION_ID") or "sdk-" + str(uuid.uuid4()))
        if not self.session_id or len(self.session_id) > 256:
            raise ValueError("SDK session_id must contain 1–256 characters")
        self.timeout_seconds = validate_timeout(timeout_seconds, name="request timeout", margin=10)
        self.connect_timeout_seconds = validate_timeout(connect_timeout_seconds, name="connection timeout")
        self._security = tls.load() if tls is not None else None
        super().__init__()
        root = client_workspace if client_workspace is not None else os.environ.get("SWCLI_CLIENT_WORKSPACE")
        self.files = WorkspaceFiles(self, root)

    def execute(self, operation: str, parameters: Optional[Mapping[str, object]] = None, *,
                request_id: Optional[str] = None, document_id: Optional[str] = None,
                expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None) -> Response[JSONValue]:
        """Dynamic dictionary route for known operations; prefer typed namespace methods."""
        return self._execute(operation, dict(parameters) if parameters is not None else None,
            request_id=request_id, document_id=document_id,
            expected_update_stamp=expected_update_stamp, lease_id=lease_id)

    def _execute(self, operation: str, parameters: Optional[Dict[str, object]] = None, *,
                 request_id: Optional[str] = None, document_id: Optional[str] = None,
                 expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None) -> Response[JSONValue]:
        request_id = str(uuid.uuid4()) if request_id is None else request_id
        values = deepcopy(parameters) if parameters is not None else {}
        envelope: Dict[str, object] = {"api_version": PROTOCOL_VERSION, "request_id": request_id,
            "session_id": self.session_id, "operation": operation, "parameters": values,
            "timeout_ms": max(1, int(self.timeout_seconds * 1000))}
        context = {"document_id": document_id, "expected_update_stamp": expected_update_stamp, "lease_id": lease_id}
        envelope.update({key: value for key, value in context.items() if value is not None})
        # Finite JSON, shared conditional checks, exact schema and context before IO.
        json.dumps(envelope, ensure_ascii=False, allow_nan=False).encode("utf-8")
        _envelope_validator("request").validate(envelope)
        validate_operation_request(operation, values, document_id=document_id,
            expected_update_stamp=expected_update_stamp, lease_id=lease_id)
        Draft202012Validator(OPERATION_CATALOG[operation].parameters).validate(values)
        try:
            options = {"security": self._security} if self._security is not None else {}
            response = call_daemon(operation, values, endpoint=self.endpoint, session_id=self.session_id,
                timeout_seconds=self.timeout_seconds, connect_timeout_seconds=self.connect_timeout_seconds,
                request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp,
                lease_id=lease_id, **options)
        except Exception as exc:
            raise TransportError(operation, request_id, exc) from exc
        try:
            _envelope_validator("response").validate(response)
            if response["request_id"] != request_id:
                raise ValueError("Daemon response request_id differs from the submitted ID")
            if response["success"]:
                validate_operation_result(operation, response["result"])
        except Exception as exc:
            raise ProtocolError(operation, request_id, response, exc) from exc
        return Response(cast(Dict[str, JSONValue], response))
