from django.test import TestCase

from leads.models import Lead, LeadStatus, Prospect, ProspectStatus


class ProspectModelTests(TestCase):
    def test_prospect_str_includes_event_and_company(self):
        prospect = Prospect.objects.create(
            event_name="Tech Conference 2024",
            company="Tech Corp",
            email="contact@techcorp.com"
        )
        self.assertIn("Tech Conference 2024", str(prospect))
        self.assertIn("Tech Corp", str(prospect))
    
    def test_convert_to_lead_creates_lead(self):
        prospect = Prospect.objects.create(
            event_name="Tech Conference 2024",
            company="Tech Corp",
            email="contact@techcorp.com",
            phone_raw="555-1234"
        )
        lead = prospect.convert_to_lead(full_name="John Doe", position="Event Manager")
        
        self.assertEqual(lead.prospect, prospect)
        self.assertEqual(lead.company, "Tech Corp")
        self.assertEqual(lead.email, "contact@techcorp.com")
        self.assertEqual(lead.full_name, "John Doe")
        self.assertEqual(lead.position, "Event Manager")
        self.assertEqual(lead.status, LeadStatus.CONTACTED)
        
        prospect.refresh_from_db()
        self.assertEqual(prospect.status, ProspectStatus.CONVERTED)
        self.assertIsNotNone(prospect.converted_at)
    
    def test_convert_to_lead_prevents_double_conversion(self):
        prospect = Prospect.objects.create(
            event_name="Tech Conference 2024",
            company="Tech Corp"
        )
        prospect.convert_to_lead()
        
        with self.assertRaises(ValueError):
            prospect.convert_to_lead()


class LeadModelTests(TestCase):
    def test_str_prefers_email(self):
        lead = Lead.objects.create(full_name="Jane Doe", email="jane@example.com")
        self.assertIn("jane@example.com", str(lead))
