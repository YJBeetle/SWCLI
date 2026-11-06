"""Real TLS sockets authenticate before RPC dispatch; configuration never falls back."""

from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from swcli.daemon.client import call_daemon
from swcli.daemon.server import SwclidServer
from swcli.secure_transport import ClientSecurity, ServerSecurity, AuthenticationFailed, apply_runtime_environment


def certificate(directory):
    directory.mkdir()
    cert, key = directory / "server.pem", directory / "key.pem"
    if importlib.util.find_spec("cryptography") is not None:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        import ipaddress
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        value = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(private.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=2))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                key_encipherment=True, data_encipherment=False, key_agreement=False,
                key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .sign(private, hashes.SHA256()))
        cert.write_bytes(value.public_bytes(serialization.Encoding.PEM))
        key.write_bytes(private.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    elif shutil.which("openssl"):
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(cert), "-days", "2", "-subj", "/CN=localhost",
            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
            "-addext", "basicConstraints=critical,CA:TRUE",
            "-addext", "keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        raise unittest.SkipTest("TLS integration needs cryptography or openssl for ephemeral test certificates")
    return cert, key


class SecurityConfigurationTests(unittest.TestCase):
    def test_credentials_never_enable_plaintext_or_disable_verification(self):
        for env in ({"SWCLI_AUTH_TOKEN_FILE": "secret"}, {"SWCLI_TLS": "0", "SWCLI_TLS_CA_FILE": "ca"},
                    {"SWCLI_TLS": "1"}, {"SWCLI_TLS": "perhaps"}):
            with self.subTest(env=env), self.assertRaises(ValueError):
                ClientSecurity.from_environment(env)
        self.assertIsNone(ClientSecurity.from_environment({}).context)

    def test_server_partial_config_fails_before_listener_or_native_work(self):
        with self.assertRaisesRegex(ValueError, "certificate"):
            ServerSecurity.load(cert="cert.pem")

    def test_bootstrap_accepts_only_paths_and_flags_not_arbitrary_environment(self):
        with self.assertRaises(ValueError):
            apply_runtime_environment({"GITHUB_TOKEN": "not-allowed"})
        with patch.dict(os.environ, {}, clear=True):
            apply_runtime_environment({"SWCLI_WORKSPACE": "C:\\Workspace\\files"})
            self.assertEqual(os.environ["SWCLI_WORKSPACE"], "C:\\Workspace\\files")


class TLSSocketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.cert, cls.key = certificate(cls.root / "trusted")
        cls.other_cert, _ = certificate(cls.root / "untrusted")
        cls.token = secrets.token_urlsafe(32)
        cls.token_file = cls.root / "token"
        cls.token_file.write_text(cls.token)
        cls.wrong_token_file = cls.root / "wrong-token"
        cls.wrong_token_file.write_text(secrets.token_urlsafe(32))

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.manager = Mock()
        self.manager.health.return_value = {"server_version": "test", "worker_alive": True}
        self.manager.call.side_effect = lambda r: {"api_version": "swcli/v1", "request_id": r["request_id"],
            "success": True, "duration_ms": 0, "result": {"ok": True}}
        self.server = SwclidServer(("127.0.0.1", 0), self.manager,
            security=ServerSecurity.load(str(self.cert), str(self.key), str(self.token_file)))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)
        self.endpoint = "127.0.0.1:" + str(self.server.server_address[1])
        env = {"SWCLI_TLS_CA_FILE": str(self.cert), "SWCLI_TLS_SERVER_NAME": "localhost",
               "SWCLI_AUTH_TOKEN_FILE": str(self.token_file)}
        p = patch.dict(os.environ, env)
        p.start(); self.addCleanup(p.stop)

    def test_actual_tls_and_token_protect_rpc_and_are_not_forwarded_or_logged(self):
        result = call_daemon("document.list", {}, endpoint=self.endpoint, timeout_seconds=3)
        self.assertTrue(result["success"])
        request = self.manager.call.call_args.args[0]
        self.assertNotIn(self.token, json.dumps(request))
        self.assertNotIn("token", request)
        security = ClientSecurity.from_environment()
        self.assertTrue(security.context.check_hostname)
        self.assertEqual(security.context.verify_mode, ssl.CERT_REQUIRED)
        self.assertNotIn(self.token, repr(security))

    def test_wrong_token_cannot_dispatch_shutdown_or_any_rpc(self):
        with patch.dict(os.environ, {"SWCLI_AUTH_TOKEN_FILE": str(self.wrong_token_file)}):
            with self.assertRaises(AuthenticationFailed) as error:
                call_daemon("daemon.shutdown", {}, endpoint=self.endpoint, timeout_seconds=3)
        self.assertEqual(error.exception._swcli_transport_phase, "authenticate")
        self.manager.call.assert_not_called(); self.manager.shutdown.assert_not_called()
        self.assertNotIn(self.wrong_token_file.read_text(), str(error.exception))

    def test_bad_ca_or_wrong_hostname_fails_without_plaintext_retry(self):
        for env in ({"SWCLI_TLS_CA_FILE": str(self.other_cert)}, {"SWCLI_TLS_SERVER_NAME": "wrong.example"}):
            with self.subTest(env=env), patch.dict(os.environ, env):
                with self.assertRaises(ssl.SSLError) as error:
                    call_daemon("daemon.health", {}, endpoint=self.endpoint, timeout_seconds=3)
                self.assertEqual(error.exception._swcli_transport_phase, "tls")
        self.manager.health.assert_not_called()

    def test_plain_client_is_refused_by_tls_listener(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises((OSError, ConnectionError, ValueError)):
                call_daemon("daemon.shutdown", {}, endpoint=self.endpoint, timeout_seconds=1)
        self.manager.shutdown.assert_not_called()

    def test_invalid_auth_header_never_echoes_credential_material(self):
        security = ServerSecurity.load(str(self.cert), str(self.key), str(self.token_file))
        writer = io.BytesIO()
        self.assertFalse(security.authenticate(io.BytesIO(b'{"token":"private-value"}\n'), writer))
        self.assertEqual(json.loads(writer.getvalue()), {"authenticated": False})
