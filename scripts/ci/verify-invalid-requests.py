"""Verify malformed wire requests fail without changing a real daemon's host."""

import json
import os
import socket

from swcli import PROTOCOL_VERSION
from swcli.daemon.client import (
    DEFAULT_ENDPOINT,
    MAX_RESPONSE_BYTES,
    call_daemon,
    parse_endpoint,
)


def require_success(response):
    if not response.get("success"):
        raise RuntimeError(f"daemon operation failed: {response.get('error')}")
    return response["result"]


def main():
    endpoint = os.environ.get("SWCLI_ENDPOINT", DEFAULT_ENDPOINT)
    host, port = parse_endpoint(endpoint)
    before = require_success(call_daemon("daemon.health", endpoint=endpoint))
    documents = require_success(call_daemon("document.list", endpoint=endpoint))
    if not before["host_connected"]:
        raise RuntimeError("invalid-request smoke needs a connected real host")
    base = {
        "api_version": PROTOCOL_VERSION,
        "request_id": "invalid-wire-smoke",
        "operation": "document.create",
        "parameters": {},
    }
    for changed in (
        {"timeout_ms": True},
        {"timeout_ms": 10**1000},
        {"session_id": "invalid\ud800"},
        {"request_id": "invalid\ud800"},
        {"parameters": {"unexpected": float("nan")}},
    ):
        # Deliberately bypass the client's strict encoder to test the daemon's
        # boundary against a nonconforming caller. No COM code is executed here.
        encoded = json.dumps({**base, **changed}).encode("utf-8") + b"\n"
        with socket.create_connection((host, port), timeout=3) as connection:
            connection.settimeout(5)
            connection.sendall(encoded)
            with connection.makefile("rb") as reader:
                line = reader.readline(MAX_RESPONSE_BYTES + 1)
        if not line or len(line) > MAX_RESPONSE_BYTES:
            raise RuntimeError("invalid request did not return a bounded response")
        response = json.loads(line.decode("utf-8"))
        if (
            response.get("success")
            or response.get("error", {}).get("code") != "ValueError"
        ):
            raise RuntimeError(f"invalid request reached execution: {response}")
        response["request_id"].encode("utf-8")
    after = require_success(call_daemon("daemon.health", endpoint=endpoint))
    after_documents = require_success(call_daemon("document.list", endpoint=endpoint))
    if (
        not after["host_connected"]
        or after["host"]["process_id"] != before["host"]["process_id"]
        or after_documents != documents
    ):
        raise RuntimeError(
            "invalid requests changed the running host or document state"
        )
    print("Invalid wire requests rejected; real host PID and documents unchanged")


if __name__ == "__main__":
    main()
