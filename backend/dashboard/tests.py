from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from io import StringIO

from crawler.models import AISearchJob, CrawlRun, CrawlRunStatus, CrawlRunTrigger, CrawlSource, DiscoveredDomain
from dashboard.models import ActivityLog
from dashboard.utils import log_activity
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
        # force_login (real session, via AuthenticationMiddleware) rather than
        # force_authenticate: some endpoints in this class (wizard_views.py) are
        # plain Django views, not DRF api_view-wrapped, and force_authenticate
        # only patches DRF's request wrapper — it has no effect on those, so
        # they'd see AnonymousUser and 401 instead of the real 403/200 checks.
        self.client.force_login(self.user)

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

    @override_settings(GEMINI_API_KEY="fake-key-for-test", AI_SEARCH_REQUIRE_GEMINI=True)
    def test_ai_search_job_create_rejects_when_one_already_in_progress(self):
        """
        Regression: no cap on concurrent AI search jobs per user beyond a
        generic 120/min request throttle, despite a single job triggering 40+
        real Gemini/Serper API calls. A second job while one is still
        pending/generating/searching must be rejected (429), not queued.
        """
        AISearchJob.objects.create(owner=self.user, seed_topic="Existing job", status="generating")

        resp = self.client.post(
            "/dashboard/api/v1/ai-search/jobs/",
            {"seed_topic": "Another topic"},
            format="json",
        )
        self.assertEqual(resp.status_code, 429)
        self.assertFalse(resp.data["success"])
        self.assertEqual(AISearchJob.objects.filter(owner=self.user).count(), 1)

    @override_settings(
        GEMINI_API_KEY="fake-key-for-test",
        AI_SEARCH_REQUIRE_GEMINI=True,
        AI_SEARCH_MAX_JOBS_PER_DAY_PER_USER=2,
    )
    def test_ai_search_job_create_rejects_past_daily_limit(self):
        for i in range(2):
            AISearchJob.objects.create(owner=self.user, seed_topic=f"Job {i}", status="done")

        resp = self.client.post(
            "/dashboard/api/v1/ai-search/jobs/",
            {"seed_topic": "One too many"},
            format="json",
        )
        self.assertEqual(resp.status_code, 429)
        self.assertFalse(resp.data["success"])
        self.assertEqual(AISearchJob.objects.filter(owner=self.user).count(), 2)

    def test_target_create_rejects_internal_url(self):
        """SSRF guard: a portal user (not just admins) must not be able to point a
        scrape target at an internal/private address via the API."""
        for start_url in [
            "http://127.0.0.1/admin",
            "http://169.254.169.254/latest/meta-data/",
            "http://192.168.1.1/",
        ]:
            with self.subTest(start_url=start_url):
                payload = {
                    "name": f"Bad target {start_url}",
                    "enabled": True,
                    "target_type": "html",
                    "start_url": start_url,
                    "run_every_minutes": 30,
                    "config": {"item_selector": "li.row", "fields": {"title": "a"}},
                }
                resp = self.client.post("/dashboard/api/v1/targets/", payload, format="json")
                self.assertEqual(resp.status_code, 400)
                self.assertFalse(ScrapeTarget.objects.filter(start_url=start_url).exists())

    def test_prospect_convert_flow_creates_lead(self):
        prospect = Prospect.objects.create(
            company="Acme",
            email="a@example.com",
            status=ProspectStatus.NEW,
            owner=self.user,
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
        lead = Lead.objects.create(company="B", status=LeadStatus.CONTACTED, owner=self.user)
        resp = self.client.post(
            "/dashboard/api/v1/leads/bulk/interested/",
            {"lead_ids": [lead.id]},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        lead.refresh_from_db()
        self.assertEqual(lead.status, LeadStatus.INTERESTED)

    def test_targets_list_rejects_invalid_page(self):
        resp = self.client.get("/dashboard/api/v1/targets/?page=abc")
        self.assertEqual(resp.status_code, 400)

    def test_wizard_detect_platform_rejects_portal_user(self):
        resp = self.client.get(
            "/dashboard/wizard/detect-platform/",
            {"url": "https://www.eventbrite.com/d/united-kingdom--london/events"},
        )
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertFalse(data["success"])

    def test_wizard_create_target_rejects_portal_user(self):
        resp = self.client.post(
            "/dashboard/wizard/create-target/",
            {
                "url": "https://example.com/events",
                "name": "Wizard Portal Target",
                "run_every_minutes": 90,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertFalse(data["success"])

    def test_wizard_create_target_name_conflict(self):
        # The wizard is admin-only (staff_json_api_user checks is_staff, not the
        # scraper group) — unlike self.user, which is a portal user by design
        # (see test_wizard_create_target_rejects_portal_user above).
        admin = get_user_model().objects.create_user(username="admin1", password="pass12345", is_staff=True)
        self.client.force_login(admin)
        ScrapeTarget.objects.create(name="Taken", start_url="https://example.com/a", owner=self.user)
        resp = self.client.post(
            "/dashboard/wizard/create-target/",
            {"url": "https://example.com/b", "name": "Taken"},
            format="json",
        )
        self.assertEqual(resp.status_code, 409)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertTrue(data["existing"])

    def test_prospect_detail_includes_raw_payload_but_list_does_not(self):
        Prospect.objects.create(
            company="Evidence Co",
            status="new",
            owner=self.user,
            source_name="ai_search",
            raw_payload={"translation_need_score": 82, "evidence_snippet": "Tender notice for interpretation."},
        )
        prospect = Prospect.objects.get(company="Evidence Co")

        list_resp = self.client.get("/dashboard/api/v1/prospects/")
        self.assertEqual(list_resp.status_code, 200)
        self.assertNotIn("raw_payload", list_resp.json()["data"]["items"][0])

        detail_resp = self.client.get(f"/dashboard/api/v1/prospects/{prospect.id}/")
        self.assertEqual(detail_resp.status_code, 200)
        detail_data = detail_resp.json()["data"]
        self.assertIn("raw_payload", detail_data)
        self.assertEqual(detail_data["raw_payload"]["translation_need_score"], 82)

    def test_prospects_list_filters_by_source_and_reports_counts(self):
        Prospect.objects.create(company="AI hit", source_name="ai_search", status="new", owner=self.user)
        Prospect.objects.create(company="Crawler hit", source_name="web_crawler", status="new", owner=self.user)
        Prospect.objects.create(company="Site check 1", source_name="Eventbrite Nairobi", status="new", owner=self.user)
        Prospect.objects.create(company="Site check 2", source_name="Meetup Kampala", status="new", owner=self.user)

        all_resp = self.client.get("/dashboard/api/v1/prospects/")
        self.assertEqual(all_resp.status_code, 200)
        all_data = all_resp.json()["data"]
        self.assertEqual(all_data["total"], 4)
        self.assertEqual(all_data["source_counts"], {"ai_search": 1, "web_crawler": 1, "site_check": 2})

        site_resp = self.client.get("/dashboard/api/v1/prospects/?source=site_check")
        self.assertEqual(site_resp.status_code, 200)
        site_data = site_resp.json()["data"]
        self.assertEqual(site_data["total"], 2)
        self.assertEqual({item["company"] for item in site_data["items"]}, {"Site check 1", "Site check 2"})
        # Counts stay keyed to the status/search filters, not the source pill itself.
        self.assertEqual(site_data["source_counts"], {"ai_search": 1, "web_crawler": 1, "site_check": 2})

        invalid_resp = self.client.get("/dashboard/api/v1/prospects/?source=not-a-real-source")
        self.assertEqual(invalid_resp.status_code, 200)
        self.assertEqual(invalid_resp.json()["data"]["total"], 4)

    def test_metrics_summary_reports_recent_contacted_count(self):
        now = timezone.now()
        Prospect.objects.create(
            company="Contacted recently", status="contacted", owner=self.user,
            contacted_at=now - timedelta(days=1),
        )
        Prospect.objects.create(
            company="Contacted long ago", status="contacted", owner=self.user,
            contacted_at=now - timedelta(days=30),
        )
        Prospect.objects.create(company="Never contacted", status="new", owner=self.user)

        resp = self.client.get("/dashboard/api/v1/metrics/summary/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["prospects_contacted_recent"], 1)
        self.assertEqual(data["prospects_contacted"], 2)

    def test_metrics_timeseries_buckets_by_day_and_classifies_source(self):
        now = timezone.now()
        Prospect.objects.create(
            company="AI hit", source_name="ai_search", status="new", owner=self.user,
            created_at=now - timedelta(hours=2),
        )
        Prospect.objects.create(
            company="Crawler hit", source_name="web_crawler", status="new", owner=self.user,
            created_at=now - timedelta(hours=3),
        )
        Prospect.objects.create(
            company="Site check hit", source_name="Eventbrite Nairobi", status="new", owner=self.user,
            created_at=now - timedelta(days=1, hours=1),
        )
        Lead.objects.create(company="Tracked lead", status="contacted", owner=self.user, created_at=now - timedelta(hours=1))

        resp = self.client.get("/dashboard/api/v1/metrics/timeseries/?granularity=day&periods=3")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["granularity"], "day")
        self.assertEqual(len(data["buckets"]), 3)

        today_bucket = data["buckets"][-1]
        yesterday_bucket = data["buckets"][-2]
        self.assertEqual(today_bucket["prospects_by_source"], {"ai_search": 1, "web_crawler": 1, "site_check": 0})
        self.assertEqual(today_bucket["prospects_total"], 2)
        self.assertEqual(today_bucket["leads_created"], 1)
        self.assertEqual(yesterday_bucket["prospects_by_source"], {"ai_search": 0, "web_crawler": 0, "site_check": 1})

    def test_metrics_timeseries_only_counts_own_records(self):
        other = get_user_model().objects.create_user(username="staff2", password="pass12345")
        Prospect.objects.create(company="Not mine", source_name="ai_search", status="new", owner=other)
        Prospect.objects.create(company="Mine", source_name="ai_search", status="new", owner=self.user)

        resp = self.client.get("/dashboard/api/v1/metrics/timeseries/?granularity=day&periods=1")
        self.assertEqual(resp.status_code, 200)
        bucket = resp.json()["data"]["buckets"][0]
        self.assertEqual(bucket["prospects_by_source"]["ai_search"], 1)

    def test_metrics_timeseries_rejects_invalid_granularity(self):
        resp = self.client.get("/dashboard/api/v1/metrics/timeseries/?granularity=year")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("granularity", resp.json())

    def test_metrics_timeseries_clamps_periods_to_max(self):
        resp = self.client.get("/dashboard/api/v1/metrics/timeseries/?granularity=day&periods=999")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["periods"], 90)
        self.assertEqual(len(data["buckets"]), 90)

    def test_metrics_timeseries_week_and_month_granularity(self):
        resp = self.client.get("/dashboard/api/v1/metrics/timeseries/?granularity=week&periods=4")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["data"]["buckets"]), 4)

        resp2 = self.client.get("/dashboard/api/v1/metrics/timeseries/?granularity=month&periods=6")
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(len(resp2.json()["data"]["buckets"]), 6)


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

    @override_settings(GEMINI_API_KEY="", AI_SEARCH_REQUIRE_GEMINI=True)
    @patch("dashboard.api.views._get_serper_api_key", return_value="fake-serper-key")
    def test_admin_ai_search_job_create_rejects_when_gemini_missing_but_serper_present(self, _mock_serper):
        """
        Regression: the admin job-creation check used to accept either
        SERPER_API_KEY or GEMINI_API_KEY being present, ignoring
        AI_SEARCH_REQUIRE_GEMINI — so an admin could get a 201 here and then
        watch run_ai_search_job (which does honor that setting) fail instantly
        with no way to have known upfront. Must now match the non-admin check.
        """
        resp = self.client.post(
            "/dashboard/api/admin/v1/ai-search/jobs/",
            {"seed_topic": "East Africa medical conference interpretation"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data["success"])

    @override_settings(GEMINI_API_KEY="fake-key-for-test", AI_SEARCH_REQUIRE_GEMINI=True)
    def test_admin_ai_search_job_create_rejects_when_delegated_owner_has_job_in_progress(self):
        """The rate limit applies to the delegated owner_id, not the admin
        submitting the request on that user's behalf."""
        AISearchJob.objects.create(
            owner=self.staff_from, seed_topic="Existing job", status="searching"
        )

        resp = self.client.post(
            "/dashboard/api/admin/v1/ai-search/jobs/",
            {"seed_topic": "Another topic", "owner_id": self.staff_from.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 429)
        self.assertFalse(resp.data["success"])
        self.assertEqual(AISearchJob.objects.filter(owner=self.staff_from).count(), 1)

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

    def test_admin_users_update_does_not_nameerror(self):
        staff = get_user_model().objects.create_user(username="staff_patch", password="pass12345")
        group, _ = Group.objects.get_or_create(name=scraper_group_name())
        staff.groups.add(group)
        resp = self.client.patch(
            f"/dashboard/api/admin/v1/users/{staff.id}/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        staff.refresh_from_db()
        self.assertFalse(staff.is_active)

    def test_admin_activity_list(self):
        log_activity(
            action="user_created",
            object_type="user",
            object_id=self.admin.id,
            description="Test audit entry",
            user=self.admin,
        )
        resp = self.client.get("/dashboard/api/admin/v1/activity/?page_size=10")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        self.assertGreaterEqual(resp.data["data"]["total"], 1)
        self.assertIn("filters", resp.data)

    def test_admin_settings_status(self):
        resp = self.client.get("/dashboard/api/admin/v1/settings/status/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        ids = {row["id"] for row in resp.data["data"]["integrations"]}
        self.assertEqual(ids, {"gemini", "gsheets", "perfex"})

    def test_admin_users_update_accepts_string_false(self):
        staff = get_user_model().objects.create_user(username="staff_bool", password="pass12345")
        group, _ = Group.objects.get_or_create(name=scraper_group_name())
        staff.groups.add(group)
        resp = self.client.patch(
            f"/dashboard/api/admin/v1/users/{staff.id}/",
            {"is_active": "false"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        staff.refresh_from_db()
        self.assertFalse(staff.is_active)

    def test_admin_users_update_rejects_invalid_boolean(self):
        staff = get_user_model().objects.create_user(username="staff_invalid_bool", password="pass12345")
        group, _ = Group.objects.get_or_create(name=scraper_group_name())
        staff.groups.add(group)
        resp = self.client.patch(
            f"/dashboard/api/admin/v1/users/{staff.id}/",
            {"is_active": "sometimes"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_admin_activity_list_rejects_invalid_page(self):
        resp = self.client.get("/dashboard/api/admin/v1/activity/?page=abc")
        self.assertEqual(resp.status_code, 400)

    def test_wizard_endpoints_allow_admin(self):
        detect = self.client.get(
            "/dashboard/wizard/detect-platform/",
            {"url": "https://www.eventbrite.com/d/united-kingdom--london/events"},
        )
        self.assertEqual(detect.status_code, 200)
        detect_data = detect.json()
        self.assertTrue(detect_data["success"])
        self.assertEqual(detect_data["platform"], "eventbrite")

        create = self.client.post(
            "/dashboard/wizard/create-target/",
            {
                "url": "https://example.com/events",
                "name": "Wizard Admin Target",
                "run_every_minutes": 90,
            },
            format="json",
        )
        self.assertEqual(create.status_code, 201)
        create_data = create.json()
        self.assertTrue(create_data["success"])


class CrawlerDiscoverEndpointTests(TestCase):
    """
    Regression tests for PUNCH_LIST #12: the frontend's entire Discover workflow
    (CrawlerDiscoverPage — Preview URLs, Add to queue, Queue & crawl now) shipped
    wired to /dashboard/api/v1/crawler/preview/ and /crawler/queue/, but neither
    endpoint existed anywhere in the backend — every action 404'd.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="discover1", password="pass12345")
        group, _ = Group.objects.get_or_create(name=scraper_group_name())
        self.user.groups.add(group)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_preview_requires_query(self):
        resp = self.client.post("/dashboard/api/v1/crawler/preview/", {}, format="json")
        self.assertEqual(resp.status_code, 400)

    @patch("dashboard.api.views.filter_discovery_hits")
    @patch("dashboard.api.views.discover_websites")
    def test_preview_returns_kept_and_dropped_hits(self, mock_discover, mock_filter):
        mock_discover.return_value = [
            {"domain": "https://kept.example", "source_url": "https://kept.example/tenders"},
            {"domain": "https://dropped.example", "source_url": "https://dropped.example/"},
        ]
        mock_filter.return_value = (
            [{"domain": "https://kept.example", "source_url": "https://kept.example/tenders"}],
            [
                {
                    "domain": "https://dropped.example",
                    "source_url": "https://dropped.example/",
                    "drop_reason": "No active opportunity",
                }
            ],
        )
        resp = self.client.post(
            "/dashboard/api/v1/crawler/preview/",
            {"query": "translation tenders Kenya", "max_results": 10},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(len(body["hits"]), 1)
        self.assertEqual(body["urls"], ["https://kept.example/tenders"])
        self.assertEqual(body["dropped_count"], 1)
        self.assertEqual(body["dropped"][0]["drop_reason"], "No active opportunity")

    def test_queue_requires_urls_or_query(self):
        resp = self.client.post("/dashboard/api/v1/crawler/queue/", {}, format="json")
        self.assertEqual(resp.status_code, 400)

    @patch("crawler.tasks.crawl_domain_task.delay")
    def test_queue_urls_creates_domains_without_crawl(self, mock_delay):
        resp = self.client.post(
            "/dashboard/api/v1/crawler/queue/",
            {"query": "x", "urls": ["https://queued.example/tenders/123"], "auto_crawl": False},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["queued"], 1)
        self.assertEqual(body["new_domains"], 1)
        self.assertIsNone(body["run_id"])
        domain = DiscoveredDomain.objects.get(domain="https://queued.example")
        self.assertEqual(domain.owner_id, self.user.id)
        self.assertEqual(domain.crawl_status, "pending")
        self.assertEqual(domain.source_url, "https://queued.example/tenders/123")
        mock_delay.assert_not_called()

    @patch("dashboard.api.views.crawl_domain_task.delay")
    def test_queue_with_auto_crawl_starts_run(self, mock_delay):
        resp = self.client.post(
            "/dashboard/api/v1/crawler/queue/",
            {"query": "x", "urls": ["https://crawlme.example/rfp"], "auto_crawl": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertIsNotNone(body["run_id"])
        run = CrawlRun.objects.get(id=body["run_id"])
        self.assertEqual(run.status, CrawlRunStatus.RUNNING)
        self.assertEqual(run.domains_queued, 1)
        self.assertEqual(run.owner_id, self.user.id)
        mock_delay.assert_called_once()
        self.assertEqual(mock_delay.call_args.kwargs["run_id"], run.id)

    @patch("dashboard.api.views.crawl_domain_task.delay")
    def test_queue_auto_crawl_skips_already_crawled_domains(self, mock_delay):
        DiscoveredDomain.objects.create(
            domain="https://done.example", crawl_status="completed", owner=self.user
        )
        resp = self.client.post(
            "/dashboard/api/v1/crawler/queue/",
            {"query": "x", "urls": ["https://done.example/"], "auto_crawl": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # Domain already exists and isn't pending: nothing new, no crawl run.
        self.assertEqual(body["new_domains"], 0)
        self.assertIsNone(body["run_id"])
        mock_delay.assert_not_called()


class RegisterUserCommandTests(TestCase):
    def test_update_keeps_existing_admin_role_by_default(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="opsadmin",
            password="oldpass123",
            is_staff=True,
            is_superuser=True,
        )
        out = StringIO()
        call_command(
            "register_user",
            "opsadmin",
            "--update",
            "--password",
            "newpass123",
            stdout=out,
        )
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


class AuthProfileApiTests(TestCase):
    """Self-service profile view/edit and password change (new: previously no
    user-profile endpoints existed at all — username/role stayed admin-only via
    Admin -> Users, and there was no way for a user to change their own password
    outside of a CLI management command)."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="staffprofile",
            password="orig-pass-123",
            email="staff@example.com",
            first_name="Staff",
            last_name="Member",
        )
        group, _ = Group.objects.get_or_create(name=scraper_group_name())
        self.user.groups.add(group)
        self.client = APIClient()
        self.client.force_login(self.user)

    def test_get_profile_requires_authentication(self):
        anon = APIClient()
        resp = anon.get("/dashboard/api/auth/profile/")
        self.assertEqual(resp.status_code, 401)

    def test_get_profile_returns_own_account_fields(self):
        resp = self.client.get("/dashboard/api/auth/profile/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["username"], "staffprofile")
        self.assertEqual(data["email"], "staff@example.com")
        self.assertEqual(data["first_name"], "Staff")
        self.assertEqual(data["last_name"], "Member")
        self.assertEqual(data["role"], "staff")

    def test_patch_profile_updates_name_and_email(self):
        resp = self.client.patch(
            "/dashboard/api/auth/profile/",
            data={"first_name": "New", "last_name": "Name", "email": "new@example.com"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "New")
        self.assertEqual(self.user.last_name, "Name")
        self.assertEqual(self.user.email, "new@example.com")

    def test_patch_profile_rejects_invalid_email(self):
        resp = self.client.patch(
            "/dashboard/api/auth/profile/",
            data={"email": "not-an-email"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "staff@example.com")

    def test_patch_profile_cannot_change_username_or_role(self):
        """Username/role stay admin-managed via Admin -> Users — the profile PATCH
        body simply has no path to touch them, unlike AdminUsersPage's endpoints."""
        resp = self.client.patch(
            "/dashboard/api/auth/profile/",
            data={"username": "hijacked", "is_staff": True},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "staffprofile")
        self.assertFalse(self.user.is_staff)

    def test_change_password_requires_correct_current_password(self):
        resp = self.client.post(
            "/dashboard/api/auth/profile/password/",
            data={"current_password": "wrong-password", "new_password": "new-strong-pass-1"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("incorrect", resp.json()["error"].lower())

    def test_change_password_enforces_validators(self):
        """AUTH_PASSWORD_VALIDATORS (min length, common-password check) apply here too."""
        resp = self.client.post(
            "/dashboard/api/auth/profile/password/",
            data={"current_password": "orig-pass-123", "new_password": "password"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_change_password_succeeds_and_keeps_session_alive(self):
        resp = self.client.post(
            "/dashboard/api/auth/profile/password/",
            data={"current_password": "orig-pass-123", "new_password": "new-strong-pass-1"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-strong-pass-1"))

        # update_session_auth_hash should keep this same client session authenticated —
        # a subsequent request must not be bounced to 401.
        follow_up = self.client.get("/dashboard/api/auth/profile/")
        self.assertEqual(follow_up.status_code, 200)
