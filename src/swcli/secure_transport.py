"""Optional TLS + bearer-file authentication for the existing daemon protocol."""

from dataclasses import dataclass, field
import hashlib
import hmac
import json
import os
import ssl
from typing import Mapping, Optional

AUTH_BYTES = 4096
HANDSHAKE_SECONDS = 5
RUNTIME_ENV = ("SWCLI_SERVER_TLS_CERT", "SWCLI_SERVER_TLS_KEY", "SWCLI_SERVER_AUTH_TOKEN_FILE",
               "SWCLI_WORKSPACE", "SWCLI_WORKSPACE_MAX_BYTES", "SWCLI_TLS", "SWCLI_TLS_CA_FILE",
               "SWCLI_TLS_SERVER_NAME", "SWCLI_AUTH_TOKEN_FILE")


class AuthenticationFailed(PermissionError):
    def __init__(self):
        super().__init__("Daemon authentication failed")
        self._swcli_transport_phase = "authenticate"


def read_token(path):
    try:
        with open(path, "rb") as stream:
            raw = stream.read(1025)
        token = raw.decode("utf-8").strip()
        if (len(raw) > 1024 or not 32 <= len(token) <= 512 or not token.isascii()
                or any(c.isspace() for c in token)):
            raise ValueError()
        return token
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError("Authentication token file must contain 32–512 non-whitespace ASCII characters") from None


@dataclass
class ClientSecurity:
    context: object = field(default=None, repr=False)
    token: str = field(default="", repr=False)
    server_name: str = ""

    @classmethod
    def from_environment(cls, env: Optional[Mapping[str, str]] = None) -> "ClientSecurity":
        env = os.environ if env is None else env
        enabled = env.get("SWCLI_TLS", "").strip().lower()
        ca = env.get("SWCLI_TLS_CA_FILE")
        token_file = env.get("SWCLI_AUTH_TOKEN_FILE")
        name = env.get("SWCLI_TLS_SERVER_NAME", "")
        if enabled not in ("", "0", "1", "false", "true"):
            raise ValueError("SWCLI_TLS must be 0 or 1")
        if enabled in ("0", "false") and (ca or token_file or name):
            raise ValueError("TLS settings conflict with SWCLI_TLS=0")
        tls = enabled in ("1", "true") or bool(ca)
        if not tls:
            if token_file or name:
                raise ValueError("Authentication and server-name configuration require TLS")
            return cls()
        if not token_file:
            raise ValueError("TLS connections require SWCLI_AUTH_TOKEN_FILE")
        context = ssl.create_default_context(cafile=ca)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return cls(context, read_token(token_file), name)

    def wrap(self, connection, host):
        if self.context is None:
            return connection
        connection.settimeout(HANDSHAKE_SECONDS)
        try:
            return self.context.wrap_socket(connection, server_hostname=self.server_name or host)
        except Exception as exc:
            exc._swcli_transport_phase = "tls"
            connection.close()
            raise

    def authenticate(self, connection, reader):
        if self.context is None:
            return
        try:
            connection.sendall(json.dumps({"authentication": "bearer", "token": self.token}).encode() + b"\n")
            raw = reader.readline(AUTH_BYTES + 1)
            if len(raw) > AUTH_BYTES or json.loads(raw).get("authenticated") is not True:
                raise AuthenticationFailed()
        except (ValueError, OSError, ConnectionError, AttributeError, TypeError) as exc:
            if isinstance(exc, AuthenticationFailed):
                raise
            raise AuthenticationFailed() from None


@dataclass
class ServerSecurity:
    context: object = field(default=None, repr=False)
    token_digest: bytes = field(default=b"", repr=False)

    @classmethod
    def load(cls, cert=None, key=None, token_file=None):
        if not any((cert, key, token_file)):
            return cls()
        if not all((cert, key, token_file)):
            raise ValueError("TLS server requires certificate, private key and authentication token file")
        token = read_token(token_file)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        def no_prompt():
            raise ValueError("Encrypted TLS keys require a noninteractive key provider")
        context.load_cert_chain(cert, key, password=no_prompt)
        return cls(context, hashlib.sha256(token.encode()).digest())

    def authenticate(self, reader, writer):
        if self.context is None:
            return True
        accepted = False
        try:
            raw = reader.readline(AUTH_BYTES + 1)
            value = json.loads(raw) if len(raw) <= AUTH_BYTES else {}
            token = value.get("token")
            if value.get("authentication") == "bearer" and isinstance(token, str) and len(token) <= 512:
                accepted = hmac.compare_digest(hashlib.sha256(token.encode()).digest(), self.token_digest)
        except (ValueError, UnicodeError, OSError, AttributeError):
            pass
        writer.write(json.dumps({"authenticated": accepted}).encode() + b"\n")
        writer.flush()
        return accepted


def runtime_environment():
    """Only configuration paths/flags, never credential contents, cross the broker."""
    return {key: os.environ[key] for key in RUNTIME_ENV if key in os.environ}


def apply_runtime_environment(values):
    if (not isinstance(values, dict) or set(values) - set(RUNTIME_ENV)
            or any(not isinstance(v, str) or len(v) > 4096 for v in values.values())):
        raise ValueError("Invalid broker runtime settings")
    os.environ.update(values)
