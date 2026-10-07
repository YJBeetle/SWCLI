"""Worker-local dimension handles retain exact owner and document boundaries."""

import unittest
from unittest import mock

from swcli.daemon.documents import (
    DimensionNotFound,
    DocumentNotFound,
    DocumentRegistry,
    SketchNotFound,
)


class Document:
    def __init__(self, title, path=""):
        self.title, self.path = title, path

    def GetTitle(self):
        return self.title

    def GetPathName(self):
        return self.path

    def GetType(self):
        return 1

    def GetSaveFlag(self):
        return False


class DimensionRegistryTests(unittest.TestCase):
    def setUp(self):
        self.document = Document("Part1")
        self.other = Document("Part2")
        self.app = mock.Mock()
        self.app.GetDocuments = lambda: (self.document, self.other)
        self.registry = DocumentRegistry(self.app)
        self.entry = self.registry.register(self.document)
        self.other_entry = self.registry.register(self.other)
        self.sketch = object()
        self.sketch_id = self.registry.register_sketch(self.entry, self.sketch)
        self.dimension = object()
        self.dimension_id = self.registry.register_dimension(
            self.entry, self.sketch_id, self.dimension
        )

    def test_short_id_preserves_exact_native_dimension_and_sketch(self):
        self.assertRegex(self.dimension_id, r"^m-[0-9a-hjkmnp-tv-z]{6}$")
        item = self.registry.resolve_dimension(self.entry, self.dimension_id)
        self.assertIs(item.dimension, self.dimension)
        self.assertEqual(item.sketch_id, self.sketch_id)
        self.assertIs(
            self.registry.resolve_sketch(self.entry, item.sketch_id), self.sketch
        )

    def test_handle_never_resolves_in_another_document(self):
        with self.assertRaises(DimensionNotFound):
            self.registry.resolve_dimension(self.other_entry, self.dimension_id)
        with self.assertRaises(SketchNotFound):
            self.registry.register_dimension(self.other_entry, self.sketch_id, object())

    def test_absent_native_handle_and_unknown_sketch_are_rejected(self):
        with self.assertRaises(ValueError):
            self.registry.register_dimension(self.entry, self.sketch_id, None)
        with self.assertRaises(SketchNotFound):
            self.registry.register_dimension(self.entry, "s-000000", object())

    def test_close_reopen_invalidates_old_handles(self):
        self.registry.forget(self.entry.document_id)
        self.assertFalse(self.entry.dimensions or self.entry.sketches)
        with self.assertRaises(DimensionNotFound):
            self.registry.resolve_dimension(self.entry, self.dimension_id)
        with self.assertRaises(DocumentNotFound):
            self.registry.register_sketch(self.entry, object())
        replacement = self.registry.register(self.document)
        self.assertNotEqual(replacement.document_id, self.entry.document_id)
        with self.assertRaises(DimensionNotFound):
            self.registry.resolve_dimension(replacement, self.dimension_id)

    def test_save_as_keeps_live_handle_owner_session_and_lease(self):
        self.registry.set_current(self.entry, session_id="writer")
        lease = self.registry.acquire_lease(
            self.entry, session_id="writer", ttl_seconds=60
        )
        self.document.title = "Saved.SLDPRT"
        self.document.path = r"C:\Workspace\Saved.SLDPRT"
        self.registry.refresh_key(self.entry)
        self.registry.sync()
        self.assertIs(self.registry.resolve(None, session_id="writer"), self.entry)
        self.assertIs(
            self.registry.resolve_dimension(self.entry, self.dimension_id).dimension,
            self.dimension,
        )
        self.assertEqual(
            self.registry.active_lease(self.entry)["lease_id"], lease["lease_id"]
        )

    def test_external_close_and_worker_replacement_drop_dimension_handles(self):
        self.app.GetDocuments = lambda: (self.other,)
        self.registry.sync()
        with self.assertRaises(DimensionNotFound):
            self.registry.resolve_dimension(self.entry, self.dimension_id)
        replacement = DocumentRegistry(self.app)
        new_entry = replacement.register(self.document)
        with self.assertRaises(DimensionNotFound):
            replacement.resolve_dimension(new_entry, self.dimension_id)

    def test_external_reopen_with_same_path_expires_handles_and_lease(self):
        self.document.path = r"C:\Workspace\Same.SLDPRT"
        self.registry.refresh_key(self.entry)
        self.registry.set_current(self.entry, session_id="writer")
        self.registry.acquire_lease(self.entry, session_id="writer", ttl_seconds=60)
        reopened = Document("Same.SLDPRT", self.document.path)
        self.app.IsSame = lambda first, second: 1 if first is second else 0
        self.app.GetDocuments = lambda: (reopened, self.other)
        self.registry.sync()
        replacement = self.registry.register(reopened)
        self.assertNotEqual(replacement.document_id, self.entry.document_id)
        self.assertFalse(self.entry.dimensions or self.entry.sketches)
        self.assertIsNone(self.registry.active_lease(replacement))
        with self.assertRaises(DimensionNotFound):
            self.registry.resolve_dimension(replacement, self.dimension_id)

    def test_another_com_wrapper_for_same_native_document_keeps_handles(self):
        wrapper = Document(self.document.title)
        self.app.IsSame = lambda first, second: 1
        registered = self.registry.register(wrapper)
        self.assertIs(registered, self.entry)
        self.assertIs(registered.document, wrapper)
        self.assertIs(
            self.registry.resolve_dimension(registered, self.dimension_id).dimension,
            self.dimension,
        )

    def test_known_disconnected_proxy_expires_but_busy_and_unknown_preserve_state(self):
        class ComError(Exception):
            def __init__(self, hresult):
                self.hresult = hresult
                super().__init__(hresult)

        for hresult, disconnected in ((-2147417848, True), (0x800401FD, True),
                                      (0x80010001, False), (0x80004005, False)):
            with self.subTest(hresult=hresult):
                self.setUp()
                wrapper = Document(self.document.title)
                self.app.IsSame = mock.Mock(side_effect=ComError(hresult))
                if disconnected:
                    replacement = self.registry.register(wrapper)
                    self.assertNotEqual(replacement.document_id, self.entry.document_id)
                    self.assertFalse(self.entry.dimensions)
                else:
                    with self.assertRaises(ComError):
                        self.registry.register(wrapper)
                    self.assertIs(self.registry.resolve_dimension(
                        self.entry, self.dimension_id).dimension, self.dimension)


if __name__ == "__main__":
    unittest.main()
