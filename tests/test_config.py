import json
import os
import tempfile
import unittest

from forgeguard.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_defaults_and_secret_rejection(self):
        config = load_config(None, workspace=".")
        self.assertEqual(config.max_steps, 12)
        self.assertIn("python", config.allowed_commands)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as handle:
            json.dump({"api_key": "must-not-live-here"}, handle)
            path = handle.name
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        with self.assertRaises(ConfigError):
            load_config(path, workspace=".")


if __name__ == "__main__":
    unittest.main()

