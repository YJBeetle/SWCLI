"""Newline-delimited JSON client for the local swclid service."""

from __future__ import annotations

import json
import os
import socket
import uuid
from typing import Any, Dict, Optional, Tuple

from .. import PROTOCOL_VERSION


DEFAULT_ENDPOINT = "127.0.0.1:18495"
MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def parse_endpoint(endpoint: str) -> Tuple[str, int]:
    host, separator, raw_port = endpoint.rpartition(":")
    if not separator or not host or not raw_port:
        raise ValueError("endpoint must use HOST:PORT")
    port = int(raw_port)
    if not 1 <= port <= 65535:
        raise ValueError("endpoint port must be between 1 and 65535")
    return host, port


def call_daemon(
    operation: str,
    parameters: Optional[Dict[str, Any]] = None,
    *,
    endpoint: Optional[str] = None,
    timeout_seconds: float = 600.0,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Submit one typed operation to swclid and return its protocol response."""

    selected_endpoint = endpoint or os.environ.get(
        "SWCLI_ENDPOINT", DEFAULT_ENDPOINT
    )
    host, port = parse_endpoint(selected_endpoint)
    request = {
        "api_version": PROTOCOL_VERSION,
        "request_id": request_id or str(uuid.uuid4()),
        "operation": operation,
        "parameters": parameters or {},
        "timeout_ms": max(1, int(timeout_seconds * 1000)),
    }
    encoded = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    ) + b"\n"

    with socket.create_connection((host, port), timeout=timeout_seconds) as connection:
        connection.settimeout(timeout_seconds + 10.0)
        connection.sendall(encoded)
        reader = connection.makefile("rb")
        line = reader.readline(MAX_RESPONSE_BYTES + 1)
    if not line:
        raise ConnectionError("swclid closed the connection without a response")
    if len(line) > MAX_RESPONSE_BYTES:
        raise ValueError("swclid response exceeds the maximum supported size")
    response = json.loads(line.decode("utf-8"))
    if response.get("request_id") != request["request_id"]:
        raise ValueError("swclid returned a mismatched request_id")
    return response
