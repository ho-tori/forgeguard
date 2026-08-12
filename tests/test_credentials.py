import os
import tempfile
import unittest

from forgeguard.credentials import CredentialManager, InMemoryCredentialBackend, SecretFileBackend


class CredentialTests(unittest.TestCase):
    def test_set_status_get_clear_without_disclosure(self):
        backend = InMemoryCredentialBackend()
        manager = CredentialManager(backend=backend, environ={})
        manager.set("sk-test-super-secret")
        status = manager.status()
        self.assertEqual(status, {"configured": True, "source": "secure_store"})
        self.assertNotIn("sk-test", repr(status))
        self.assertEqual(manager.get(), "sk-test-super-secret")
        manager.clear()
        self.assertEqual(manager.status(), {"configured": False, "source": None})

    def test_missing_optional_secret_file_reports_not_configured(self):
        manager = CredentialManager(
            backend=InMemoryCredentialBackend(),
            environ={"FORGEGUARD_API_KEY_FILE": os.path.join(tempfile.gettempdir(), "forgeguard-definitely-missing-key")},
        )
        self.assertEqual(manager.status(), {"configured": False, "source": None})
        self.assertIsNone(manager.get())

    @unittest.skipIf(os.name == "nt", "POSIX permission bits do not protect Windows files")
    def test_secret_file_rejects_permissive_mode(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as handle:
            handle.write("secret")
            path = handle.name
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        os.chmod(path, 0o644)
        manager = CredentialManager(backend=InMemoryCredentialBackend(), environ={"FORGEGUARD_API_KEY_FILE": path})
        with self.assertRaises(PermissionError):
            manager.get()
        os.chmod(path, 0o600)
        self.assertEqual(SecretFileBackend(path).get(), "secret")


if __name__ == "__main__":
    unittest.main()
