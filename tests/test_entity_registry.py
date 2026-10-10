"""Scope changes retire handles; same-looking faces are never rebound."""

import io
import json
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.daemon.entities import (
    EntityRegistry,
    EntityNotFound,
    EntityReferenceStale,
    EntityBindingConflict,
)
from swcli.hosts.windows_entity_observation import FaceBinding
from swcli.daemon.documents import DocumentRegistry
from swcli.hosts.native_trace import trace_native_request


class EntityRegistryTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(
            IsSame=mock.Mock(side_effect=lambda a, b: int(a is b))
        )
        self.issued = set()
        self.registry = EntityRegistry(self.app, "d-first", issued_ids=self.issued)
        self.body = object()
        self.faces = [
            FaceBinding(object(), self.body, bytes((index + 1,))) for index in range(3)
        ]

    def register(self, faces=None, **kwargs):
        return self.registry.register_faces(
            self.faces if faces is None else faces,
            configuration=kwargs.get("configuration", "default"),
            update_stamp=kwargs.get("update_stamp", 12),
        )

    def resolve(self, token, **kwargs):
        return self.registry.resolve(
            token,
            configuration=kwargs.get("configuration", "default"),
            update_stamp=kwargs.get("update_stamp", 12),
        )

    def test_short_exact_document_local_ids_and_scope(self):
        tokens = self.register()
        self.assertEqual(len(set(tokens)), 3)
        for token, binding in zip(tokens, self.faces):
            self.assertRegex(token, r"^e-[a-z0-9]{6}$")
            self.assertIs(self.resolve(token).binding, binding)
        other = EntityRegistry(self.app, "d-other", issued_ids=self.issued)
        with self.assertRaises(EntityNotFound):
            other.resolve(tokens[0], configuration="default", update_stamp=12)
        other_tokens = other.register_faces(
            self.faces, configuration="default", update_stamp=12
        )
        self.assertTrue(set(tokens).isdisjoint(other_tokens))

    def test_registry_identity_calls_have_paired_private_trace_boundaries(self):
        stream = io.StringIO()
        with (
            mock.patch.dict("os.environ", {"SWCLI_TRACE_NATIVE_CALLS": "1"}),
            mock.patch("swcli.hosts.native_trace.sys.stderr", stream),
            trace_native_request("req-test", "entity.list"),
        ):
            tokens = self.register()
        calls = [json.loads(line) for line in stream.getvalue().splitlines()]
        identity = [event for event in calls if event["stage"] == "entity-registry"]
        self.assertTrue(identity)
        self.assertEqual(
            [event["phase"] for event in identity],
            [phase for _ in range(len(identity) // 2) for phase in ("begin", "end")],
        )
        self.assertTrue(all(event["call"] == "ISldWorks.IsSame" for event in identity))
        self.assertTrue(all(token not in stream.getvalue() for token in tokens))
        self.assertNotIn("reference", stream.getvalue())

    def test_registry_trace_preserves_first_native_exception_without_payload(self):
        stream = io.StringIO()
        failure = RuntimeError("private identity error")
        self.app.IsSame.side_effect = failure
        with (
            mock.patch.dict("os.environ", {"SWCLI_TRACE_NATIVE_CALLS": "1"}),
            mock.patch("swcli.hosts.native_trace.sys.stderr", stream),
        ):
            with self.assertRaises(RuntimeError) as caught:
                with trace_native_request("req-test", "entity.list"):
                    self.register()
        self.assertIs(caught.exception, failure)
        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(events[-2]["phase"], "error")
        self.assertEqual(events[-2]["stage"], "entity-registry")
        self.assertNotIn("private identity error", stream.getvalue())
        self.assertEqual(self.issued, set())

    def test_failed_lookup_before_first_discovery_does_not_claim_an_empty_complete_set(
        self,
    ):
        with self.assertRaises(EntityNotFound):
            self.resolve("e-111111")
        self.assertEqual(len(self.register()), 3)

    def test_native_wrapper_identity_reuses_handles_even_with_changed_reference_bytes(
        self,
    ):
        tokens = self.register()
        replacements = [
            FaceBinding(object(), self.body, b"fresh" + binding.reference)
            for binding in self.faces
        ]
        mapping = {id(a.face): id(b.face) for a, b in zip(self.faces, replacements)}
        self.app.IsSame.side_effect = lambda a, b: int(
            a is b or mapping.get(id(a)) == id(b)
        )
        self.assertEqual(self.register(replacements), tokens)
        for token, replacement in zip(tokens, replacements):
            self.assertIs(self.resolve(token).binding, replacement)

    def test_equal_bytes_do_not_rebind_different_live_face_in_same_scope(self):
        tokens = self.register()
        replacement = [
            FaceBinding(object(), self.body, face.reference) for face in self.faces
        ]
        before = (self.registry._entries.copy(), self.issued.copy())
        with self.assertRaises(EntityBindingConflict):
            self.register(replacement)
        self.assertEqual((self.registry._entries, self.issued), before)
        self.assertIs(self.resolve(tokens[0]).binding, self.faces[0])

    def test_stamp_or_configuration_change_retires_ids_without_automatic_revival(self):
        for kwargs in ({"update_stamp": 13}, {"configuration": "other"}):
            with self.subTest(kwargs=kwargs):
                registry = EntityRegistry(self.app, "d-first", issued_ids=self.issued)
                old = registry.register_faces(
                    self.faces, configuration="default", update_stamp=12
                )[0]
                with self.assertRaises(EntityReferenceStale):
                    registry.resolve(
                        old,
                        configuration=kwargs.get("configuration", "default"),
                        update_stamp=kwargs.get("update_stamp", 12),
                    )
                with self.assertRaises(EntityReferenceStale):
                    registry.resolve(old, configuration="default", update_stamp=12)
                new = registry.register_faces(
                    self.faces, configuration="default", update_stamp=12
                )
                self.assertNotIn(old, new)

    def test_fresh_discovery_after_stamp_change_allocates_all_new_tokens(self):
        old = self.register()
        new = self.register(update_stamp=13)
        self.assertTrue(set(old).isdisjoint(new))
        with self.assertRaises(EntityReferenceStale):
            self.resolve(old[0], update_stamp=13)

    def test_malformed_scope_or_binding_does_not_modify_registration(self):
        self.register()
        before = (self.registry._entries.copy(), self.issued.copy())
        for kwargs in (
            {"configuration": None},
            {"configuration": ""},
            {"update_stamp": None},
            {"update_stamp": True},
            {"update_stamp": 12.0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(EntityBindingConflict):
                self.register(**kwargs)
        for faces in (
            [],
            None,
            "faces",
            [None],
            self.faces * 22,
            [FaceBinding(None, self.body, b"x")],
            [FaceBinding(object(), None, b"x")],
            [FaceBinding(object(), self.body, b"")],
            [FaceBinding(object(), self.body, bytearray(b"x"))],
        ):
            with (
                self.subTest(faces_type=type(faces).__name__),
                self.assertRaises(EntityBindingConflict),
            ):
                self.registry.register_faces(
                    faces, configuration="default", update_stamp=12
                )
        self.assertEqual((self.registry._entries, self.issued), before)

    def test_bad_native_identity_or_exception_never_publishes_partial_batch(self):
        before = self.issued.copy()
        for status in (None, True, False, "1", 1.0, 2, 3):
            self.app.IsSame.side_effect = None
            self.app.IsSame.return_value = status
            with self.subTest(status=status), self.assertRaises(EntityBindingConflict):
                self.register()
            self.assertEqual(self.registry._entries, {})
            self.assertEqual(self.issued, before)
        failure = RuntimeError("native busy")
        self.app.IsSame.side_effect = failure
        with self.assertRaises(RuntimeError) as caught:
            self.register()
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.issued, before)

    def test_duplicate_native_face_reference_and_mixed_bodies_are_refused(self):
        invalid = (
            [self.faces[0], self.faces[0]],
            [self.faces[0], FaceBinding(object(), self.body, self.faces[0].reference)],
            [self.faces[0], FaceBinding(object(), object(), b"new")],
        )
        for bindings in invalid:
            with (
                self.subTest(bindings=bindings),
                self.assertRaises(EntityBindingConflict),
            ):
                self.register(bindings)
            self.assertEqual(self.registry._entries, {})
            self.assertEqual(self.issued, set())

    def test_same_scope_incomplete_discovery_preserves_full_previous_set(self):
        tokens = self.register()
        before = (self.registry._entries.copy(), self.issued.copy())
        with self.assertRaises(EntityBindingConflict):
            self.register(self.faces[:-1])
        self.assertEqual((self.registry._entries, self.issued), before)
        self.assertIs(self.resolve(tokens[-1]).binding, self.faces[-1])

    def test_native_face_cannot_change_body_ownership_under_same_scope(self):
        self.register()
        before = self.registry._entries.copy()
        with self.assertRaises(EntityBindingConflict):
            self.register(
                [
                    FaceBinding(face.face, object(), face.reference)
                    for face in self.faces
                ]
            )
        self.assertEqual(self.registry._entries, before)

    def test_close_prevents_registration_and_resolution_without_reissuing_ids(self):
        old = self.register()
        self.registry.close()
        with self.assertRaises(EntityNotFound):
            self.register()
        with self.assertRaises(EntityNotFound):
            self.resolve(old[0])
        reopened = EntityRegistry(self.app, "d-reopen", issued_ids=self.issued)
        fresh = reopened.register_faces(
            self.faces, configuration="default", update_stamp=12
        )
        self.assertTrue(set(old).isdisjoint(fresh))
        self.assertTrue(set(old) <= self.issued)

    def test_retired_token_collision_is_skipped_during_fresh_discovery(self):
        old = self.register()[0]
        suffix = next(
            value
            for value in ("111111", "222222", "333333", "444444")
            if "e-" + value not in self.issued
        )
        with mock.patch(
            "swcli.daemon.entities.secrets.choice", side_effect=list(old[2:] + suffix)
        ):
            new = self.register(self.faces[:1], update_stamp=13)
        self.assertEqual(new, ["e-" + suffix])
        self.assertIn(old, self.issued)
        with self.assertRaises(EntityReferenceStale):
            self.resolve(old, update_stamp=13)

    def test_failed_new_scope_read_still_retires_old_scope_handles(self):
        old = self.register()
        self.app.IsSame.side_effect = None
        self.app.IsSame.return_value = 2
        with self.assertRaises(EntityBindingConflict):
            self.register(update_stamp=13)
        self.assertEqual(self.registry._entries, {})
        self.assertEqual(self.issued, set(old))
        with self.assertRaises(EntityReferenceStale):
            self.resolve(old[0], update_stamp=13)
        self.app.IsSame.side_effect = lambda a, b: int(a is b)
        self.assertTrue(set(old).isdisjoint(self.register(update_stamp=13)))


class DocumentEntityLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(
            IsSame=lambda a, b: int(
                getattr(a, "identity", a) is getattr(b, "identity", b)
            )
        )
        self.registry = DocumentRegistry(self.app)
        self.document = self.document_object()
        self.entry = self.registry.register(self.document)
        body = object()
        self.bindings = [
            FaceBinding(object(), body, b"one"),
            FaceBinding(object(), body, b"two"),
        ]

    @staticmethod
    def document_object(identity=None):
        return SimpleNamespace(
            identity=object() if identity is None else identity,
            GetTitle=lambda: "part.SLDPRT",
            GetPathName=lambda: "C:\\part.SLDPRT",
            GetType=lambda: 1,
            GetSaveFlag=lambda: False,
        )

    def register_faces(self, entry):
        return entry.entities.register_faces(
            self.bindings, configuration="default", update_stamp=12
        )

    def test_owner_assigns_document_local_registry_without_native_calls(self):
        self.assertEqual(self.entry.entities.document_id, self.entry.document_id)
        self.assertIs(self.entry.entities.app, self.app)
        self.assertIs(self.entry.entities._issued_ids, self.registry._issued_entity_ids)
        self.assertEqual(self.entry.entities._entries, {})

    def test_forget_closes_even_an_externally_retained_registry(self):
        token = self.register_faces(self.entry)[0]
        retained = self.entry.entities
        self.registry.forget(self.entry.document_id)
        with self.assertRaises(EntityNotFound):
            retained.resolve(token, configuration="default", update_stamp=12)
        with self.assertRaises(EntityNotFound):
            self.register_faces(self.entry)

    def test_live_document_wrapper_reuse_keeps_exact_entity_registry(self):
        tokens = self.register_faces(self.entry)
        retained = self.entry.entities
        wrapped = self.document_object(self.document.identity)
        repeated = self.registry.register(wrapped)
        self.assertIs(repeated, self.entry)
        self.assertIs(repeated.entities, retained)
        self.assertEqual(self.register_faces(repeated), tokens)

    def test_same_path_external_reopen_closes_old_registry_and_never_reuses_tokens(
        self,
    ):
        old = self.register_faces(self.entry)
        reopened = self.registry.register(self.document_object())
        self.assertIsNot(reopened.entities, self.entry.entities)
        with self.assertRaises(EntityNotFound):
            self.entry.entities.resolve(
                old[0], configuration="default", update_stamp=12
            )
        self.assertTrue(set(old).isdisjoint(self.register_faces(reopened)))
        self.assertTrue(set(old) <= self.registry._issued_entity_ids)

    def test_synchronizing_external_close_expires_entity_handles(self):
        old = self.register_faces(self.entry)
        self.app.GetDocuments = lambda: ()
        self.registry.sync()
        with self.assertRaises(EntityNotFound):
            self.entry.entities.resolve(
                old[0], configuration="default", update_stamp=12
            )


if __name__ == "__main__":
    unittest.main()
