import unittest
from unittest.mock import patch

from models.chat_message import ChatMessage


class RoleEngineSpeakerPrefixTests(unittest.TestCase):
    def _engine(self):
        with patch("core.role_engine.get_client", return_value=None):
            from core.role_engine import RoleEngine

            return RoleEngine()

    def test_strips_repeated_customer_name_prefixes(self):
        engine = self._engine()

        self.assertEqual(
            engine._strip_speaker_prefix("小刘：小刘: 小刘：你好呀", "小刘", "客户"),
            "你好呀",
        )

    def test_strips_generic_customer_prefix(self):
        engine = self._engine()

        self.assertEqual(
            engine._strip_speaker_prefix("客户： 我先了解一下", "小刘", "客户"),
            "我先了解一下",
        )

    def test_keeps_name_when_it_is_part_of_message_body(self):
        engine = self._engine()

        self.assertEqual(
            engine._strip_speaker_prefix("你好，可以叫我小刘", "小刘", "客户"),
            "你好，可以叫我小刘",
        )

    def test_script_format_does_not_compound_existing_prefixes(self):
        engine = self._engine()
        conversation = [
            ChatMessage(role="assistant", content="小刘：小刘：我想先了解一下"),
            ChatMessage(role="user", content="销售：好的"),
        ]

        messages = engine._format_as_script(conversation, "小刘", "销售")

        self.assertEqual(messages[0]["content"], "小刘：我想先了解一下")
        self.assertTrue(messages[1]["content"].startswith("销售：好的"))


if __name__ == "__main__":
    unittest.main()
