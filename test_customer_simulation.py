import unittest
from unittest.mock import patch

from core.difficulty_engine import DifficultyEngine
from prompts.customer_simulation import (
    DIFFICULTY_SETTINGS,
    _pick_diverse_objections,
    build_customer_prompt,
    build_diverse_scenario,
)


class CustomerSimulationDifficultyTests(unittest.TestCase):
    def test_new_user_starts_at_new_easy_baseline(self):
        engine = DifficultyEngine.__new__(DifficultyEngine)
        engine._get_user_avg_score = lambda user, lookback: None

        self.assertEqual(engine.recommend("new-user"), "easy")

    def test_new_easy_uses_previous_hard_baseline(self):
        easy = DIFFICULTY_SETTINGS["easy"]

        self.assertEqual(easy["receptivity_score"], 2)
        self.assertIn("挑剔多疑", easy["customer_personality"])
        self.assertIn("模板化话术", easy["red_line_action"])

    def test_difficulty_increases_objection_dimensions(self):
        with patch("prompts.customer_simulation.random.randint", return_value=1):
            easy, easy_dims = _pick_diverse_objections("easy", [])
            medium, medium_dims = _pick_diverse_objections("medium", [])
            hard, hard_dims = _pick_diverse_objections("hard", [])

        self.assertEqual((len(easy), len(easy_dims)), (4, 4))
        self.assertEqual((len(medium), len(medium_dims)), (5, 5))
        self.assertEqual((len(hard), len(hard_dims)), (6, 6))

    @patch("prompts.customer_simulation._generate_dynamic_details")
    def test_generated_objections_and_random_route_reach_final_prompt(self, generate):
        generate.return_value = {
            "customer_personality": "会核验每一句承诺",
            "primary_objections": "独特顾虑甲；独特顾虑乙",
            "trigger_action": "提供证据",
            "red_line_action": "回避问题",
        }

        scenario = build_diverse_scenario("easy", wedding_type="酒店婚宴")
        prompt = build_customer_prompt(scenario)

        self.assertIn("独特顾虑甲；独特顾虑乙", prompt)
        self.assertIn(scenario["question_style"], prompt)
        self.assertIn(scenario["question_route"], prompt)
        self.assertEqual(len(scenario["question_route"].split(" → ")), 10)


if __name__ == "__main__":
    unittest.main()
