from decimal import Decimal

from django.test import SimpleTestCase

from leads.lead_value import lead_value_from_translation_score


class LeadValueTests(SimpleTestCase):
    def test_tier_mapping(self):
        self.assertEqual(lead_value_from_translation_score(85), Decimal("7500.00"))
        self.assertEqual(lead_value_from_translation_score(65), Decimal("3500.00"))
        self.assertEqual(lead_value_from_translation_score(45), Decimal("1500.00"))
        self.assertIsNone(lead_value_from_translation_score(None))
