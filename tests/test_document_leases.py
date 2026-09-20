import unittest

from swcli.daemon.documents import (
    DocumentLeaseConflict,
    DocumentLeaseNotFound,
    DocumentRegistry,
)


class DocumentLeaseTests(unittest.TestCase):
    def setUp(self):
        class Document:
            GetTitle = lambda self: "part.SLDPRT"
            GetPathName = lambda self: "C:\\part.SLDPRT"
            GetType = lambda self: 1
            GetSaveFlag = lambda self: False

        self.now = 100.0
        self.registry = DocumentRegistry(object(), clock=lambda: self.now)
        self.entry = self.registry.register(Document())

    def test_acquire_is_idempotent_for_the_same_session(self):
        first = self.registry.acquire_lease(
            self.entry, session_id="agent-a", ttl_seconds=30.0
        )
        self.now += 5.0
        second = self.registry.acquire_lease(
            self.entry, session_id="agent-a", ttl_seconds=60.0
        )

        self.assertEqual(second["lease_id"], first["lease_id"])
        self.assertEqual(second["expires_in_seconds"], 60.0)

    def test_acquire_rejects_another_session_until_expiry(self):
        self.registry.acquire_lease(
            self.entry, session_id="agent-a", ttl_seconds=10.0
        )
        with self.assertRaisesRegex(DocumentLeaseConflict, "agent-a"):
            self.registry.acquire_lease(
                self.entry, session_id="agent-b", ttl_seconds=10.0
            )

        self.now += 10.0
        acquired = self.registry.acquire_lease(
            self.entry, session_id="agent-b", ttl_seconds=10.0
        )
        self.assertEqual(acquired["session_id"], "agent-b")

    def test_renew_and_release_require_the_owning_session(self):
        lease = self.registry.acquire_lease(
            self.entry, session_id="agent-a", ttl_seconds=10.0
        )
        with self.assertRaises(DocumentLeaseConflict):
            self.registry.renew_lease(
                lease["lease_id"], session_id="agent-b", ttl_seconds=10.0
            )
        renewed = self.registry.renew_lease(
            lease["lease_id"], session_id="agent-a", ttl_seconds=20.0
        )
        self.assertEqual(renewed["expires_in_seconds"], 20.0)

        released = self.registry.release_lease(
            lease["lease_id"], session_id="agent-a"
        )
        self.assertEqual(released["lease_id"], lease["lease_id"])
        with self.assertRaises(DocumentLeaseNotFound):
            self.registry.release_lease(
                lease["lease_id"], session_id="agent-a"
            )

    def test_expired_lease_is_not_active(self):
        self.registry.acquire_lease(
            self.entry, session_id="agent-a", ttl_seconds=1.0
        )
        self.now += 1.0
        self.assertIsNone(self.registry.active_lease(self.entry))

    def test_lease_ttl_must_be_positive(self):
        for ttl_seconds in (0.0, float("nan"), float("inf")):
            with self.subTest(ttl_seconds=ttl_seconds), self.assertRaisesRegex(
                ValueError, "positive and finite"
            ):
                self.registry.acquire_lease(
                    self.entry,
                    session_id="agent-a",
                    ttl_seconds=ttl_seconds,
                )

    def test_forgetting_document_removes_its_lease(self):
        lease = self.registry.acquire_lease(
            self.entry, session_id="agent-a", ttl_seconds=30.0
        )

        self.registry.forget(self.entry.document_id)

        with self.assertRaises(DocumentLeaseNotFound):
            self.registry.renew_lease(
                lease["lease_id"], session_id="agent-a", ttl_seconds=30.0
            )


if __name__ == "__main__":
    unittest.main()
