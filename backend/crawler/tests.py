from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from crawler.models import (
    AISearchJob,
    AISearchResult,
    CrawlRun,
    CrawlRunDomainResult,
    CrawlRunStatus,
    DiscoveredDomain,
    EventProspect,
    WebsiteProfile,
)
from crawler.crawler import crawl_domain
from crawler.prospect_pipeline import create_or_update_prospect
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

    def test_promote_increments_job_prospects_created(self):
        """
        Regression: AISearchJob.prospects_created was defined and serialized to
        the frontend but never written anywhere — always showed 0 regardless of
        how many results from the job were actually promoted.
        """
        self.assertEqual(self.job.prospects_created, 0)

        promote_ai_search_result_to_prospect(self.result, owner_id=self.user.id)
        self.job.refresh_from_db()
        self.assertEqual(self.job.prospects_created, 1)

        # Promoting the same (already-promoted) result again must not double-count.
        promote_ai_search_result_to_prospect(self.result, owner_id=self.user.id)
        self.job.refresh_from_db()
        self.assertEqual(self.job.prospects_created, 1)

        second_result = AISearchResult.objects.create(
            job=self.job,
            domain="another-org.or.ke",
            org_name="Another Org",
            raw_data={"source_url": "https://another-org.or.ke/tenders"},
        )
        promote_ai_search_result_to_prospect(second_result, owner_id=self.user.id)
        self.job.refresh_from_db()
        self.assertEqual(self.job.prospects_created, 2)

    def test_owner_id_none_does_not_match_another_users_prospect(self):
        """
        Regression: dedup used to be scoped "if owner_id:" (truthy-only), so
        owner_id=None searched/matched across every owner's Prospects instead of
        being scoped to the unowned pool — a scheduled/system-initiated promote
        could silently overwrite a different user's Prospect that happened to
        share an email. Must now match exactly on owner_id, including None.
        """
        other_user_prospect = Prospect.objects.create(
            owner=self.user,
            email="procurement@example-hospital.or.ke",
            company="Someone Else's Record",
        )
        prospect, created = promote_ai_search_result_to_prospect(
            self.result,
            owner_id=None,
        )
        self.assertTrue(created)
        self.assertNotEqual(prospect.id, other_user_prospect.id)
        self.assertIsNone(prospect.owner_id)


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

    def test_contact_email_kept_when_it_appears_in_page_text(self):
        merged = merge_extraction_into_prospect(
            {"domain": "example.or.ke"},
            {"contact_email": "proc@example.or.ke"},
            page_text="Contact our procurement office at proc@example.or.ke for tender details.",
        )
        self.assertEqual(merged["contact_email"], "proc@example.or.ke")

    def test_contact_email_discarded_when_not_present_in_page_text(self):
        """
        Prompt-injection hardening: a model-reported contact_email that doesn't
        actually appear in the source page text is dropped rather than trusted —
        closes the "page instructs the model to fabricate a different email"
        vector (redirecting outreach to an attacker-controlled inbox).
        """
        merged = merge_extraction_into_prospect(
            {"domain": "example.or.ke"},
            {"contact_email": "attacker@evil.example"},
            page_text="This page has no email address anywhere in its content at all.",
        )
        self.assertEqual(merged["contact_email"], "")

    def test_contact_email_kept_when_no_page_text_given(self):
        """Backward-compatible default: without page_text, no verification is
        attempted (existing callers that don't pass it keep prior behavior)."""
        merged = merge_extraction_into_prospect(
            {"domain": "example.or.ke"},
            {"contact_email": "proc@example.or.ke"},
        )
        self.assertEqual(merged["contact_email"], "proc@example.or.ke")

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


class FinalizeCrawlRunTests(TestCase):
    """
    _finalize_crawl_run_if_complete is the fix for the bug where discover_websites_task
    used to mark a CrawlRun SUCCESS immediately after enqueueing crawl_domain_task for
    each domain, before any of them had actually run. Every queued child task then
    treated the non-RUNNING status as "cancelled" (_run_is_cancelled) and self-aborted
    with no crawling ever happening. These tests exercise the replacement completion
    tracking directly, independent of Celery task wiring.
    """

    def _domain(self, n: int) -> DiscoveredDomain:
        return DiscoveredDomain.objects.create(domain=f"finalize-{n}.example.com")

    def test_run_stays_running_until_every_queued_domain_is_terminal(self):
        from crawler.tasks import _finalize_crawl_run_if_complete

        run = CrawlRun.objects.create(status=CrawlRunStatus.RUNNING, domains_queued=2)
        d1, d2 = self._domain(1), self._domain(2)
        CrawlRunDomainResult.objects.create(crawl_run=run, domain=d1, state="queued")
        CrawlRunDomainResult.objects.create(crawl_run=run, domain=d2, state="queued")

        _finalize_crawl_run_if_complete(run.id)
        run.refresh_from_db()
        self.assertEqual(run.status, CrawlRunStatus.RUNNING)
        self.assertIsNone(run.finished_at)

        CrawlRunDomainResult.objects.filter(domain=d1).update(state="scored")
        _finalize_crawl_run_if_complete(run.id)
        run.refresh_from_db()
        self.assertEqual(run.status, CrawlRunStatus.RUNNING, "only 1 of 2 domains done")

        CrawlRunDomainResult.objects.filter(domain=d2).update(state="failed")
        _finalize_crawl_run_if_complete(run.id)
        run.refresh_from_db()
        self.assertEqual(run.status, CrawlRunStatus.SUCCESS)
        self.assertIsNotNone(run.finished_at)

    def test_noop_once_run_is_already_terminal(self):
        from crawler.tasks import _finalize_crawl_run_if_complete

        run = CrawlRun.objects.create(
            status=CrawlRunStatus.FAILED, domains_queued=0, error_text="boom"
        )
        _finalize_crawl_run_if_complete(run.id)
        run.refresh_from_db()
        self.assertEqual(run.status, CrawlRunStatus.FAILED)


class DiscoverWebsitesTaskStatusTests(TestCase):
    """
    Regression tests for the discover_websites_task run-status race itself.

    migrations/0002_seed_sources_and_target.py seeds real, enabled CrawlSource rows
    (with live discovery queries) into every fresh database, including the test DB —
    so discover_websites_task would otherwise make real Serper/HTTP calls out to the
    internet here. Disable them in setUp so these tests only ever see the
    DiscoveredDomain rows each test creates explicitly, and run hermetically.
    """

    def setUp(self):
        from crawler.models import CrawlSource

        CrawlSource.objects.filter(enabled=True).update(enabled=False)

    @patch("crawler.tasks.crawl_domain_task.delay")
    def test_run_stays_running_with_children_not_cancelled(self, mock_delay):
        from crawler.tasks import _run_is_cancelled, discover_websites_task

        DiscoveredDomain.objects.create(domain="alpha.example.com")
        DiscoveredDomain.objects.create(domain="beta.example.com")

        result = discover_websites_task.apply(kwargs={"initiated_by_id": None}).get()
        run = CrawlRun.objects.get(id=result["run_id"])

        # Before the fix, this was CrawlRunStatus.SUCCESS at this exact point — before
        # either crawl_domain_task had run — which made _run_is_cancelled(run.id) return
        # True for every domain about to be processed.
        self.assertEqual(run.status, CrawlRunStatus.RUNNING)
        self.assertIsNone(run.finished_at)
        self.assertEqual(run.domains_queued, 2)
        self.assertEqual(mock_delay.call_count, 2)
        self.assertFalse(_run_is_cancelled(run.id))
        self.assertEqual(
            CrawlRunDomainResult.objects.filter(crawl_run=run, state="queued").count(), 2
        )

    def test_run_finalizes_immediately_when_nothing_is_pending(self):
        from crawler.tasks import discover_websites_task

        result = discover_websites_task.apply(kwargs={"initiated_by_id": None}).get()
        run = CrawlRun.objects.get(id=result["run_id"])
        self.assertEqual(run.status, CrawlRunStatus.SUCCESS)
        self.assertIsNotNone(run.finished_at)


class EventProspectUniqueConstraintTests(TestCase):
    """
    Regression tests for the missing dedup guard on EventProspect: two concurrent
    analyze_domain_task runs for the same domain (nothing prevented this — no
    crawl-in-progress lock beyond the non-atomic DiscoveredDomain.crawl_status
    field) could both pass event_processor.py's update_or_create() lookup and
    create duplicate rows for the same event. A DB-level unique constraint on
    (event_name, organizer_domain) — update_or_create's own key — closes this;
    Django retries update_or_create on IntegrityError when a matching unique
    constraint exists.
    """

    def test_duplicate_event_name_and_organizer_domain_is_rejected_at_db_level(self):
        from django.db import IntegrityError, transaction

        user = User.objects.create_user(username="evtuser1", password="x")
        EventProspect.objects.create(
            owner=user, event_name="Regional Health Summit", organizer_domain="example.org"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EventProspect.objects.create(
                    owner=user, event_name="Regional Health Summit", organizer_domain="example.org"
                )
        self.assertEqual(
            EventProspect.objects.filter(
                event_name="Regional Health Summit", organizer_domain="example.org"
            ).count(),
            1,
        )

    def test_update_or_create_with_same_key_updates_instead_of_duplicating(self):
        user = User.objects.create_user(username="evtuser2", password="x")
        first, created_first = EventProspect.objects.update_or_create(
            event_name="Trade Expo",
            organizer_domain="events.example",
            defaults={"owner": user, "urgency_score": 10},
        )
        self.assertTrue(created_first)

        second, created_second = EventProspect.objects.update_or_create(
            event_name="Trade Expo",
            organizer_domain="events.example",
            defaults={"owner": user, "urgency_score": 20},
        )
        self.assertFalse(created_second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(
            EventProspect.objects.filter(
                event_name="Trade Expo", organizer_domain="events.example"
            ).count(),
            1,
        )
        second.refresh_from_db()
        self.assertEqual(second.urgency_score, 20)


class CreateOrUpdateProspectOwnerScopingTests(TestCase):
    """
    Regression tests for crawler/prospect_pipeline.py's create_or_update_prospect:
    dedup used to be scoped "if owner_id:" (truthy-only), so owner_id=None — the
    value passed for every scheduled crawl run, since discover_websites_task's
    beat schedule calls it with no initiating user — searched/matched across every
    owner's Prospects instead of the unowned pool. A scheduled run's new lead
    could then silently overwrite a different user's existing Prospect.
    """

    def _profile(self, *, domain: str, email: str = "", org_name: str = "Acme") -> WebsiteProfile:
        discovered = DiscoveredDomain.objects.create(domain=domain)
        return WebsiteProfile.objects.create(
            domain=discovered,
            org_name=org_name,
            contact_emails=[email] if email else [],
        )

    def test_owner_id_none_does_not_match_another_users_prospect(self):
        from leads.models import Prospect

        user = User.objects.create_user(username="pp-owner", password="x")
        other_prospect = Prospect.objects.create(
            owner=user, email="shared@example.org", company="Someone Else's Record"
        )
        profile = self._profile(domain="shared-example.org", email="shared@example.org")

        prospect, created = create_or_update_prospect(profile, score=90, owner_id=None)

        self.assertTrue(created)
        self.assertNotEqual(prospect.id, other_prospect.id)
        self.assertIsNone(prospect.owner_id)
        other_prospect.refresh_from_db()
        self.assertEqual(other_prospect.company, "Someone Else's Record")

    def test_same_owner_dedup_still_updates_existing_prospect(self):
        user = User.objects.create_user(username="pp-owner2", password="x")
        profile = self._profile(domain="dedup-example.org", email="dedup@example.org")

        first, created_first = create_or_update_prospect(profile, score=90, owner_id=user.id)
        self.assertTrue(created_first)

        profile.org_name = "Acme Updated"
        second, created_second = create_or_update_prospect(profile, score=91, owner_id=user.id)
        self.assertFalse(created_second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(second.company, "Acme Updated")

    def test_two_unowned_runs_dedup_against_each_other(self):
        """The unowned (owner_id=None) pool should still dedup against itself —
        the fix scopes exactly to owner_id, it doesn't disable dedup for None."""
        profile = self._profile(domain="system-example.org", email="system@example.org")

        first, created_first = create_or_update_prospect(profile, score=90, owner_id=None)
        self.assertTrue(created_first)

        second, created_second = create_or_update_prospect(profile, score=91, owner_id=None)
        self.assertFalse(created_second)
        self.assertEqual(first.id, second.id)


class CrawlDomainFailureAndRetryTests(TestCase):
    """
    Regression tests for two related bugs in crawl_domain_task:
    (1) a single failed page among many used to mark the whole domain "failed"
        (crawl_domain()'s `error` field only ever reflects the *last* fetch
        failure, not overall outcome) — now gated on whether any pages were
        actually collected instead;
    (2) failed domains were never retried — DiscoveredDomain.next_attempt_at was
        defined/indexed but never written — now backed off exponentially and
        picked back up by discover_websites_task once the window passes.

    migrations/0002_seed_sources_and_target.py seeds real, enabled CrawlSource
    rows into every fresh DB including the test DB — disable them so
    discover_websites_task doesn't make live Serper/HTTP calls here (see
    DiscoverWebsitesTaskStatusTests, which hit this the same way).
    """

    def setUp(self):
        from crawler.models import CrawlSource

        CrawlSource.objects.filter(enabled=True).update(enabled=False)

    def _domain(self, **kwargs) -> DiscoveredDomain:
        defaults = {"domain": "retry-test.example.com"}
        defaults.update(kwargs)
        return DiscoveredDomain.objects.create(**defaults)

    def _run(self, domains_queued: int = 1) -> CrawlRun:
        return CrawlRun.objects.create(status=CrawlRunStatus.RUNNING, domains_queued=domains_queued)

    @patch("crawler.tasks.analyze_domain_task.delay")
    @patch("crawler.tasks.crawl_domain")
    def test_partial_page_failure_does_not_mark_domain_failed(self, mock_crawl_domain, mock_analyze_delay):
        mock_crawl_domain.return_value = {
            "pages": [{"url": "https://retry-test.example.com/", "text": "hi", "html": "<html></html>"}],
            "emails": [],
            "phones": [],
            "pages_crawled": 1,
            "error": "timeout fetching https://retry-test.example.com/about",
        }
        domain = self._domain()
        run = self._run()

        from crawler.tasks import crawl_domain_task

        crawl_domain_task.apply(kwargs={"domain_id": domain.id, "run_id": run.id}).get()

        domain.refresh_from_db()
        self.assertEqual(domain.crawl_status, "completed")
        self.assertIsNone(domain.next_attempt_at)
        # Diagnostic text is kept even though the crawl overall succeeded.
        self.assertIn("timeout", domain.error_text)
        result = CrawlRunDomainResult.objects.get(crawl_run=run, domain=domain)
        self.assertTrue(result.crawl_succeeded)

    @patch("crawler.tasks.analyze_domain_task.delay")
    @patch("crawler.tasks.crawl_domain")
    def test_zero_pages_marks_failed_and_schedules_retry(self, mock_crawl_domain, mock_analyze_delay):
        mock_crawl_domain.return_value = {
            "pages": [],
            "emails": [],
            "phones": [],
            "pages_crawled": 0,
            "error": "connection refused",
        }
        domain = self._domain()
        run = self._run()

        from crawler.tasks import crawl_domain_task

        crawl_domain_task.apply(kwargs={"domain_id": domain.id, "run_id": run.id}).get()

        domain.refresh_from_db()
        self.assertEqual(domain.crawl_status, "failed")
        self.assertIsNotNone(domain.next_attempt_at)
        self.assertGreater(domain.next_attempt_at, timezone.now())
        result = CrawlRunDomainResult.objects.get(crawl_run=run, domain=domain)
        self.assertFalse(result.crawl_succeeded)

    def test_next_attempt_backoff_is_exponential_and_capped(self):
        from crawler.tasks import _next_attempt_backoff

        self.assertEqual(_next_attempt_backoff(1), timezone.timedelta(hours=1))
        self.assertEqual(_next_attempt_backoff(2), timezone.timedelta(hours=2))
        self.assertEqual(_next_attempt_backoff(3), timezone.timedelta(hours=4))
        self.assertEqual(_next_attempt_backoff(20), timezone.timedelta(hours=72))

    @patch("crawler.tasks.crawl_domain_task.delay")
    def test_discover_requeues_failed_domain_past_backoff_window(self, mock_delay):
        from crawler.tasks import discover_websites_task

        due = self._domain(
            domain="due-for-retry.example.com",
            crawl_status="failed",
            next_attempt_at=timezone.now() - timezone.timedelta(minutes=5),
        )
        not_due = self._domain(
            domain="not-due-for-retry.example.com",
            crawl_status="failed",
            next_attempt_at=timezone.now() + timezone.timedelta(hours=1),
        )

        result = discover_websites_task.apply(kwargs={"initiated_by_id": None}).get()

        self.assertEqual(result["domains_queued"], 1)
        queued_ids = {c.kwargs["domain_id"] for c in mock_delay.call_args_list}
        self.assertIn(due.id, queued_ids)
        self.assertNotIn(not_due.id, queued_ids)


class CrawlDomainRateLimitConfigTests(TestCase):
    """
    Regression tests: CRAWLER_RATE_LIMIT_SECONDS (and max pages/depth) used to be
    computed into CrawlRun.config but crawl_domain() always built its RateLimiter
    from the hardcoded DEFAULT_DELAY_BETWEEN_REQUESTS_SECONDS constant regardless
    — operators setting the env var to slow down or speed up crawling saw no
    effect. crawl_domain now accepts explicit overrides; crawl_domain_task wires
    them from the live env config.
    """

    def _domain(self) -> DiscoveredDomain:
        return DiscoveredDomain.objects.create(domain="ratelimit-test.example.com")

    @patch("crawler.crawler._discover_seed_urls")
    @patch("crawler.crawler.is_allowed_by_robots", return_value=True)
    @patch("crawler.crawler.fetch_page")
    @patch("crawler.crawler.RateLimiter")
    def test_explicit_rate_limit_seconds_is_used(
        self, mock_limiter_cls, mock_fetch, mock_robots, mock_seed_urls
    ):
        mock_seed_urls.return_value = ["https://ratelimit-test.example.com/"]
        mock_fetch.return_value = ("<html><body>hi</body></html>", "hi")

        crawl_domain(self._domain(), rate_limit_seconds=9.5, max_pages=1, max_depth=0)

        mock_limiter_cls.assert_called_once_with(seconds=9.5)

    @patch("crawler.crawler._discover_seed_urls")
    @patch("crawler.crawler.is_allowed_by_robots", return_value=True)
    @patch("crawler.crawler.fetch_page")
    @patch("crawler.crawler.RateLimiter")
    def test_defaults_to_module_constant_when_not_overridden(
        self, mock_limiter_cls, mock_fetch, mock_robots, mock_seed_urls
    ):
        from crawler.constants import DEFAULT_DELAY_BETWEEN_REQUESTS_SECONDS

        mock_seed_urls.return_value = ["https://ratelimit-test.example.com/"]
        mock_fetch.return_value = ("<html><body>hi</body></html>", "hi")

        crawl_domain(self._domain(), max_pages=1, max_depth=0)

        mock_limiter_cls.assert_called_once_with(seconds=DEFAULT_DELAY_BETWEEN_REQUESTS_SECONDS)

    def test_get_crawler_config_reads_rate_and_page_limits_from_env(self):
        from crawler.tasks import _get_crawler_config

        with patch.dict(
            "os.environ",
            {
                "CRAWLER_RATE_LIMIT_SECONDS": "3.25",
                "CRAWLER_MAX_PAGES_PER_DOMAIN": "10",
                "CRAWLER_MAX_CRAWL_DEPTH": "1",
            },
        ):
            cfg = _get_crawler_config()

        self.assertEqual(cfg["rate_limit_seconds"], 3.25)
        self.assertEqual(cfg["max_pages_per_domain"], 10)
        self.assertEqual(cfg["max_crawl_depth"], 1)


class FetchPageForQualificationThrottleTests(TestCase):
    """
    Regression tests: fetch_page_for_qualification (shared by crawler discovery
    and AI search qualification) previously had no robots.txt check and no rate
    limiting at all, unlike the BFS crawler — a discovery/AI-search run could hit
    target hosts back-to-back with zero politeness control.
    """

    def setUp(self):
        # The rate limiter is a lazily-created module-level singleton; reset it
        # between tests so one test's constructed instance/mock doesn't leak.
        import crawler.services.prospect_verify as pv

        pv._qualification_rate_limiter = None
        self.addCleanup(setattr, pv, "_qualification_rate_limiter", None)

    @patch("crawler.crawler.is_allowed_by_robots", return_value=False)
    def test_disallowed_by_robots_short_circuits_before_fetching(self, mock_robots):
        import httpx

        from crawler.services.prospect_verify import fetch_page_for_qualification

        with patch("httpx.stream") as mock_stream:
            ok, text, reason = fetch_page_for_qualification("https://blocked.example.com/page")

        self.assertFalse(ok)
        self.assertEqual(reason, "Disallowed by robots.txt")
        mock_stream.assert_not_called()

    @patch("crawler.crawler.is_allowed_by_robots", return_value=True)
    def test_allowed_by_robots_waits_on_rate_limiter(self, mock_robots):
        from crawler.services.prospect_verify import (
            _get_qualification_rate_limiter,
            fetch_page_for_qualification,
        )

        limiter = _get_qualification_rate_limiter()
        with patch.object(limiter, "wait") as mock_wait, patch("httpx.stream") as mock_stream:
            mock_stream.side_effect = Exception("stop before real network call")
            fetch_page_for_qualification("https://allowed.example.com/page")

        mock_wait.assert_called_once_with(domain="allowed.example.com")
