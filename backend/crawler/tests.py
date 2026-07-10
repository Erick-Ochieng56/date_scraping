from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from crawler.models import AISearchJob, AISearchResult, CrawlRun, CrawlRunStatus, CrawlRunTrigger
from crawler.tasks import _run_is_stopped
from crawler.services.active_buyer import (
    check_forward_timeline,
    has_active_buyer_signal,
    is_buyer_procurement_context,
    is_generic_hub_page,
    is_procurement_portal_url,
    is_verifiable_procurement_portal,
    passes_active_buyer_gate,
    portal_has_current_language_opportunity,
    preflight_candidate_page,
    url_looks_stale,
)
from crawler.services.competitor_filter import is_likely_competitor
from crawler.services.directory_filter import is_directory_or_aggregator
from crawler.services.event_validation import accept_event_candidate
from crawler.services.geo_filter import (
    ensure_query_has_geo,
    passes_geo_gate,
    text_mentions_east_africa,
)
from crawler.services.promote_ai_result import promote_ai_search_result_to_prospect
from crawler.services.ai_page_extract import (
    merge_extraction_into_prospect,
    qualify_ai_search_candidate,
    result_promotable,
    result_translation_need_score,
)
from crawler.services.prospect_verify import (
    looks_like_past_event_text,
    page_supports_prospect,
)
from leads.models import Prospect

User = get_user_model()


class CompetitorFilterTests(TestCase):
    def test_flags_lsp_seller_page(self):
        text = (
            "We offer translation and interpretation services. "
            "Our team of translators supports 40 language pairs."
        )
        flagged, reason = is_likely_competitor("example-events.org", [text])
        self.assertTrue(flagged)
        self.assertIn("seller", reason.lower())

    def test_allows_buyer_rfp_page(self):
        text = (
            "Request for proposals: simultaneous interpretation and conference equipment "
            "for the regional health summit in Nairobi, Kenya. Procurement deadline next month."
        )
        flagged, _ = is_likely_competitor("health-ministry.go.ke", [text])
        self.assertFalse(flagged)


class EventValidationTests(TestCase):
    def test_rejects_past_dated_event(self):
        ok, reason = accept_event_candidate(
            {
                "translation_need_score": 80,
                "event_url": "https://example.org/events/summit-2025",
                "event_date": "2025-01-10",
                "event_date_raw": "10 January 2025",
                "event_location": "Nairobi, Kenya",
            },
            today=date(2026, 6, 17),
        )
        self.assertFalse(ok)
        self.assertIn("past", reason.lower())

    def test_rejects_low_score_without_date(self):
        ok, reason = accept_event_candidate(
            {
                "translation_need_score": 55,
                "event_url": "https://example.org/events/summit",
                "event_date": "",
                "event_date_raw": "",
                "event_location": "Kampala, Uganda",
            }
        )
        self.assertFalse(ok)
        self.assertIn("date", reason.lower())

    def test_accepts_high_score_with_future_date(self):
        ok, _ = accept_event_candidate(
            {
                "translation_need_score": 85,
                "event_url": "https://example.org/events/summit-2026",
                "event_date": "2026-09-01",
                "event_date_raw": "1 September 2026",
                "event_location": "Dar es Salaam, Tanzania",
            },
            today=date(2026, 6, 17),
        )
        self.assertTrue(ok)

    def test_rejects_foreign_event_in_strict_geo_mode(self):
        ok, reason = accept_event_candidate(
            {
                "translation_need_score": 85,
                "event_url": "https://example.com/events/summit-2026",
                "event_date": "2026-09-01",
                "event_date_raw": "1 September 2026",
                "event_location": "London, United Kingdom",
            },
            today=date(2026, 6, 17),
        )
        self.assertFalse(ok)
        self.assertIn("east africa", reason.lower())


class ProspectVerifyTests(TestCase):
    def test_detects_past_event_language(self):
        self.assertTrue(looks_like_past_event_text("The conference was held in Nairobi in 2024"))

    @override_settings(CRAWLER_GEO_MODE="global")
    def test_page_supports_prospect_requires_topic_overlap(self):
        ok, reason = page_supports_prospect(
            (
                "Local bakery menu and catering options for weddings, birthdays, and "
                "corporate lunches. We deliver fresh bread, pastries, and custom cakes "
                "across the city every morning."
            ),
            seed_topic="East Africa medical conference interpretation tender",
        )
        self.assertFalse(ok)
        self.assertIn("topic", reason.lower())

    @override_settings(CRAWLER_GEO_MODE="global")
    def test_page_supports_prospect_accepts_buyer_intent_without_full_seed_overlap(self):
        ok, reason = page_supports_prospect(
            (
                "The regional health association published an RFP for simultaneous "
                "interpretation services at an upcoming summit in Nairobi. Procurement "
                "deadline is next month for qualified language service vendors."
            ),
            seed_topic="East Africa medical conference interpretation tender",
            intent_reference="NGOs procuring interpretation for programmes or events",
        )
        self.assertTrue(ok, reason)

    def test_page_supports_prospect_accepts_intent_reference_overlap(self):
        ok, reason = page_supports_prospect(
            (
                "Our hospital multilingual patient information programme ensures every "
                "patient receives care instructions in their preferred language across "
                "all departments and outpatient clinics in Kenya."
            ),
            seed_topic="unrelated seed topic words only",
            intent_reference="Healthcare providers with ongoing multilingual comms needs",
        )
        self.assertTrue(ok, reason)


class GeoFilterTests(TestCase):
    @override_settings(CRAWLER_GEO_MODE="east_africa")
    def test_ensure_query_has_geo_appends_region(self):
        q = ensure_query_has_geo("interpretation tender RFP", "")
        self.assertIn("Kenya", q)
        self.assertIn("interpretation", q)

    @override_settings(CRAWLER_GEO_MODE="east_africa")
    def test_passes_geo_gate_accepts_kenya_text(self):
        ok, _ = passes_geo_gate("Annual summit in Nairobi, Kenya", domain="example.org")
        self.assertTrue(ok)

    @override_settings(CRAWLER_GEO_MODE="east_africa")
    def test_passes_geo_gate_rejects_foreign_only(self):
        ok, reason = passes_geo_gate("Conference in London, United Kingdom", domain="example.com")
        self.assertFalse(ok)
        self.assertIn("outside", reason.lower())

    def test_text_mentions_east_africa(self):
        self.assertTrue(text_mentions_east_africa("Forum in Kampala, Uganda"))


class DirectoryFilterTests(TestCase):
    def test_flags_eventbrite_domain(self):
        flagged, reason = is_directory_or_aggregator("www.eventbrite.com")
        self.assertTrue(flagged)
        self.assertIn("eventbrite", reason.lower())

    def test_allows_company_domain(self):
        flagged, _ = is_directory_or_aggregator("health-ministry.go.ke")
        self.assertFalse(flagged)

    def test_flags_tender_aggregator_domains(self):
        cases = (
            ("www.tendersinfo.com", "tendersinfo"),
            ("tenderskenya.co.ke", "tenderskenya"),
            ("developmentaid.org", "developmentaid"),
        )
        for host, needle in cases:
            flagged, reason = is_directory_or_aggregator(host)
            self.assertTrue(flagged, host)
            self.assertIn(needle, reason.lower())


class PromoteAiResultTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="staff1", password="x")
        self.job = AISearchJob.objects.create(
            owner=self.user,
            seed_topic="East Africa medical conference",
            region="Kenya",
            status="done",
        )
        self.result = AISearchResult.objects.create(
            job=self.job,
            domain="example-hospital.or.ke",
            org_name="Example Hospital",
            org_type="hospital",
            why_needs_translation="Multilingual patient information programme",
            contact_email="procurement@example-hospital.or.ke",
            raw_data={"source_url": "https://example-hospital.or.ke/procurement"},
        )

    def test_promote_creates_prospect(self):
        prospect, created = promote_ai_search_result_to_prospect(
            self.result,
            owner_id=self.user.id,
        )
        self.assertTrue(created)
        self.assertEqual(prospect.company, "Example Hospital")
        self.assertEqual(prospect.email, "procurement@example-hospital.or.ke")
        self.assertEqual(prospect.owner_id, self.user.id)
        self.result.refresh_from_db()
        self.assertEqual(self.result.raw_data.get("promoted_prospect_id"), prospect.id)

    def test_promote_is_idempotent(self):
        first, created_first = promote_ai_search_result_to_prospect(
            self.result,
            owner_id=self.user.id,
        )
        self.assertTrue(created_first)
        second, created_second = promote_ai_search_result_to_prospect(
            self.result,
            owner_id=self.user.id,
        )
        self.assertFalse(created_second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(Prospect.objects.filter(owner=self.user).count(), 1)


class AiPageExtractTests(TestCase):
    def test_merge_extraction_populates_org_and_score(self):
        merged = merge_extraction_into_prospect(
            {"domain": "example.or.ke", "org_name": "", "why_needs_translation": "fallback"},
            {
                "org_name": "Example NGO",
                "org_type": "ngo",
                "translation_need_score": 82,
                "evidence_snippet": "RFP for simultaneous interpretation at regional summit.",
                "translation_need_reasoning": "Active procurement for interpretation services.",
                "buyer_signal_type": "tender",
                "international_signals": ["multilingual programme"],
                "contact_email": "proc@example.or.ke",
            },
        )
        self.assertEqual(merged["org_name"], "Example NGO")
        self.assertEqual(merged["translation_need_score"], 82)
        self.assertIn("interpretation", merged["evidence_snippet"])

    @override_settings(
        GEMINI_API_KEY="",
        AI_SEARCH_MIN_SCORE=80,
        AI_SEARCH_REQUIRE_ACTIVE_BUYER=True,
        CRAWLER_GEO_MODE="global",
    )
    def test_qualify_without_gemini_uses_rule_verify(self):
        page = (
            "Request for proposal: simultaneous interpretation services for the East Africa "
            "medical conference. Closing date 30 September 2026. National Health Association "
            "invites qualified vendors to submit proposals for conference interpretation in Nairobi."
        )
        ok, reason, enriched = qualify_ai_search_candidate(
            {
                "domain": "health-assoc.or.ke",
                "source_url": "https://health-assoc.or.ke/tenders/interpretation-rfp-2026",
                "org_name": "",
            },
            seed_topic="East Africa medical conference interpretation tender",
            page_text=page,
        )
        self.assertTrue(ok, reason)
        self.assertEqual(enriched["domain"], "health-assoc.or.ke")

    @override_settings(AI_SEARCH_REQUIRE_ACTIVE_BUYER=True, CRAWLER_GEO_MODE="global")
    def test_qualify_rejects_org_homepage(self):
        page = (
            "The East African Community is an intergovernmental organization working toward "
            "political integration across partner states with multilingual programmes and "
            "international cooperation across the region."
        )
        ok, reason, _ = qualify_ai_search_candidate(
            {
                "domain": "eac.int",
                "source_url": "https://www.eac.int/",
            },
            seed_topic="East Africa interpretation tender",
            page_text=page,
            allow_gemini=False,
        )
        self.assertFalse(ok)
        self.assertIn("opportunity", reason.lower())

    def test_result_promotable_respects_score(self):
        user = User.objects.create_user(username="scoreuser", password="x")
        job = AISearchJob.objects.create(owner=user, seed_topic="test", status="done")
        low = AISearchResult.objects.create(
            job=job,
            domain="low.example",
            raw_data={"translation_need_score": 45},
        )
        high = AISearchResult.objects.create(
            job=job,
            domain="high.example",
            raw_data={"translation_need_score": 85},
        )
        legacy = AISearchResult.objects.create(job=job, domain="legacy.example", raw_data={})
        with self.settings(AI_SEARCH_PROMOTE_MIN_SCORE=80):
            self.assertFalse(result_promotable(low))
            self.assertTrue(result_promotable(high))
            self.assertFalse(result_promotable(legacy))
        self.assertEqual(result_translation_need_score(high), 85)


class ActiveBuyerTests(TestCase):
    def test_detects_buyer_rfp_context(self):
        text = "Request for proposal for translation services. Closing date 15 August 2026."
        self.assertTrue(is_buyer_procurement_context(text))

    def test_rejects_careers_hub(self):
        self.assertTrue(
            is_generic_hub_page(
                "https://msf.or.ke/work-with-us/work-field",
                "We seek bilingual field staff for our medical programmes.",
            )
        )

    def test_rejects_past_year_only_content(self):
        ok, reason = check_forward_timeline(
            "The FIFAfrica conference was held in 2022 in Kampala with past speakers listed.",
            today=date(2026, 6, 19),
        )
        self.assertFalse(ok)
        self.assertIn("past", reason.lower())

    def test_buyer_tender_not_flagged_as_lsp(self):
        page = (
            "Request for proposal: English-French translation services for research publications. "
            "Closing date 1 December 2026. Submit proposals to procurement@icipe.org."
        )
        flagged, _ = is_likely_competitor("icipe.org", [page])
        self.assertFalse(flagged)

    def test_has_active_buyer_signal_on_tender_page(self):
        page = (
            "Invitation to tender for simultaneous interpretation at annual summit. "
            "Deadline for submission: 20 October 2026."
        )
        ok, _ = has_active_buyer_signal(
            page,
            url="https://example.or.ke/tenders/interpretation-2026",
        )
        self.assertTrue(ok)

    def test_verified_portal_with_current_language_tender(self):
        page = (
            "Procurement notices. Open tenders.\n"
            "RFP: Provision of simultaneous interpretation services for annual forum. "
            "Closing date 15 November 2026.\n"
            "Closed: Translation equipment hire 2024 — contract awarded."
        )
        ok, reason = portal_has_current_language_opportunity(page, today=date(2026, 6, 19))
        self.assertTrue(ok, reason)
        verifiable, _ = is_verifiable_procurement_portal(
            "agra.org",
            url="https://agra.org/opportunities/procurement-notices/",
            page_text=page,
        )
        self.assertTrue(verifiable)
        self.assertFalse(
            is_generic_hub_page(
                "https://agra.org/opportunities/procurement-notices/",
                page,
                domain="agra.org",
            )
        )

    def test_verified_portal_rejects_past_only_language_tenders(self):
        page = (
            "Procurement notices archive. "
            "Tender: Translation services for 2023 annual report — closed. "
            "Interpretation services for 2024 summit — contract awarded."
        )
        ok, reason = portal_has_current_language_opportunity(page, today=date(2026, 6, 19))
        self.assertFalse(ok)
        self.assertIn("past", reason.lower())

    def test_third_party_aggregator_not_verifiable_portal(self):
        verifiable, reason = is_verifiable_procurement_portal(
            "kenyatenders.com",
            url="https://www.kenyatenders.com/tender/interpretation",
            page_text="Tender for interpretation services closing 2026.",
        )
        self.assertFalse(verifiable)
        self.assertIn("aggregator", reason.lower())

    @override_settings(AI_SEARCH_REQUIRE_ACTIVE_BUYER=True, CRAWLER_GEO_MODE="global")
    def test_qualify_accepts_verified_portal_with_current_tender(self):
        page = (
            "AGRA procurement notices. Current opportunities.\n"
            "Invitation to tender: French-Portuguese translation of programme materials. "
            "Submission deadline 30 September 2026. Email procurement@agra.org."
        )
        ok, reason, _ = qualify_ai_search_candidate(
            {
                "domain": "agra.org",
                "source_url": "https://agra.org/opportunities/procurement-notices/",
            },
            seed_topic="East Africa NGO translation tender",
            page_text=page,
            allow_gemini=False,
        )
        self.assertTrue(ok, reason)


class DiscoveryQualifyTests(TestCase):
    @patch("crawler.services.discovery_qualify.fetch_page_for_qualification")
    def test_rejects_tender_aggregator(self, mock_fetch):
        mock_fetch.return_value = (
            True,
            "Tender for interpretation services closing 2026.",
            "",
        )
        from crawler.services.discovery_qualify import filter_discovery_hit

        ok, reason = filter_discovery_hit(
            {
                "domain": "https://www.kenyatenders.com",
                "source_url": "https://www.kenyatenders.com/tender/interpretation",
            }
        )
        self.assertFalse(ok)
        self.assertIn("aggregator", reason.lower())

    @patch("crawler.services.discovery_qualify.fetch_page_for_qualification")
    def test_rejects_stale_pdf_url(self, mock_fetch):
        mock_fetch.return_value = (False, "", "PDF document (skipped)")
        from crawler.services.discovery_qualify import filter_discovery_hit

        ok, reason = filter_discovery_hit(
            {
                "domain": "https://www.idlo.int",
                "source_url": "https://www.idlo.int/sites/default/files/itb_no_n_148-2024_ken.pdf",
            }
        )
        self.assertFalse(ok)
        self.assertTrue(
            "pdf" in reason.lower() or "archived" in reason.lower(),
            reason,
        )

    @patch("crawler.services.discovery_qualify.fetch_page_for_qualification")
    @override_settings(CRAWLER_GEO_MODE="global", CRAWLER_REQUIRE_ACTIVE_BUYER=True)
    def test_rejects_kelinkenya_2014_rfp_url(self, mock_fetch):
        from crawler.services.discovery_qualify import filter_discovery_hit

        ok, reason = filter_discovery_hit(
            {
                "domain": "https://www.kelinkenya.org",
                "source_url": (
                    "https://www.kelinkenya.org/request-for-proposal-for-goods-and-services-"
                    "rfp-kelinfaoeoi42014"
                ),
            }
        )
        self.assertFalse(ok)
        self.assertIn("archived", reason.lower())
        mock_fetch.assert_not_called()

    @patch("crawler.services.discovery_qualify.fetch_page_for_qualification")
    @override_settings(CRAWLER_GEO_MODE="global", CRAWLER_REQUIRE_ACTIVE_BUYER=True)
    def test_accepts_current_rfp_landing(self, mock_fetch):
        mock_fetch.return_value = (
            True,
            (
                "Request for proposal for simultaneous interpretation services. "
                "Closing date 30 September 2026. Submit to procurement@example.or.ke."
            ),
            "",
        )
        from crawler.services.discovery_qualify import filter_discovery_hit

        ok, reason = filter_discovery_hit(
            {
                "domain": "https://www.afhea.org",
                "source_url": "https://afhea.org/request-for-quotation-rfq-interpretation-and-translation-services",
            }
        )
        self.assertTrue(ok, reason)


class StaleOpportunityTests(TestCase):
    def test_url_detects_year_embedded_in_slug(self):
        url = "https://www.kelinkenya.org/request-for-proposal-for-goods-and-services-rfp-kelinfaoeoi42014"
        self.assertTrue(url_looks_stale(url, today=date(2026, 6, 19)))

    def test_rejects_kelin_2014_framework_eoi_page(self):
        page = (
            "Request for proposal for goods and services RFP # KELIN/FAO/EOI/4/2014. "
            "KELIN wishes to invite reputable firms to express interest. "
            "KELIN/FAO/EOI/4/2014 (u) Provision of translation and sign language interpretation services. "
            "This information should reach KELIN Kenya by 28th February, 2014 by 1500Hrs."
        )
        ok, reason = check_forward_timeline(
            page,
            url="https://www.kelinkenya.org/request-for-proposal-for-goods-and-services-rfp-kelinfaoeoi42014",
            today=date(2026, 6, 19),
        )
        self.assertFalse(ok)
        self.assertIn("past", reason.lower())

    def test_sidebar_future_years_do_not_rescue_past_rfp(self):
        page = (
            "Request for proposal RFP # KELIN/FAO/EOI/4/2014. "
            "Provision of translation and sign language interpretation services. "
            "Submit by 28th February, 2014. "
            "Contact us\nNews\nJune 16, 2026\nLatest press release from 2026."
        )
        ok, reason = passes_active_buyer_gate(
            page,
            url="https://www.kelinkenya.org/current-rfp-interpretation",
            today=date(2026, 6, 19),
        )
        self.assertFalse(ok)
        self.assertIn("past", reason.lower())

    @patch("crawler.services.discovery_qualify.fetch_page_for_qualification")
    @override_settings(CRAWLER_GEO_MODE="global", CRAWLER_REQUIRE_ACTIVE_BUYER=True)
    def test_discovery_rejects_kelinkenya_2014_rfp_body(self, mock_fetch):
        mock_fetch.return_value = (
            True,
            (
                "Request for proposal for goods and services RFP # KELIN/FAO/EOI/4/2014. "
                "KELIN/FAO/EOI/4/2014 (u) Provision of translation and sign language interpretation services. "
                "This information should reach KELIN Kenya by 28th February, 2014 by 1500Hrs. "
                "Contact us\nNews\nJune 16, 2026"
            ),
            "",
        )
        from crawler.services.discovery_qualify import filter_discovery_hit

        ok, reason = filter_discovery_hit(
            {
                "domain": "https://www.kelinkenya.org",
                "source_url": "https://www.kelinkenya.org/current-rfp-interpretation",
            }
        )
        self.assertFalse(ok)
        self.assertIn("past", reason.lower())


class CrawlSessionTaskTests(TestCase):
    def test_run_is_stopped_when_past_ends_at(self):
        run = CrawlRun.objects.create(
            trigger=CrawlRunTrigger.SESSION,
            status=CrawlRunStatus.RUNNING,
            ends_at=timezone.now() - timedelta(minutes=1),
            session_mode=True,
        )
        self.assertTrue(_run_is_stopped(run.id))

    def test_run_is_stopped_false_before_deadline(self):
        run = CrawlRun.objects.create(
            trigger=CrawlRunTrigger.SESSION,
            status=CrawlRunStatus.RUNNING,
            ends_at=timezone.now() + timedelta(hours=1),
            session_mode=True,
        )
        self.assertFalse(_run_is_stopped(run.id))

    def test_run_is_stopped_when_cancelled(self):
        run = CrawlRun.objects.create(
            trigger=CrawlRunTrigger.SESSION,
            status=CrawlRunStatus.FAILED,
            ends_at=timezone.now() + timedelta(hours=1),
            session_mode=True,
        )
        self.assertTrue(_run_is_stopped(run.id))


class CrawlSessionProgressTests(TestCase):
    def test_maybe_notify_session_progress_sends_for_long_session(self):
        from unittest.mock import patch

        from django.contrib.auth import get_user_model
        from crawler.tasks import _maybe_notify_session_progress

        user = get_user_model().objects.create_user(username="proguser", password="x")
        run = CrawlRun.objects.create(
            owner=user,
            trigger=CrawlRunTrigger.SESSION,
            status=CrawlRunStatus.RUNNING,
            duration_minutes=720,
            started_at=timezone.now() - timedelta(hours=3),
            ends_at=timezone.now() + timedelta(hours=9),
            session_mode=True,
            cycles_completed=2,
            domains_queued=10,
        )
        with patch("dashboard.utils.notify_crawl_session") as mock_notify:
            _maybe_notify_session_progress(run)
        mock_notify.assert_called_once()
        self.assertEqual(mock_notify.call_args[0][2], "progress")

    def test_maybe_notify_session_progress_skips_short_session(self):
        from unittest.mock import patch

        from crawler.tasks import _maybe_notify_session_progress

        run = CrawlRun.objects.create(
            trigger=CrawlRunTrigger.SESSION,
            status=CrawlRunStatus.RUNNING,
            duration_minutes=60,
            started_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(minutes=30),
            session_mode=True,
        )
        with patch("dashboard.utils.notify_crawl_session") as mock_notify:
            _maybe_notify_session_progress(run)
        mock_notify.assert_not_called()


class CrawlScheduleEnqueueTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(username="scheduser", password="x")

    def test_enqueue_starts_due_schedule(self):
        from unittest.mock import MagicMock, patch

        from crawler.models import CrawlSchedule
        from crawler.tasks import enqueue_due_crawl_schedules

        schedule = CrawlSchedule.objects.create(
            owner=self.user,
            name="Every 12h",
            enabled=True,
            interval_minutes=720,
            session_duration_minutes=60,
        )

        with patch("crawler.services.crawl_session.start_crawl_session_for_user") as mock_start:
            mock_start.return_value = MagicMock(id=99)
            result = enqueue_due_crawl_schedules()

        self.assertEqual(result["started"], 1)
        mock_start.assert_called_once_with(self.user, 60, notify=True)
        schedule.refresh_from_db()
        self.assertIsNotNone(schedule.last_started_at)

    def test_enqueue_skips_when_active_session(self):
        from unittest.mock import patch

        from crawler.models import CrawlSchedule
        from crawler.tasks import enqueue_due_crawl_schedules

        CrawlSchedule.objects.create(
            owner=self.user,
            name="Every 12h",
            enabled=True,
            interval_minutes=720,
        )
        CrawlRun.objects.create(
            owner=self.user,
            trigger=CrawlRunTrigger.SESSION,
            status=CrawlRunStatus.RUNNING,
            ends_at=timezone.now() + timedelta(hours=2),
            duration_minutes=120,
            session_mode=True,
        )

        with patch("crawler.services.crawl_session.start_crawl_session_for_user") as mock_start:
            result = enqueue_due_crawl_schedules()

        self.assertEqual(result["started"], 0)
        self.assertGreaterEqual(result["skipped"], 1)
        mock_start.assert_not_called()

    def test_enqueue_skips_before_interval_elapsed(self):
        from unittest.mock import patch

        from crawler.models import CrawlSchedule
        from crawler.tasks import enqueue_due_crawl_schedules

        CrawlSchedule.objects.create(
            owner=self.user,
            name="Every 12h",
            enabled=True,
            interval_minutes=720,
            last_started_at=timezone.now() - timedelta(minutes=30),
        )

        with patch("crawler.services.crawl_session.start_crawl_session_for_user") as mock_start:
            result = enqueue_due_crawl_schedules()

        self.assertEqual(result["started"], 0)
        mock_start.assert_not_called()

    def test_enqueue_no_double_start_same_tick(self):
        from unittest.mock import MagicMock, patch

        from crawler.models import CrawlSchedule
        from crawler.tasks import enqueue_due_crawl_schedules

        CrawlSchedule.objects.create(
            owner=self.user,
            name="Due now",
            enabled=True,
            interval_minutes=60,
            session_duration_minutes=45,
        )

        with patch("crawler.services.crawl_session.start_crawl_session_for_user") as mock_start:
            mock_start.return_value = MagicMock(id=1)
            enqueue_due_crawl_schedules()
            enqueue_due_crawl_schedules()

        mock_start.assert_called_once()
