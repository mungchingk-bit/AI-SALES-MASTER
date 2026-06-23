import unittest

from ui.training_tab import _has_selected_style


class TrainingStyleSelectionTests(unittest.TestCase):
    def test_empty_and_legacy_default_styles_are_rejected(self):
        self.assertFalse(_has_selected_style(None))
        self.assertFalse(_has_selected_style(""))
        self.assertFalse(_has_selected_style("不指定（默认顾问式）"))

    def test_named_style_is_accepted(self):
        self.assertTrue(_has_selected_style("免免式"))


if __name__ == "__main__":
    unittest.main()
