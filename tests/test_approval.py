import os
import tempfile
import unittest

from forgeguard.approval import ApprovalStore
from forgeguard.models import Action


class MutableClock(object):
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = MutableClock()
        self.store = ApprovalStore(os.path.join(self.temp.name, "approvals.db"), ttl_seconds=60, clock=self.clock)
        self.action = Action("run_command", {"argv": ["git", "reset", "--hard"]})

    def tearDown(self):
        self.temp.cleanup()

    def test_approval_is_bound_to_exact_action_and_single_use(self):
        request = self.store.request(self.action, "destructive_git")
        self.store.decide(request.id, approved=True)
        swapped = Action("run_command", {"argv": ["git", "push", "--force"]})
        self.assertFalse(self.store.consume(request.id, swapped))
        self.assertTrue(self.store.consume(request.id, self.action))
        self.assertFalse(self.store.consume(request.id, self.action))

    def test_expired_or_rejected_approval_cannot_be_consumed(self):
        expired = self.store.request(self.action, "destructive_git")
        self.store.decide(expired.id, approved=True)
        self.clock.now += 61
        self.assertFalse(self.store.consume(expired.id, self.action))

        rejected = self.store.request(self.action, "destructive_git")
        self.store.decide(rejected.id, approved=False)
        self.assertFalse(self.store.consume(rejected.id, self.action))


if __name__ == "__main__":
    unittest.main()

