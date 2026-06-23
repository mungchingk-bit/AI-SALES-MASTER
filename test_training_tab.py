import unittest
from types import SimpleNamespace

from ui.training_tab import _has_selected_style, _resolve_training_style


class TrainingStyleSelectionTests(unittest.TestCase):
    def test_empty_and_legacy_default_styles_are_rejected(self):
        self.assertFalse(_has_selected_style(None))
        self.assertFalse(_has_selected_style(""))
        self.assertFalse(_has_selected_style("不指定（默认顾问式）"))

    def test_named_style_is_accepted(self):
        self.assertTrue(_has_selected_style("免免式"))

    def test_sales_login_defaults_to_own_style(self):
        profiles = [
            SimpleNamespace(id="a", name="免免式"),
            SimpleNamespace(id="b", name="茉莉式"),
        ]

        selected = _resolve_training_style(None, "茉莉", "sales", profiles)

        self.assertEqual(selected.id, "b")

    def test_explicit_style_overrides_sales_default(self):
        profiles = [
            SimpleNamespace(id="a", name="免免式"),
            SimpleNamespace(id="b", name="茉莉式"),
        ]

        selected = _resolve_training_style("免免式", "茉莉", "sales", profiles)

        self.assertEqual(selected.id, "a")

    def test_admin_without_selection_has_no_default(self):
        profiles = [SimpleNamespace(id="a", name="免免式")]

        self.assertIsNone(_resolve_training_style(None, "免免", "admin", profiles))


if __name__ == "__main__":
    unittest.main()
