import io
import json
import unittest

from forgeguard.demo import run_demo


class DemoTests(unittest.TestCase):
    def test_mechanism_demo_is_deterministic(self):
        stream = io.StringIO()
        self.assertTrue(run_demo(stream))
        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual([event["demo"] for event in events], [
            "1_guardrail",
            "2_approval_binding",
            "3_feedback_loop",
            "4_audit",
            "5_policy_check",
        ])
        self.assertEqual(events[0]["state"], "awaiting_approval")
        self.assertTrue(events[1]["swap_blocked"])
        self.assertTrue(events[1]["replay_blocked"])
        self.assertTrue(events[2]["next_turn_saw_failure"])
        self.assertEqual(events[2]["final_content"], "fixed")
        self.assertEqual(events[4]["verdict"], "require_approval")
        self.assertEqual(events[4]["risk"], "arbitrary_code")
        self.assertTrue(events[4]["side_effect_free"])


if __name__ == "__main__":
    unittest.main()

