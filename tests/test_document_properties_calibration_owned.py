"""Owned-interface capability/control faults. Fakes and plain Python only, no COM."""
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_document_properties_calibration as portable
import test_document_properties_calibration_ci as hosted
import test_document_properties_calibration_watchdog as watchdog


class Stream:
    def __init__(self):
        self.data = io.BytesIO()
    def Write(self, value): return self.data.write(value)
    def Read(self, count): return self.data.read(count)
    def Seek(self, offset, origin): return self.data.seek(offset, origin)


class MarshalLifecycle(unittest.TestCase):
    def fixture(self, release_fails=False):
        events = []
        packet = b'fake-owned-capability-do-not-log'
        def marshal(stream, iid, obj, context, flags):
            self.assertEqual((iid, context, flags), ('IDispatch', 'LOCAL', 'TABLESTRONG'))
            self.assertIs(obj, app._oleobj_)
            events.append('marshal')
            stream.Write(packet)
        def release(stream):
            self.assertEqual(stream.Read(65537), packet)
            events.append('release')
            if release_fails: raise OSError('release fault')
        pc = SimpleNamespace(CreateStreamOnHGlobal=Stream, CoMarshalInterface=marshal, CoReleaseMarshalData=release,
                             IID_IDispatch='IDispatch', MSHCTX_LOCAL='LOCAL', MSHLFLAGS_TABLESTRONG='TABLESTRONG')
        app = SimpleNamespace(_oleobj_=object())
        return pc, app, packet, events

    def test_strong_table_packet_released_once_and_never_recorded(self):
        pc, app, packet, events = self.fixture()
        evidence = {}
        with hosted.ci.owned_interface_packet(pc, app, evidence, lambda label, fn: fn()) as received:
            self.assertEqual(received, packet)
            self.assertEqual(events, ['marshal'])
        self.assertEqual(events, ['marshal', 'release'])
        self.assertTrue(evidence['released'])
        self.assertNotIn(packet.decode(), json.dumps(evidence))

    def test_primary_failure_survives_secondary_release_failure(self):
        pc, app, packet, events = self.fixture(release_fails=True)
        evidence = {}
        with self.assertRaisesRegex(ValueError, 'original worker failure'):
            with hosted.ci.owned_interface_packet(pc, app, evidence, lambda label, fn: fn()):
                raise ValueError('original worker failure')
        self.assertEqual(events, ['marshal', 'release'])
        self.assertFalse(evidence['released'])
        self.assertEqual(evidence['release_failure']['message'], 'release fault')

    def test_release_failure_alone_prevents_success(self):
        pc, app, packet, events = self.fixture(release_fails=True)
        with self.assertRaisesRegex(OSError, 'release fault'):
            with hosted.ci.owned_interface_packet(pc, app, {}, lambda label, fn: fn()):
                pass
        self.assertEqual(events.count('release'), 1)


class OwnedBinding(unittest.TestCase):
    def fixture(self, pid=2940, fail_unmarshal=False):
        c = portable.fixture()
        app = portable.App([])
        app.pid = pid
        c.args.owned_interface_stdin, c.args.isolated_host = True, True
        c._owned_interface_data = b'fake-owned-capability-do-not-log'
        events = []
        def unmarshal(stream, iid):
            self.assertEqual(stream.Read(65537), b'fake-owned-capability-do-not-log')
            events.append('unmarshal')
            if fail_unmarshal: raise ValueError('unmarshal fault')
            return 'owned-dispatch'
        def dispatch(value):
            self.assertEqual(value, 'owned-dispatch')
            events.append('dispatch')
            return app
        c.pythoncom = SimpleNamespace(CreateStreamOnHGlobal=Stream, CoUnmarshalInterface=unmarshal, IID_IDispatch='IDispatch')
        c.client = SimpleNamespace(Dispatch=dispatch)
        return c, app, events

    def test_explicit_owned_packet_still_requires_exact_native_pid(self):
        for pid in (2940, 6608, True, '2940'):
            c, app, events = self.fixture(pid)
            if pid == 2940 and type(pid) is int:
                self.assertIs(c.attach_owned_interface(), app)
                self.assertTrue(c.report['owned_interface_binding']['identity_verified'])
            else:
                with self.assertRaisesRegex(RuntimeError, 'PID mismatch'):
                    c.attach_owned_interface()
                self.assertFalse(c.report['owned_interface_binding']['identity_verified'])
            self.assertEqual(events, ['unmarshal', 'dispatch'])
            self.assertIsNone(c._owned_interface_data)
            self.assertNotIn('fake-owned-capability', json.dumps(c.report))
            self.assertNotIn('rot_binding', c.report)

    def test_unmarshal_failure_has_no_rot_fallback_or_second_unmarshal(self):
        c, app, events = self.fixture(fail_unmarshal=True)
        with self.assertRaisesRegex(ValueError, 'unmarshal fault'):
            c.attach_owned_interface()
        with self.assertRaisesRegex(RuntimeError, 'packet missing'):
            c.attach_owned_interface()
        self.assertEqual(events, ['unmarshal'])
        self.assertNotIn('rot_binding', c.report)

    def test_no_packet_rejected_before_native_and_plain_cli_cannot_inject_one(self):
        c, app, events = self.fixture()
        c._owned_interface_data = None
        with self.assertRaisesRegex(RuntimeError, 'packet missing'):
            c.attach_owned_interface()
        self.assertEqual(events, [])
        with self.assertRaisesRegex(RuntimeError, 'authorized in-memory packet'):
            portable.Calibration(SimpleNamespace(owned_interface_stdin=True, isolated_host=True))


class AuthorizedPipeTransfer(unittest.TestCase):
    def setUp(self):
        self.f = watchdog.WorkerAuthorizationTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.packet = b'portable-fake-capability-do-not-persist'
        self.f.args.owned_interface_data = self.packet
        self.f.args.isolated_host = True
        source = self.f.script.read_text().replace("parser.add_argument('--stage')", "parser.add_argument('--stage')\nparser.add_argument('--isolated-host', action='store_true')\nparser.add_argument('--owned-interface-stdin', action='store_true')")
        source = source.replace('args = parser.parse_args()', "args = parser.parse_args()\nassert args.owned_interface_stdin\nassert globals().pop('_SWCLI_OWNED_INTERFACE') == " + repr(self.packet))
        self.f.script.write_text(source)

    def test_authorized_worker_receives_packet_in_memory_without_files_or_argv(self):
        code, receipt = self.f.run_fixture()
        self.assertEqual(code, 0, receipt)
        self.assertTrue(receipt['owned_interface_transfer_completed'])
        self.assertEqual(receipt['worker_identity']['owned_interface_size'], len(self.packet))
        self.assertIn('--owned-interface-stdin', receipt['worker_identity']['script_args'])
        for path in (self.f.root / 'evidence-driver').iterdir():
            if path.is_file(): self.assertNotIn(self.packet, path.read_bytes())
        self.assertTrue(self.f.marker.exists())

    def test_failed_authorization_sends_nothing_and_never_executes_fixture(self):
        with patch.object(watchdog.driver, 'authorize_worker', side_effect=ValueError('identity rejected')):
            code, receipt = self.f.run_fixture()
        self.assertEqual(code, 1)
        self.assertFalse(receipt['worker_authorized'])
        self.assertFalse(receipt['owned_interface_transfer_completed'])
        self.assertFalse(self.f.marker.exists())
        self.assertFalse(self.f.site_marker.exists())
        for path in (self.f.root / 'evidence-driver').iterdir():
            if path.is_file(): self.assertNotIn(self.packet, path.read_bytes())

    def test_oversized_or_unisolated_packet_rejected_before_popen(self):
        for packet, isolated in ((b'', True), (b'x' * 65537, True), (self.packet, False)):
            with self.subTest(size=len(packet), isolated=isolated):
                self.f.args.owned_interface_data, self.f.args.isolated_host = packet, isolated
                with patch.object(watchdog.driver.subprocess, 'Popen') as popen:
                    with self.assertRaisesRegex(ValueError, 'bounded bytes'):
                        watchdog.driver.worker_config(self.f.args, self.f.script, self.f.source, self.f.root)
                    popen.assert_not_called()
