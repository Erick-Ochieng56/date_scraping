from django.test import TestCase

from leads.models import Lead


class LeadModelTests(TestCase):
    def test_str_prefers_email(self):
        lead = Lead.objects.create(full_name="Jane Doe", email="jane@example.com")
        self.assertIn("jane@example.com", str(lead))
