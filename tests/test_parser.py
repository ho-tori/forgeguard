import unittest

from forgeguard.models import Action
from forgeguard.parser import ActionParseError, parse_action


class ParserTests(unittest.TestCase):
    def test_parses_strict_action(self):
        self.assertEqual(
            parse_action('{"action":"read_file","arguments":{"path":"README.md"}}'),
            Action("read_file", {"path": "README.md"}),
        )

    def test_rejects_markdown_and_unknown_top_level_fields(self):
        for raw in (
            '```json\n{"action":"finish","arguments":{"summary":"ok"}}\n```',
            '{"action":"finish","arguments":{"summary":"ok"},"extra":1}',
        ):
            with self.subTest(raw=raw), self.assertRaises(ActionParseError):
                parse_action(raw)

    def test_rejects_unknown_action_and_bad_arguments(self):
        invalid = (
            '{"action":"browse","arguments":{}}',
            '{"action":"read_file","arguments":{}}',
            '{"action":"read_file","arguments":{"path":"x","surprise":true}}',
            '{"action":"run_command","arguments":{"argv":"git status"}}',
        )
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(ActionParseError):
                parse_action(raw)


if __name__ == "__main__":
    unittest.main()

