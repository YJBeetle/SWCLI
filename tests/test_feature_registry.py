"""Exact, document-local feature handles are not names or persistent IDs."""

from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.daemon.documents import (
    DocumentNotFound,
    DocumentLeaseConflict,
    DocumentRegistry,
    FeatureIdConflict,
    FeatureNotFound,
)


class Feature:
    def __init__(self, native_id, *, identity=None):
        self.native_id = native_id
        self.identity = object() if identity is None else identity
        self.Name = "name is not identity"
        self.reads = 0

    def GetID(self):
        self.reads += 1
        return self.native_id


class ComError(Exception):
    def __init__(self, hresult):
        self.hresult = hresult
        super().__init__(hresult)


def document(title):
    return SimpleNamespace(
        GetTitle=lambda: title,
        GetPathName=lambda: "",
        GetType=lambda: 1,
        GetSaveFlag=lambda: False,
        GetUpdateStamp=lambda: 0,
    )


class FeatureRegistryTests(unittest.TestCase):
    def setUp(self):
        self.document, self.other = document("Part1"), document("Part2")
        self.app = SimpleNamespace(
            GetDocuments=lambda: (self.document, self.other),
            IsSame=mock.Mock(side_effect=lambda a, b: int(a.identity is b.identity)),
        )
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.document)
        self.other_entry = self.registry.register(self.other)

    def register(self, feature):
        return self.registry.register_feature(self.entry, feature)

    def state(self):
        return (
            self.entry.features.copy(),
            self.entry.feature_ids_by_native_id.copy(),
            self.registry._issued_feature_ids.copy(),
        )

    def test_new_features_are_indexed_without_all_pairs_com_scans(self):
        features = [Feature(index) for index in range(1000)]
        handles = [self.register(feature) for feature in features]
        self.assertEqual(len(set(handles)), 1000)
        self.app.IsSame.assert_not_called()
        for native_id, (handle, feature) in enumerate(zip(handles, features)):
            self.assertRegex(handle, r"^f-[a-z0-9]{6}$")
            self.assertEqual(feature.reads, 1)
            self.assertEqual(self.entry.feature_ids_by_native_id[native_id], handle)
            self.assertIs(self.registry.resolve_feature(self.entry, handle), feature)

    def test_repeated_wrapper_and_rename_reuse_exact_live_handle(self):
        original = Feature(1)
        handle = self.register(original)
        replacement = Feature(1, identity=original.identity)
        replacement.Name = "renamed"
        self.assertEqual(self.register(replacement), handle)
        self.assertIs(self.registry.resolve_feature(self.entry, handle), replacement)
        self.app.IsSame.assert_called_once_with(original, replacement)

    def test_ids_are_document_local_and_names_never_resolve_targets(self):
        first, second = Feature(1), Feature(2)
        a, b = self.register(first), self.register(second)
        c = self.registry.register_feature(self.other_entry, Feature(1))
        self.assertEqual(len({a, b, c}), 3)
        with self.assertRaises(FeatureNotFound):
            self.registry.resolve_feature(self.other_entry, a)
        with self.assertRaises(FeatureNotFound):
            self.registry.resolve_feature(self.entry, first.Name)
        self.app.IsSame.assert_not_called()

    def test_duplicate_native_id_and_wrapper_identity_do_not_bypass_com(self):
        original = Feature(1)
        self.register(original)
        before = self.state()
        with self.assertRaises(FeatureIdConflict):
            self.register(Feature(1))
        self.app.IsSame.side_effect = None
        self.app.IsSame.return_value = 0
        with self.assertRaises(FeatureIdConflict):
            self.register(original)
        self.assertEqual(self.state(), before)

    def test_invalid_and_failed_native_ids_preserve_all_state(self):
        self.register(Feature(1))
        before = self.state()
        for value in (None, True, 1.5, "1", 2**31, -(2**31) - 1):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.register(Feature(value))
            self.assertEqual(self.state(), before)
        with self.assertRaises(AttributeError):
            self.register(object())
        self.app.IsSame.assert_not_called()

    def test_busy_unknown_and_invalid_identity_results_preserve_live_handles(self):
        original = Feature(1)
        self.register(original)
        before = self.state()
        for status in (0x80010001, 0x80004005):
            self.app.IsSame.side_effect = ComError(status)
            with self.subTest(status=status), self.assertRaises(ComError):
                self.register(Feature(1, identity=original.identity))
            self.assertEqual(self.state(), before)
        self.app.IsSame.side_effect = None
        for value in (2, None, True, "1"):
            self.app.IsSame.return_value = value
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.register(Feature(1, identity=original.identity))
            self.assertEqual(self.state(), before)

    def test_disconnected_proxy_expires_only_that_feature(self):
        first, second = Feature(1), Feature(2)
        old, unaffected = self.register(first), self.register(second)
        self.app.IsSame.side_effect = ComError(-2147417848)
        replacement = Feature(1)
        new = self.register(replacement)
        self.assertNotEqual(new, old)
        self.assertIs(self.entry.features[new], replacement)
        self.assertIs(self.entry.features[unaffected], second)
        with self.assertRaises(FeatureNotFound):
            self.registry.resolve_feature(self.entry, old)

    def test_close_and_reopen_expire_handles_and_never_reissue_retired_tokens(self):
        old = self.register(Feature(1))
        self.registry.forget(self.entry.document_id)
        self.assertEqual(self.entry.features, {})
        self.assertEqual(self.entry.feature_ids_by_native_id, {})
        with self.assertRaises(DocumentNotFound):
            self.register(Feature(2))
        fresh = self.registry.register(self.document)
        suffix = "111111" if old != "f-111111" else "222222"
        with mock.patch(
            "swcli.daemon.documents.secrets.choice",
            side_effect=list(old[2:] + suffix),
        ):
            new = self.registry.register_feature(fresh, Feature(1))
        self.assertEqual(new, "f-" + suffix)
        with self.assertRaises(FeatureNotFound):
            self.registry.resolve_feature(fresh, old)

    def test_feature_handles_do_not_confer_lease_permission(self):
        handle = self.register(Feature(1))
        lease = self.registry.acquire_lease(
            self.entry, session_id="owner", ttl_seconds=60
        )
        self.assertIsNotNone(self.registry.resolve_feature(self.entry, handle))
        with self.assertRaises(DocumentLeaseConflict):
            self.registry.require_lease(
                self.entry, session_id="other", lease_id=lease["lease_id"]
            )


if __name__ == "__main__":
    unittest.main()
