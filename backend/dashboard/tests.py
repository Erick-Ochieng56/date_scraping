from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from io import StringIO

from crawler.models import CrawlRun, CrawlRunStatus, CrawlRunTrigger, CrawlSchedule, CrawlSource, DiscoveredDomain
from dashboard.models import ActivityLog
from dashboard.utils import log_activity
from leads.models import Lead, LeadStatus, Prospect, ProspectStatus
from scraper.models import ScrapeRun, ScrapeRunStatus, ScrapeSession, ScrapeSessionStatus, ScrapeTarget

from .permissions import scraper_group_name


class DashboardV1ApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="staff1", password="pass12345")
        group, _ = Group.objects.get_or_create(name=scraper_group_name())
        self.user.groups.add(group)
        self.client = APIClient()
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

    def test_prospect_convert_flow_creates_lead(self):
        prospect = Prospect.objects.create(
            owner=self.user,
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

    def test_prospect_list_includes_score_from_raw_payload(self):
        Prospect.objects.create(
            owner=self.user,
            company="Scored Co",
            email="scored@example.com",
            status=ProspectStatus.NEW,
            source_name="web_crawler",
            raw_payload={"translation_need_score": 72, "score_label": "high"},
        )
        Prospect.objects.create(
            owner=self.user,
            company="Low Co",
            email="low@example.com",
            status=ProspectStatus.NEW,
            raw_payload={"translation_need_score": 25, "score_label": "low"},
        )
        resp = self.client.get("/dashboard/api/v1/prospects/?sort=score")
        self.assertEqual(resp.status_code, 200)
        items = resp.data["data"]["items"]
        self.assertEqual(items[0]["company"], "Scored Co")
        self.assertEqual(items[0]["translation_need_score"], 72)
        self.assertEqual(items[0]["score_label"], "high")
        self.assertEqual(items[0]["source_name"], "web_crawler")

        filtered = self.client.get("/dashboard/api/v1/prospects/?min_score=60")
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.data["data"]["total"], 1)
        self.assertEqual(filtered.data["data"]["items"][0]["company"], "Scored Co")

    def test_event_prospect_promote_creates_prospect(self):
        from crawler.models import EventProspect

        ep = EventProspect.objects.create(
            owner=self.user,
            event_name="East Africa Summit 2026",
            organizer_name="Summit Org",
            organizer_domain="summit-example.org",
            translation_need_score=75,
            urgency_score=80,
            languages_involved=["English", "Swahili"],
            status="new",
        )
        resp = self.client.post(f"/dashboard/api/v1/event-prospects/{ep.id}/promote/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        self.assertTrue(resp.data["created"])
        ep.refresh_from_db()
        self.assertEqual(ep.status, "converted")
        self.assertTrue(Prospect.objects.filter(id=resp.data["prospect_id"], source_name="event_crawler").exists())

    def test_lead_bulk_interested_transition(self):
        lead = Lead.objects.create(owner=self.user, company="B", status=LeadStatus.CONTACTED)
        resp = self.client.post(
            "/dashboard/api/v1/leads/bulk/interested/",
            {"lead_ids": [lead.id]},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        lead.refresh_from_db()
        self.assertEqual(lead.status, LeadStatus.INTERESTED)

    def test_leads_bulk_sync_crm_queues_interested(self):
        from unittest.mock import patch

        lead = Lead.objects.create(company="Sync Co", status=LeadStatus.INTERESTED, owner=self.user)
        with patch("crm_integration.tasks.sync_lead_to_perfex.delay") as mock_delay:
            resp = self.client.post(
                "/dashboard/api/v1/leads/bulk/sync-crm/",
                {"lead_ids": [lead.id]},
                format="json",
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        mock_delay.assert_called_once_with(lead.id)

    def test_prospect_manual_create(self):
        resp = self.client.post(
            "/dashboard/api/v1/prospects/",
            {
                "company": "Manual Co",
                "event_name": "Trade Show",
                "email": "manual@example.com",
                "source_name": "manual",
                "status": "new",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["data"]["company"], "Manual Co")
        self.assertEqual(Prospect.objects.filter(company="Manual Co", owner=self.user).count(), 1)

    def test_lead_manual_create(self):
        resp = self.client.post(
            "/dashboard/api/v1/leads/",
            {
                "company": "Lead Co",
                "full_name": "Jane Doe",
                "email": "jane@example.com",
                "status": "contacted",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["data"]["company"], "Lead Co")
        self.assertEqual(Lead.objects.filter(company="Lead Co", owner=self.user).count(), 1)

    def test_metrics_quality_returns_pipeline_signals(self):
        Prospect.objects.create(
            owner=self.user,
            company="High",
            status=ProspectStatus.NEW,
            raw_payload={"translation_need_score": 85},
        )
        resp = self.client.get("/dashboard/api/v1/metrics/quality/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        data = resp.data["data"]
        self.assertIn("prospects_high_score_new", data)
        self.assertIn("discovery_drops", data)
        self.assertGreaterEqual(data["prospects_high_score_new"], 1)

    def test_notifications_list_and_mark_read(self):
        from dashboard.models import Notification

        n = Notification.objects.create(
            user=self.user,
            title="Test alert",
            message="Something happened",
            type="info",
        )
        resp = self.client.get("/dashboard/api/v1/notifications/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["unread_count"], 1)
        self.assertEqual(resp.data["data"]["items"][0]["id"], n.id)

        read = self.client.post(f"/dashboard/api/v1/notifications/{n.id}/read/")
        self.assertEqual(read.status_code, 200)
        n.refresh_from_db()
        self.assertTrue(n.read)

        Notification.objects.create(
            user=self.user,
            title="Second",
            message="Unread",
            type="warning",
        )
        read_all = self.client.post("/dashboard/api/v1/notifications/read-all/")
        self.assertEqual(read_all.status_code, 200)
        self.assertEqual(read_all.data["marked"], 1)
        self.assertEqual(Notification.objects.filter(user=self.user, read=False).count(), 0)

        limited = self.client.get("/dashboard/api/v1/notifications/?limit=1")
        self.assertEqual(limited.status_code, 200)
        self.assertEqual(len(limited.data["data"]["items"]), 1)

    def test_profile_get_patch_and_change_password(self):
        self.user.email = "staff1@example.com"
        self.user.save(update_fields=["email"])

        resp = self.client.get("/dashboard/api/v1/profile/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["username"], "staff1")
        self.assertEqual(resp.data["data"]["email"], "staff1@example.com")
        self.assertEqual(resp.data["data"]["role"], "staff")

        patch = self.client.patch("/dashboard/api/v1/profile/", {"email": "new@example.com"}, format="json")
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(patch.data["data"]["email"], "new@example.com")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")

        bad_pw = self.client.post(
            "/dashboard/api/v1/profile/change-password/",
            {"current_password": "wrong", "new_password": "newpass12345"},
            format="json",
        )
        self.assertEqual(bad_pw.status_code, 400)

        change = self.client.post(
            "/dashboard/api/v1/profile/change-password/",
            {"current_password": "pass12345", "new_password": "newpass12345"},
            format="json",
        )
        self.assertEqual(change.status_code, 200)
        self.assertTrue(change.data["success"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass12345"))

    def test_trigger_all_targets_queues_enabled_only(self):
        from unittest.mock import MagicMock, patch

        ScrapeTarget.objects.create(
            name="Enabled",
            start_url="https://example.com",
            owner=self.user,
            enabled=True,
        )
        ScrapeTarget.objects.create(
            name="Disabled",
            start_url="https://example.org",
            owner=self.user,
            enabled=False,
        )
        with patch("dashboard.api.views.scrape_target") as mock_scrape:
            mock_task = MagicMock()
            mock_task.id = "task-abc"
            mock_scrape.delay.return_value = mock_task
            resp = self.client.post("/dashboard/api/v1/targets/trigger/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["count"], 1)
        mock_scrape.delay.assert_called_once()

    def test_prospect_patch_updates_fields(self):
        prospect = Prospect.objects.create(
            owner=self.user,
            company="Before",
            email="before@example.com",
            status=ProspectStatus.NEW,
        )
        resp = self.client.patch(
            f"/dashboard/api/v1/prospects/{prospect.id}/",
            {"company": "After", "notes": "Updated note"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        prospect.refresh_from_db()
        self.assertEqual(prospect.company, "After")
        self.assertEqual(prospect.notes, "Updated note")

    def test_lead_patch_updates_lead_value(self):
        lead = Lead.objects.create(owner=self.user, company="Co", status=LeadStatus.CONTACTED, lead_value=100)
        resp = self.client.patch(
            f"/dashboard/api/v1/leads/{lead.id}/",
            {"lead_value": "2500.00", "full_name": "Alex"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.full_name, "Alex")
        self.assertEqual(float(lead.lead_value), 2500.0)

    def test_convert_sets_lead_value_from_score(self):
        prospect = Prospect.objects.create(
            owner=self.user,
            company="Scored",
            email="scored@example.com",
            status=ProspectStatus.CONTACTED,
            raw_payload={"translation_need_score": 85},
        )
        resp = self.client.post(f"/dashboard/api/v1/prospects/{prospect.id}/convert/")
        self.assertEqual(resp.status_code, 200)
        lead = Lead.objects.get(prospect=prospect)
        self.assertEqual(float(lead.lead_value), 7500.0)

    def test_prospect_duplicates_by_email(self):
        a = Prospect.objects.create(owner=self.user, company="A", email="dup@example.com", status=ProspectStatus.NEW)
        Prospect.objects.create(owner=self.user, company="B", email="dup@example.com", status=ProspectStatus.NEW)
        resp = self.client.get(f"/dashboard/api/v1/prospects/{a.id}/duplicates/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["total"], 1)
        self.assertEqual(resp.data["data"]["items"][0]["match_reason"], "same_email")

    def test_quality_workflow_score_to_crm(self):
        from unittest.mock import patch

        prospect = Prospect.objects.create(
            owner=self.user,
            company="Workflow Co",
            email="wf@example.com",
            status=ProspectStatus.NEW,
            raw_payload={"translation_need_score": 72},
        )
        convert = self.client.post(f"/dashboard/api/v1/prospects/{prospect.id}/convert/")
        self.assertEqual(convert.status_code, 200)
        lead_id = convert.data["lead_id"]
        lead = Lead.objects.get(id=lead_id)
        self.assertIsNotNone(lead.lead_value)

        interested = self.client.post(f"/dashboard/api/v1/leads/{lead_id}/mark-interested/")
        self.assertEqual(interested.status_code, 200)

        with patch("crm_integration.tasks.sync_lead_to_perfex.delay") as mock_delay:
            sync = self.client.post("/dashboard/api/v1/leads/bulk/sync-crm/", {"lead_ids": [lead_id]}, format="json")
        self.assertEqual(sync.status_code, 200)
        self.assertEqual(sync.data["count"], 1)
        mock_delay.assert_called_once_with(lead_id)

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

    def test_start_crawl_session(self):
        from unittest.mock import MagicMock, patch

        with patch("crawler.services.crawl_session.crawl_session_coordinator_task") as mock_coord, patch(
            "crawler.services.crawl_session.finalize_crawl_session"
        ) as mock_finalize:
            mock_task = MagicMock()
            mock_task.id = "coord-abc"
            mock_coord.delay.return_value = mock_task
            mock_finalize.apply_async.return_value = MagicMock()

            resp = self.client.post(
                "/dashboard/api/v1/crawl-sessions/",
                {"preset": "1h"},
                format="json",
            )

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data["success"])
        run = CrawlRun.objects.get(id=resp.data["run_id"])
        self.assertEqual(run.trigger, CrawlRunTrigger.SESSION)
        self.assertEqual(run.duration_minutes, 60)
        self.assertIsNotNone(run.ends_at)
        self.assertEqual(run.status, CrawlRunStatus.RUNNING)
        mock_coord.delay.assert_called_once_with(run.id)
        mock_finalize.apply_async.assert_called_once()

    def test_active_session_conflict(self):
        from unittest.mock import MagicMock, patch

        CrawlRun.objects.create(
            owner=self.user,
            trigger=CrawlRunTrigger.SESSION,
            status=CrawlRunStatus.RUNNING,
            ends_at=timezone.now() + timedelta(hours=2),
            duration_minutes=120,
            session_mode=True,
        )

        with patch("crawler.services.crawl_session.crawl_session_coordinator_task") as mock_coord, patch(
            "crawler.services.crawl_session.finalize_crawl_session"
        ):
            mock_coord.delay.return_value = MagicMock(id="x")
            resp = self.client.post(
                "/dashboard/api/v1/crawl-sessions/",
                {"duration_minutes": 60},
                format="json",
            )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("active", resp.data["error"].lower())

    def test_cancel_session_creates_notification(self):
        from unittest.mock import patch

        run = CrawlRun.objects.create(
            owner=self.user,
            trigger=CrawlRunTrigger.SESSION,
            status=CrawlRunStatus.RUNNING,
            ends_at=timezone.now() + timedelta(hours=1),
            duration_minutes=60,
            session_mode=True,
            coordinator_task_id="coord-1",
        )

        with patch("dashboard.api.views.current_app.control.revoke"):
            resp = self.client.post(f"/dashboard/api/v1/crawl-sessions/{run.id}/stop/")

        self.assertEqual(resp.status_code, 200)
        run.refresh_from_db()
        self.assertEqual(run.status, CrawlRunStatus.FAILED)
        from dashboard.models import Notification

        self.assertTrue(
            Notification.objects.filter(user=self.user, title__icontains="stopped").exists()
        )

    def test_session_serializer_fields(self):
        run = CrawlRun.objects.create(
            owner=self.user,
            trigger=CrawlRunTrigger.SESSION,
            status=CrawlRunStatus.RUNNING,
            ends_at=timezone.now() + timedelta(minutes=30),
            duration_minutes=30,
            session_mode=True,
        )
        resp = self.client.get(f"/dashboard/api/v1/crawl-runs/{run.id}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.data["data"]
        self.assertEqual(data["trigger"], "session")
        self.assertEqual(data["duration_minutes"], 30)
        self.assertIsNotNone(data["time_remaining_seconds"])
        self.assertTrue(data["is_session_active"])

    def test_get_active_crawl_session(self):
        run = CrawlRun.objects.create(
            owner=self.user,
            trigger=CrawlRunTrigger.SESSION,
            status=CrawlRunStatus.RUNNING,
            ends_at=timezone.now() + timedelta(hours=3),
            duration_minutes=180,
            session_mode=True,
        )
        resp = self.client.get("/dashboard/api/v1/crawl-sessions/active/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["id"], run.id)

    def test_crawl_schedule_crud(self):
        resp = self.client.post(
            "/dashboard/api/v1/crawl-schedules/",
            {
                "name": "Nightly crawl",
                "enabled": True,
                "interval_minutes": 720,
                "session_duration_minutes": 120,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        schedule_id = resp.data["data"]["id"]
        self.assertEqual(resp.data["data"]["name"], "Nightly crawl")
        self.assertTrue(resp.data["data"]["is_due"])

        resp = self.client.get("/dashboard/api/v1/crawl-schedules/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["total"], 1)

        resp = self.client.patch(
            f"/dashboard/api/v1/crawl-schedules/{schedule_id}/",
            {"enabled": False},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["data"]["enabled"])

        resp = self.client.delete(f"/dashboard/api/v1/crawl-schedules/{schedule_id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(CrawlSchedule.objects.filter(id=schedule_id).exists())

    def test_crawl_schedule_owner_scoped(self):
        User = get_user_model()
        other = User.objects.create_user(username="other", password="pass12345")
        schedule = CrawlSchedule.objects.create(
            owner=other,
            name="Other schedule",
            interval_minutes=360,
        )
        resp = self.client.get(f"/dashboard/api/v1/crawl-schedules/{schedule.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_start_scrape_session(self):
        from unittest.mock import MagicMock, patch

        with patch("scraper.services.scrape_session.scrape_session_coordinator_task") as mock_coord, patch(
            "scraper.services.scrape_session.finalize_scrape_session"
        ) as mock_finalize:
            mock_task = MagicMock()
            mock_task.id = "coord-scrape"
            mock_coord.delay.return_value = mock_task
            mock_finalize.apply_async.return_value = MagicMock()

            resp = self.client.post(
                "/dashboard/api/v1/scrape-sessions/",
                {"preset": "1h"},
                format="json",
            )

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data["success"])
        session = ScrapeSession.objects.get(id=resp.data["session_id"])
        self.assertEqual(session.duration_minutes, 60)
        self.assertIsNotNone(session.ends_at)
        self.assertEqual(session.status, ScrapeSessionStatus.RUNNING)

    def test_active_scrape_session_conflict(self):
        from unittest.mock import MagicMock, patch

        ScrapeSession.objects.create(
            owner=self.user,
            status=ScrapeSessionStatus.RUNNING,
            ends_at=timezone.now() + timedelta(hours=2),
            duration_minutes=120,
        )

        with patch("scraper.services.scrape_session.scrape_session_coordinator_task") as mock_coord, patch(
            "scraper.services.scrape_session.finalize_scrape_session"
        ):
            mock_coord.delay.return_value = MagicMock(id="x")
            resp = self.client.post(
                "/dashboard/api/v1/scrape-sessions/",
                {"duration_minutes": 60},
                format="json",
            )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("active", resp.data["error"].lower())

    def test_stop_scrape_session(self):
        from unittest.mock import patch

        session = ScrapeSession.objects.create(
            owner=self.user,
            status=ScrapeSessionStatus.RUNNING,
            ends_at=timezone.now() + timedelta(hours=1),
            duration_minutes=60,
            coordinator_task_id="coord-1",
        )

        with patch("dashboard.api.views.current_app.control.revoke"), patch(
            "dashboard.api.views.finalize_scrape_session.delay"
        ) as mock_finalize:
            resp = self.client.post(f"/dashboard/api/v1/scrape-sessions/{session.id}/stop/")
            mock_finalize.assert_called_once()

        self.assertEqual(resp.status_code, 200)

    def test_get_active_scrape_session(self):
        session = ScrapeSession.objects.create(
            owner=self.user,
            status=ScrapeSessionStatus.RUNNING,
            ends_at=timezone.now() + timedelta(hours=3),
            duration_minutes=180,
        )
        resp = self.client.get("/dashboard/api/v1/scrape-sessions/active/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["id"], session.id)


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
        self.client.force_login(self.admin)

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

    def test_wizard_create_target_name_conflict(self):
        ScrapeTarget.objects.create(name="Taken", start_url="https://example.com/a", owner=self.admin)
        resp = self.client.post(
            "/dashboard/wizard/create-target/",
            {"url": "https://example.com/b", "name": "Taken"},
            format="json",
        )
        self.assertEqual(resp.status_code, 409)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertTrue(data["existing"])

    def test_admin_active_crawl_sessions(self):
        from django.contrib.auth import get_user_model

        staff = get_user_model().objects.create_user(username="session_staff", password="pass12345")
        run = CrawlRun.objects.create(
            owner=staff,
            trigger=CrawlRunTrigger.SESSION,
            status=CrawlRunStatus.RUNNING,
            ends_at=timezone.now() + timedelta(hours=2),
            duration_minutes=120,
            session_mode=True,
        )
        resp = self.client.get("/dashboard/api/admin/v1/crawl-sessions/active/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["data"]), 1)
        self.assertEqual(resp.data["data"][0]["id"], run.id)
        self.assertEqual(resp.data["data"][0]["owner_username"], "session_staff")

    def test_admin_stop_crawl_session(self):
        from unittest.mock import patch
        from django.contrib.auth import get_user_model

        staff = get_user_model().objects.create_user(username="session_staff2", password="pass12345")
        run = CrawlRun.objects.create(
            owner=staff,
            trigger=CrawlRunTrigger.SESSION,
            status=CrawlRunStatus.RUNNING,
            ends_at=timezone.now() + timedelta(hours=1),
            duration_minutes=60,
            session_mode=True,
            coordinator_task_id="coord-x",
        )
        with patch("dashboard.api.views.current_app.control.revoke"):
            resp = self.client.post(f"/dashboard/api/admin/v1/crawl-sessions/{run.id}/stop/")
        self.assertEqual(resp.status_code, 200)
        run.refresh_from_db()
        self.assertEqual(run.status, CrawlRunStatus.FAILED)


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
