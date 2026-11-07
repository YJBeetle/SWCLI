import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.hosts import windows_definition_identity as identity
from swcli.hosts.native_trace import native_call, trace_native_request


class DefinitionIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "sldworks.tlb"
        self.path.write_bytes(b"installed official fixture")
        self.stream = io.StringIO()
        self.info = mock.Mock()
        self.info.GetDocumentation.return_value = ("IExtrudeFeatureData2", "", 0, "")
        self.info.GetTypeAttr.return_value = SimpleNamespace(iid="{EXTRUDE2}", typekind=4)
        self.library = mock.Mock()
        self.library.GetLibAttr.return_value = ("{SWLIB}", 0, 3, 33, 0, 0)
        self.library.GetTypeInfoCount.return_value = 1
        self.library.GetDocumentation.return_value = self.info.GetDocumentation.return_value
        self.library.GetTypeInfo.return_value = self.info
        self.info.GetContainingTypeLib.return_value = (self.library, 0)
        self.com = SimpleNamespace(LoadTypeLib=mock.Mock(return_value=self.library),
                                   TKIND_INTERFACE=3, TKIND_DISPATCH=4)
        self.ole = mock.Mock()
        self.ole.GetTypeInfo.return_value = self.info
        self.definition = SimpleNamespace(_oleobj_=self.ole)
        identity._installed_catalog.cache_clear()
        self.addCleanup(identity._installed_catalog.cache_clear)
        patches = [mock.patch.dict(os.environ, SWCLI_TRACE_NATIVE_CALLS="", SWCLI_TRACE_DEFINITION_INTERFACES="1",
                                   SWCLI_SLDWORKS_TYPELIB=str(self.path)),
                   mock.patch.dict("sys.modules", pythoncom=self.com),
                   mock.patch("sys.stderr", self.stream)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def observe(self):
        with trace_native_request("req-identity", "feature.extrude"):
            result = native_call("read", "GetDefinition", lambda: self.definition)
        self.assertIs(result, self.definition)
        return json.loads(self.stream.getvalue())

    def test_exact_returned_iid_name_and_library_match_official_catalog(self):
        record = self.observe()
        self.assertEqual(record["status"], "matched")
        self.assertIs(record["returned_typeinfo_matches_v2"], True)
        self.assertEqual(record["request_id"], "req-identity")
        self.assertEqual(record["sequence"], 1)
        self.assertEqual(record["matching_official_interfaces"], ["IExtrudeFeatureData2"])
        self.com.LoadTypeLib.assert_called_once_with(str(self.path))
        self.ole.QueryInterface.assert_not_called()
        self.assertEqual(self.ole.method_calls, [mock.call.GetTypeInfo()])

    def test_all_three_names_are_collected_without_guessed_iids(self):
        for name in identity._INTERFACES:
            with self.subTest(name=name):
                identity._installed_catalog.cache_clear()
                self.stream.seek(0); self.stream.truncate()
                self.info.GetDocumentation.return_value = (name, "", 0, "")
                self.library.GetDocumentation.return_value = (name, "", 0, "")
                self.assertEqual(self.observe()["matching_official_interfaces"], [name])

    def test_same_name_different_iid_does_not_prove_v2(self):
        returned = mock.Mock(wraps=self.info)
        returned.GetTypeAttr.return_value = SimpleNamespace(iid="{EXTRUDE1}", typekind=4)
        self.ole.GetTypeInfo.return_value = returned
        record = self.observe()
        self.assertEqual(record["status"], "unmatched")
        self.assertIs(record["returned_typeinfo_matches_v2"], False)
        self.ole.QueryInterface.assert_not_called()

    def test_coclass_or_foreign_library_does_not_match(self):
        for kind, guid in ((5, "{SWLIB}"), (4, "{OTHER}")):
            with self.subTest(kind=kind, guid=guid):
                self.stream.seek(0); self.stream.truncate()
                returned = mock.Mock(wraps=self.info)
                returned.GetTypeAttr.return_value = SimpleNamespace(iid="{EXTRUDE2}", typekind=kind)
                foreign = mock.Mock()
                foreign.GetLibAttr.return_value = (guid, 0, 3, 33, 0, 0)
                returned.GetContainingTypeLib.return_value = (foreign, 0)
                self.ole.GetTypeInfo.return_value = returned
                self.assertIs(self.observe()["returned_typeinfo_matches_v2"], False)

    def test_diagnostic_unavailable_retains_partial_evidence_and_original_object(self):
        self.com.LoadTypeLib.side_effect = OSError("private diagnostic error")
        record = self.observe()
        self.assertEqual(record["status"], "unavailable")
        self.assertEqual(record["returned_typeinfo"]["iid"], "{EXTRUDE2}")
        self.assertEqual(record["diagnostic_error_type"], "OSError")
        self.assertNotIn("private diagnostic error", self.stream.getvalue())

    def test_non_absolute_path_is_refused_before_load(self):
        with self.assertRaises(ValueError):
            identity._installed_catalog("sldworks.tlb")
        self.com.LoadTypeLib.assert_not_called()

    def test_off_is_silent_and_never_reads_identity(self):
        os.environ["SWCLI_TRACE_DEFINITION_INTERFACES"] = ""
        with trace_native_request("req-off", "feature.extrude"):
            self.assertIs(native_call("read", "GetDefinition", lambda: self.definition), self.definition)
        self.ole.GetTypeInfo.assert_not_called()
        self.assertEqual(self.stream.getvalue(), "")

    def test_observer_or_stream_failure_cannot_replace_return_value(self):
        with mock.patch.object(identity, "record_definition_identity", side_effect=OSError):
            with trace_native_request("req-fail", "feature.extrude"):
                self.assertIs(native_call("read", "GetDefinition", lambda: self.definition), self.definition)
        with mock.patch.object(identity.sys, "stderr", mock.Mock(write=mock.Mock(side_effect=OSError))):
            identity.record_definition_identity(self.definition)

    def test_outer_get_definition_boundary_does_not_duplicate_identity_reads(self):
        with trace_native_request("req-fillet", "feature.fillet"):
            result = native_call("fillet", "GetDefinition", lambda:
                                 native_call("read", "GetDefinition", lambda: self.definition))
        self.assertIs(result, self.definition)
        self.ole.GetTypeInfo.assert_called_once_with()
        self.assertEqual(len(self.stream.getvalue().splitlines()), 1)

    def test_native_error_retained_and_no_identity_observation(self):
        failure = RuntimeError("original business failure")
        with self.assertRaises(RuntimeError) as caught:
            with trace_native_request("req-error", "feature.extrude"):
                native_call("read", "GetDefinition", mock.Mock(side_effect=failure))
        self.assertIs(caught.exception, failure)
        self.ole.GetTypeInfo.assert_not_called()
        self.assertEqual(self.stream.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
