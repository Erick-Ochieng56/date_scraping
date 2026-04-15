from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from crawler.models import CrawlRun, CrawlRunStatus, CrawlRunTrigger, CrawlSource, DiscoveredDomain
from leads.models import Lead, LeadStatus, Prospect, ProspectStatus
from scraper.models import ScrapeRun, ScrapeRunStatus, ScrapeTarget

from .permissions import scraper_group_name


class DashboardV1ApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="staff1", password="pass12345")
        group, _ = Group.objects.get_or_create(name=scraper_group_name())
        self.user.groups.add(group)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_targets_list_requires_portal_access(self):
        ScrapeTarget.objects.create(name="T1", start_url="https://example.com", owner=self.user)
        resp = self.client.get("/dashboard/api/v1/targets/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["data"]["total"], 1)

    def test_target_create_and_patch(self):
        payload = {
            "name": "Portal target",
            "enabled": True,
            "target_type": "html",
            "start_url": "https://example.org/list",
            "run_every_minutes": 30,
            "config": {"item_selector": "li.row", "fields": {"title": "a"}},
        }
        resp = self.client.post("/dashboard/api/v1/targets/", payload, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data["success"])
        tid = resp.data["data"]["id"]
        self.assertEqual(resp.data["data"]["name"], "Portal target")
        self.assertEqual(resp.data["data"]["config"]["item_selector"], "li.row")

        patch = self.client.patch(
            f"/dashboard/api/v1/targets/{tid}/",
            {"enabled": False, "run_every_minutes": 120},
            format="json",
        )
        self.assertEqual(patch.status_code, 200)
        self.assertFalse(patch.data["data"]["enabled"])
        self.assertEqual(patch.data["data"]["run_every_minutes"], 120)

    def test_prospect_convert_flow_creates_lead(self):
        prospect = Prospect.objects.create(
            company="Acme",
            email="a@example.com",
            status=ProspectStatus.NEW,
        )
        resp = self.client.post(
            "/dashboard/api/v1/prospects/bulk/convert/",
            {"prospect_ids": [prospect.id]},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        prospect.refresh_from_db()
        self.assertEqual(prospect.status, ProspectStatus.CONVERTED)
        self.assertTrue(Lead.objects.filter(prospect=prospect).exists())

    def test_lead_bulk_interested_transition(self):
        lead = Lead.objects.create(company="B", status=LeadStatus.CONTACTED)
        resp = self.client.post(
            "/dashboard/api/v1/leads/bulk/interested/",
            {"lead_ids": [lead.id]},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        lead.refresh_from_db()
        self.assertEqual(lead.status, LeadStatus.INTERESTED)


class DashboardAdminApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username="admin1", password="pass12345", is_staff=True, is_superuser=True)
        self.staff_from = User.objects.create_user(username="staff_from", password="pass12345")
        self.staff_to = User.objects.create_user(username="staff_to", password="pass12345")
        group, _ = Group.objects.get_or_create(name=scraper_group_name())
        self.staff_from.groups.add(group)
        self.staff_to.groups.add(group)
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_admin_create_staff_user(self):
        resp = self.client.post(
            "/dashboard/api/admin/v1/users/create-staff/",
            {"username": "newstaff", "password": "pass12345", "email": "n@example.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["data"]["role"], "staff")

    def test_admin_ownership_transfer_scrape_targets(self):
        t1 = ScrapeTarget.objects.create(name="T-from", start_url="https://example.com", owner=self.staff_from)
        resp = self.client.post(
            "/dashboard/api/admin/v1/ownership/transfer/",
            {
                "object_type": "scrape_targets",
                "from_user_id": self.staff_from.id,
                "to_user_id": self.staff_to.id,
                "transfer_all": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        t1.refresh_from_db()
        self.assertEqual(t1.owner_id, self.staff_to.id)

    def test_admin_scraper_endpoints_list_and_retry(self):
        target = ScrapeTarget.objects.create(name="T-admin", start_url="https://example.com", owner=self.staff_from)
        run = ScrapeRun.objects.create(
            owner=self.staff_from,
            target=target,
            status=ScrapeRunStatus.FAILED,
            trigger="manual",
        )
        list_resp = self.client.get("/dashboard/api/admin/v1/scraper/runs/?status=failed")
        self.assertEqual(list_resp.status_code, 200)
        self.assertGreaterEqual(list_resp.data["data"]["total"], 1)
        retry_resp = self.client.post(f"/dashboard/api/admin/v1/scraper/runs/{run.id}/retry/")
        self.assertEqual(retry_resp.status_code, 200)

    def test_admin_crawler_endpoints_list_and_controls(self):
        source = CrawlSource.objects.create(
            name="S1",
            discovery_query="translation agencies",
            source_type="search",
            enabled=True,
            owner=self.staff_from,
        )
        domain = DiscoveredDomain.objects.create(
            domain="https://example.org",
            source=source,
            crawl_status="failed",
            owner=self.staff_from,
            error_text="network",
        )
        run = CrawlRun.objects.create(
            trigger=CrawlRunTrigger.MANUAL,
            status=CrawlRunStatus.RUNNING,
            owner=self.staff_from,
            task_id="abc123",
        )

        sources_resp = self.client.get("/dashboard/api/admin/v1/crawler/sources/")
        self.assertEqual(sources_resp.status_code, 200)
        self.assertGreaterEqual(sources_resp.data["data"]["total"], 1)

        patch_resp = self.client.patch(
            f"/dashboard/api/admin/v1/crawler/sources/{source.id}/",
            {"enabled": False},
            format="json",
        )
        self.assertEqual(patch_resp.status_code, 200)
        source.refresh_from_db()
        self.assertFalse(source.enabled)

        reset_resp = self.client.post("/dashboard/api/admin/v1/crawler/domains/reset-failed/", {}, format="json")
        self.assertEqual(reset_resp.status_code, 200)
        domain.refresh_from_db()
        self.assertEqual(domain.crawl_status, "pending")
        self.assertEqual(domain.error_text, "")

        cancel_resp = self.client.post(f"/dashboard/api/admin/v1/crawler/runs/{run.id}/cancel/")
        self.assertEqual(cancel_resp.status_code, 200)
        run.refresh_from_db()
        self.assertEqual(run.status, CrawlRunStatus.FAILED)
