from __future__ import annotations

from unittest.mock import Mock, patch

from django.test import TestCase

from crm_integration.mapping import build_perfex_lead_payload
from crm_integration.perfex_client import PerfexClient, PerfexConfig
from crm_integration.tasks import sync_lead_to_perfex
from leads.models import Lead, LeadStatus
from crm_integration.models import PerfexLeadSync, PerfexSyncStatus
from scraper.services.hashing import sha256_of_obj


class PerfexMappingTests(TestCase):
    def test_mapping_includes_defaults_and_raw_extra(self):
        lead = Lead.objects.create(
            full_name="Jane Doe",
            email="jane@example.com",
            phone_raw="(555) 111-2222",
            raw_payload={"perfex": {"custom_field": "x"}},
        )
        payload = build_perfex_lead_payload(lead, defaults={"status": "1"})
        self.assertEqual(payload["name"], "Jane Doe")
        self.assertEqual(payload["email"], "jane@example.com")
        self.assertEqual(payload["status"], "1")
        self.assertEqual(payload["custom_field"], "x")


class PerfexClientTests(TestCase):
    def test_client_calls_expected_url_and_headers(self):
        session = Mock()
        resp = Mock()
        resp.status_code = 200
        resp.json.return_value = {"id": 123}
        session.request.return_value = resp

        client = PerfexClient(PerfexConfig(base_url="https://perfex.local", token="t"), session=session)
        client.create_lead({"name": "X"})

        args, kwargs = session.request.call_args
        self.assertEqual(kwargs["url"], "https://perfex.local/api/leads")
        self.assertIn("Authorization", kwargs["headers"])


class PerfexTaskIdempotencyTests(TestCase):
    def test_sync_task_skips_when_already_synced_same_payload(self):
        lead = Lead.objects.create(full_name="Jane Doe", email="jane@example.com", status=LeadStatus.SYNCED)
        sync = PerfexLeadSync.objects.create(lead=lead, status=PerfexSyncStatus.SYNCED, perfex_lead_id="1")

        payload = build_perfex_lead_payload(lead, defaults={})
        sync.payload_hash = sha256_of_obj(payload)
        sync.save(update_fields=["payload_hash"])

        with patch("crm_integration.tasks._client") as mock_client:
            mock_client.return_value = Mock()
            result = sync_lead_to_perfex.run(lead_id=lead.id, force=False)
            self.assertEqual(result, "skipped")
