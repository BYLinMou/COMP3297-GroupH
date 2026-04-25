from django.test import TestCase

from defects.effectiveness import classify_developer


class DeveloperEffectivenessClassificationTests(TestCase):
    def test_fixed_less_than_20_returns_insufficient_data(self):
        self.assertEqual(classify_developer(19, 0), "Insufficient data")

    def test_ratio_below_1_over_32_returns_good(self):
        self.assertEqual(classify_developer(32, 0), "Good")

    def test_ratio_between_1_over_32_and_1_over_8_returns_fair(self):
        self.assertEqual(classify_developer(32, 1), "Fair")

    def test_ratio_greater_or_equal_1_over_8_returns_poor(self):
        self.assertEqual(classify_developer(24, 3), "Poor")

    def test_negative_input_raises_value_error(self):
        with self.assertRaisesMessage(ValueError, "cannot be negative"):
            classify_developer(-1, 0)
