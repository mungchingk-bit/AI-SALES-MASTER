import unittest

from prompts.evaluation import build_evaluation_prompt


class EvaluationPromptTests(unittest.TestCase):
    def test_learning_mode_without_style_uses_default_profile(self):
        prompt = build_evaluation_prompt(
            {
                "mode": "salesperson",
                "scenario": {},
                "conversation": [
                    {"role": "user", "content": "我先了解一下"},
                    {"role": "assistant", "content": "您更看重哪一部分？"},
                ],
            },
            style_profile=None,
        )

        self.assertIn("专业顾问", prompt)
        self.assertIn("第1轮-客户：我先了解一下", prompt)
        self.assertIn("第2轮-销售：您更看重哪一部分？", prompt)

    def test_learning_mode_uses_selected_style_name(self):
        prompt = build_evaluation_prompt(
            {"mode": "salesperson", "scenario": {}, "conversation": []},
            style_profile={"name": "顾问式", "description": "先倾听后建议"},
        )

        self.assertIn("顾问式", prompt)
        self.assertIn("先倾听后建议", prompt)


if __name__ == "__main__":
    unittest.main()
