import os
import tempfile
import unittest

from forgeguard.memory import MemoryStore, SecretDetected


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(os.path.join(self.temp.name, "memory.db"))

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_keyword_search_is_bounded_and_relevant(self):
        self.store.add("s", "convention", "Use snake_case for Python names", ["python", "style"])
        self.store.add("s", "fact", "The web server listens on loopback", ["web", "security"])
        results = self.store.search("fix python naming", limit=1)
        self.assertEqual(len(results), 1)
        self.assertIn("snake_case", results[0].content)

    def test_secret_like_content_is_not_persisted(self):
        with self.assertRaises(SecretDetected):
            self.store.add("s", "fact", "api_key = sk-abcdefghijklmnopqrstuvwxyz", [])
        self.assertEqual(self.store.count(), 0)


if __name__ == "__main__":
    unittest.main()

