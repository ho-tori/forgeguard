import io
import json
import os
import sys
import tempfile
import unittest

from forgeguard.demo import _reply, run_demo
from forgeguard.policy import PolicyEngine
from forgeguard.policy_check import check_policy


class DemoTests(unittest.TestCase):
    def test_policy_check_demo_leaves_absolute_marker_uncreated(self):
        with tempfile.TemporaryDirectory() as workspace:
            marker_path = os.path.join(workspace, "policy-check-marker.txt")
            policy = PolicyEngine(
                workspace,
                [sys.executable, os.path.basename(sys.executable)],
            )
            checked = check_policy(
                _reply(
                    "run_command",
                    argv=[
                        sys.executable,
                        "-c",
                        "open(%r, 'w').write('executed')" % marker_path,
                    ],
                ),
                policy,
            )

            self.assertEqual(checked["verdict"], "require_approval")
            self.assertEqual(checked["risk"], "arbitrary_code")
            self.assertFalse(os.path.exists(marker_path))

            stream = io.StringIO()
            self.assertTrue(
                run_demo(stream, workspace=workspace, marker_path=marker_path)
            )
            events = [json.loads(line) for line in stream.getvalue().splitlines()]
            self.assertTrue(events[4]["side_effect_free"])
            self.assertFalse(os.path.exists(marker_path))

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

