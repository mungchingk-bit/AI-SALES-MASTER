import time
import unittest
from threading import Event
from unittest.mock import patch

from core.evaluation_jobs import is_evaluation_running, schedule_evaluation


class EvaluationJobTests(unittest.TestCase):
    def test_duplicate_session_job_is_not_started(self):
        started = Event()
        release = Event()

        class FakeEvaluator:
            def evaluate(self, *args, **kwargs):
                started.set()
                release.wait(2)

        with patch("core.evaluator.Evaluator", FakeEvaluator):
            self.assertTrue(schedule_evaluation("session-dedup"))
            self.assertTrue(started.wait(1))
            self.assertFalse(schedule_evaluation("session-dedup"))
            release.set()
            for _ in range(100):
                if not is_evaluation_running("session-dedup"):
                    break
                time.sleep(0.01)

        self.assertFalse(is_evaluation_running("session-dedup"))


if __name__ == "__main__":
    unittest.main()
