"""SDK responses and explicit failure handling; no native lifecycle ownership."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Generic, List, Mapping, Optional, TypeVar, Union, cast

JSONValue = Union[None, bool, int, float, str, List["JSONValue"], Dict[str, "JSONValue"]]
from ..secure_transport import ClientSecurity

T = TypeVar("T")


class Unset(Enum):
    """An omitted optional parameter, distinct from false, zero, empty or null."""
    VALUE = "unset"


UNSET = Unset.VALUE


@dataclass(frozen=True)
class TLSConfig:
    """Per-client certificate-verified TLS with a bearer token file."""
    token_file: Union[str, Path]
    ca_file: Optional[Union[str, Path]] = None
    server_name: Optional[str] = None

    def load(self) -> ClientSecurity:
        settings = {"SWCLI_TLS": "1", "SWCLI_AUTH_TOKEN_FILE": str(self.token_file)}
        if self.ca_file is not None:
            settings["SWCLI_TLS_CA_FILE"] = str(self.ca_file)
        if self.server_name is not None:
            settings["SWCLI_TLS_SERVER_NAME"] = self.server_name
        return ClientSecurity.from_environment(settings)


@dataclass(frozen=True)
class Error:
    code: str
    message: str
    details: JSONValue = None


class RemoteError(RuntimeError):
    """A received daemon/native refusal, including any partial result in response."""
    def __init__(self, response: Response[object]):
        error = response.error
        super().__init__(f"{error.code}: {error.message}" if error else "SWCLI operation failed")
        self.response = response
        self.request_id = response.request_id
        self.error = error
        self.outcome_unknown = False


class TransportError(ConnectionError):
    """No usable reply; preserve the ID and inspect state before another write."""
    def __init__(self, operation: str, request_id: str, cause: Exception):
        super().__init__(str(cause))
        self.operation = operation
        self.request_id = request_id
        self.phase = getattr(cause, "_swcli_transport_phase", None)
        self.outcome_unknown = self.phase not in ("connect", "configuration", "tls", "authenticate")


class ProtocolError(ValueError):
    def __init__(self, operation: str, request_id: str, raw: object, cause: Exception):
        message = str(getattr(cause, "message", cause))
        if len(message) > 1024:
            message = message[:1024] + "…"
        super().__init__(f"Invalid {operation} response: {message}")
        self.operation, self.request_id, self.raw = operation, request_id, raw
        self.outcome_unknown = True


@dataclass(frozen=True)
class Response(Generic[T]):
    """Validated protocol envelope. Inspect it or explicitly require success."""
    raw: Mapping[str, JSONValue]

    @property
    def request_id(self) -> str:
        return cast(str, self.raw["request_id"])

    @property
    def success(self) -> bool:
        """Protocol success; native result.ok may still report a refusal."""
        return self.raw["success"] is True

    @property
    def ok(self) -> bool:
        result = self.raw.get("result")
        return self.success and not (isinstance(result, dict) and result.get("ok") is False)

    @property
    def result(self) -> Optional[T]:
        return cast(Optional[T], self.raw.get("result"))

    @property
    def duration_ms(self) -> float:
        return float(cast(Union[int, float], self.raw["duration_ms"]))

    @property
    def replayed(self) -> bool:
        return self.raw.get("replayed") is True

    @property
    def error(self) -> Optional[Error]:
        value = self.raw.get("error")
        if not isinstance(value, dict):
            result = self.raw.get("result")
            value = result.get("error") if isinstance(result, dict) else None
        if not isinstance(value, dict):
            return None
        return Error(str(value.get("code", value.get("type", "OperationFailed"))),
                     str(value.get("message", "")), value.get("details"))

    def require_result(self) -> T:
        """Raise for a protocol/native refusal without discarding its raw receipt."""
        if not self.ok:
            raise RemoteError(cast("Response[object]", self))
        return cast(T, self.raw["result"])
