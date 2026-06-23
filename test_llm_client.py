import unittest
import os
from unittest.mock import patch

import requests

from core.llm_client import OpenAICompatibleClient


class CloudTimeoutRecoveryTests(unittest.TestCase):
    @patch("core.llm_client.time.sleep")
    @patch("core.llm_client.requests.post")
    def test_cloud_timeout_is_bounded_and_raised_for_ui_recovery(self, post, sleep):
        post.side_effect = requests.exceptions.Timeout("slow provider")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            client = OpenAICompatibleClient()
            with self.assertRaisesRegex(TimeoutError, "云端模型响应超时"):
                client.chat([], "system", max_tokens=32)

        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args.kwargs["timeout"], (10.0, 60.0))
        sleep.assert_called_once_with(8)


if __name__ == "__main__":
    unittest.main()
