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
    is_procurement_portal_listing_url,
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
    serper_geo_payload,
    text_mentions_east_africa,
)
from crawler.services.service_scope import classify_service_scope, requires_strict_geo
from crawler.services.promote_ai_result import promote_ai_search_result_to_prospect
from crawler.services.ai_page_extract import (
    ai_search_min_score,
    ai_search_promote_min_score,
    merge_extraction_into_prospect,
    qualify_ai_search_candidate,
    result_promotable,
    result_translation_need_score,
)
from crawler.services.company_discovery import (
    _government_site_fragment,
    company_first_query_templates,
    general_prospect_query_templates,
)
from crawler.services.prospect_verify import (
    looks_like_past_event_text,
    page_supports_prospect,
)
from leads.models import Prospect

User = get_user_model()


class GeminiThrottleTests(TestCase):
    """
    Regression tests for the Gemini call-pacing fix: generate_text() used to fire
    every call (query generation, grounded search, page extraction, competitor-signal
    derivation) with zero pacing, exhausting the per-minute request quota within the
    first few candidates of a job and forcing everything after onto the weaker
    rules-only fallback — even with a billed API key, since paid tiers still have a
    (higher, but finite) per-minute limit.
    """

    def setUp(self):
        from crawler.services import gemini_client

        self.gemini_client = gemini_client
        gemini_client._last_call_at = 0.0

    @override_settings(GEMINI_MIN_SECONDS_BETWEEN_CALLS=5.0)
    def test_first_call_does_not_wait(self):
        with patch.object(self.gemini_client.time, "sleep") as mock_sleep:
            self.gemini_client._throttle_gemini_call()
        mock_sleep.assert_not_called()

    @override_settings(GEMINI_MIN_SECONDS_BETWEEN_CALLS=5.0)
    def test_second_call_waits_remaining_interval(self):
        self.gemini_client._throttle_gemini_call()
        with patch.object(self.gemini_client.time, "sleep") as mock_sleep:
            self.gemini_client._throttle_gemini_call()
        mock_sleep.assert_called_once()
        waited = mock_sleep.call_args[0][0]
        self.assertGreater(waited, 0)
        self.assertLessEqual(waited, 5.0)

    @override_settings(GEMINI_MIN_SECONDS_BETWEEN_CALLS=0)
    def test_throttle_disabled_when_interval_is_zero(self):
        self.gemini_client._throttle_gemini_call()
        with patch.object(self.gemini_client.time, "sleep") as mock_sleep:
            self.gemini_client._throttle_gemini_call()
        mock_sleep.assert_not_called()


class GeminiModelSplitTests(TestCase):
    """
    Regression tests locking in the cost-driven model split: mechanical/templated
    calls (search query generation, competitor-signal derivation) use the cheaper
    GEMINI_LITE_MODEL; judgment-critical calls (page extraction/date parsing, where a
    wrong answer becomes a bad prospect or a stale lead) stay on GEMINI_ANALYSIS_MODEL.
    """

    @patch("crawler.services.ai_search.generate_text")
    @override_settings(GEMINI_LITE_MODEL="test-lite-model", GEMINI_ANALYSIS_MODEL="test-flash-model")
    def test_generate_search_queries_uses_lite_model(self, mock_generate):
        from crawler.services.ai_search import generate_search_queries

        mock_generate.return_value = "[]"
        generate_search_queries(seed_topic="translation conference", region="Kenya")

        mock_generate.assert_called()
        self.assertEqual(mock_generate.call_args.kwargs.get("model"), "test-lite-model")

    @patch("crawler.services.competitor_deriver.generate_text")
    @override_settings(GEMINI_LITE_MODEL="test-lite-model", GEMINI_ANALYSIS_MODEL="test-flash-model")
    def test_derive_competitor_signals_uses_lite_model(self, mock_generate):
        from crawler.services.competitor_deriver import derive_competitor_signals

        mock_generate.return_value = (
            '{"competitor_keywords": [], "competitor_org_types": [], '
            '"prospect_org_types": [], "prospect_signals": [], "reasoning": ""}'
        )
        derive_competitor_signals("interpretation tender Kenya")

        mock_generate.assert_called()
        self.assertEqual(mock_generate.call_args.kwargs.get("model"), "test-lite-model")

    @patch("crawler.services.ai_page_extract.generate_text")
    @override_settings(GEMINI_LITE_MODEL="test-lite-model", GEMINI_ANALYSIS_MODEL="test-flash-model")
    def test_page_extraction_stays_on_analysis_model(self, mock_generate):
        from crawler.services.ai_page_extract import extract_prospect_from_page

        mock_generate.return_value = "{}"
        extract_prospect_from_page(
            "example.org", "https://example.org/tender", "some page text", seed_topic="x"
        )

        mock_generate.assert_called()
        self.assertEqual(mock_generate.call_args.kwargs.get("model"), "test-flash-model")


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

    def test_flags_interpretation_equipment_rental_seller(self):
        """
        Regression test for a real false negative: seamevents.com's
        /interpretation-equipment-rental page is a fellow LSP renting interpretation
        equipment (one of Ateric's own service lines), not a client — but it never
        mentions "translator"/"LSP"/"language service provider" anywhere, so the
        staffing-agency-focused keyword checks above never flagged it.
        """
        text = (
            "SEAM Events provides interpretation equipment rental for conferences and "
            "summits across the region, including receivers, headsets, and booths "
            "for simultaneous interpretation."
        )
        flagged, reason = is_likely_competitor(
            "seamevents.com",
            [text],
            landing_url="https://seamevents.com/interpretation-equipment-rental",
        )
        self.assertTrue(flagged, reason)
        self.assertIn("equipment rental", reason.lower())

    def test_allows_buyer_page_needing_equipment_rental(self):
        """A genuine buyer's tender for equipment rental services must not itself be
        misflagged as a competitor just because it mentions "equipment rental"."""
        text = (
            "Request for proposals: we require interpretation equipment rental services "
            "for our annual regional conference. Closing date 15 October 2026."
        )
        flagged, _ = is_likely_competitor(
            "health-ministry.go.ke",
            [text],
            landing_url="https://health-ministry.go.ke/tenders/equipment-rental-rfp",
        )
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

    @override_settings(CRAWLER_GEO_MODE="east_africa")
    def test_passes_geo_gate_allows_virtual_service_outside_east_africa(self):
        """
        Regression test for D2 (DISCOVERY_QUALITY_ANALYSIS.md): location-agnostic
        services (document translation, localization, etc.) must not be rejected just
        because the candidate is outside East Africa — only physical-presence needs
        (simultaneous/conference interpretation, equipment) stay geo-gated.
        """
        ok, reason = passes_geo_gate(
            "We provide certified document translation services for clients "
            "in London, United Kingdom and across Europe.",
            domain="example.co.uk",
        )
        self.assertTrue(ok, reason)

    @override_settings(CRAWLER_GEO_MODE="east_africa")
    def test_passes_geo_gate_still_rejects_physical_service_outside_east_africa(self):
        ok, reason = passes_geo_gate(
            "We need simultaneous interpretation and conference equipment for our "
            "annual meeting in London, United Kingdom.",
            domain="example.co.uk",
        )
        self.assertFalse(ok)
        self.assertIn("outside", reason.lower())

    @override_settings(CRAWLER_GEO_MODE="east_africa")
    def test_ensure_query_has_geo_skips_prepend_for_virtual_query(self):
        q = ensure_query_has_geo("document translation localization services", "")
        self.assertNotIn("Kenya", q)

    @override_settings(CRAWLER_GEO_MODE="east_africa")
    def test_serper_geo_payload_skips_bias_for_virtual_query(self):
        self.assertEqual(serper_geo_payload(query="document translation localization services"), {})
        self.assertNotEqual(serper_geo_payload(query="simultaneous interpretation booking"), {})


class ServiceScopeTests(TestCase):
    def test_classifies_physical_presence_terms(self):
        self.assertEqual(
            classify_service_scope("We need simultaneous interpretation for our summit"),
            "physical",
        )

    def test_classifies_virtual_terms(self):
        self.assertEqual(
            classify_service_scope("We need document translation and localization"),
            "virtual",
        )

    def test_virtual_interpretation_overrides_bare_interpretation_word(self):
        """'virtual interpretation' must classify as virtual despite containing the
        generic word 'interpretation', which alone would lean physical."""
        self.assertEqual(classify_service_scope("We need virtual interpretation support"), "virtual")

    def test_no_signal_is_unknown(self):
        self.assertEqual(classify_service_scope("Welcome to our company website"), "unknown")

    def test_requires_strict_geo_only_lifted_for_virtual(self):
        self.assertTrue(requires_strict_geo("physical"))
        self.assertTrue(requires_strict_geo("unknown"))
        self.assertFalse(requires_strict_geo("virtual"))


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
    def test_qualify_rejects_org_homepage_with_no_active_opportunity(self):
        """
        Since F1's fix (DISCOVERY_QUALITY_ANALYSIS.md), a homepage showing genuine
        LSP-relevant signals (multilingual/international, as here) is no longer
        rejected outright as a "generic hub" — it's now rejected by the (separate,
        still-active) active-buyer gate because it has no tender/RFP/hiring signal,
        which is the correct, more specific reason under strict active-buyer mode.
        """
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
        self.assertIn("no active tender", reason.lower())

    @override_settings(CRAWLER_GEO_MODE="global")
    def test_qualify_accepts_general_fit_homepage_when_active_buyer_not_required(self):
        """
        Regression test for D1 (general-prospect mode, the new default): the same kind
        of institutional homepage rejected in strict active-buyer mode above should now
        pass qualification when require_active_buyer=False is explicitly requested —
        it's a genuine org-type + international-signal fit, just with no live tender.
        """
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
            seed_topic="East Africa regional organizations",
            page_text=page,
            allow_gemini=False,
            require_active_buyer=False,
        )
        self.assertTrue(ok, reason)

    @override_settings(CRAWLER_GEO_MODE="global")
    def test_qualify_rejects_unrelated_grant_in_general_mode_without_gemini(self):
        """
        Regression test for a real production false positive: pfizer.com's
        competitive-grants page (about hospital equipment, unrelated to language
        services) reached the results table with no score at all ("Not scored") in
        general-prospect mode once Gemini quota was exhausted for that candidate.
        CRAWLER_GEO_MODE=global isolates this from the (separate, already-passing)
        geo gate so it exercises only the language-relevance floor being tested here.

        Root cause: when not extracted, the score check is skipped (gated on
        `extracted`) and the active-buyer language check is skipped too (gated on
        `rab`, which is False in general mode) — nothing required any language-service
        connection. qualify_ai_search_candidate must reject this regardless of mode.
        """
        page = (
            "Pfizer Competitive Grants Program: request for proposals for hospital "
            "equipment upgrades supporting patient care. Closing date: 30 September 2026. "
            "Submit your grant proposal describing the medical equipment needed."
        )
        ok, reason, enriched = qualify_ai_search_candidate(
            {
                "domain": "pfizer.com",
                "source_url": "https://www.pfizer.com/about/programs-policies/grants/competitive-grants",
                "org_type": "hospital",
                "why_needs_translation": "Healthcare translation procurement",
            },
            seed_topic="hospital patient information translation",
            page_text=page,
            allow_gemini=False,
            require_active_buyer=False,
        )
        self.assertFalse(ok, reason)
        self.assertIsNone(enriched.get("translation_need_score"))

    def test_result_promotable_respects_score(self):
        user = User.objects.create_user(username="scoreuser", password="x")
        job = AISearchJob.objects.create(
            owner=user, seed_topic="test", status="done", require_active_buyer=True
        )
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

    def test_result_promotable_uses_general_mode_threshold_by_default(self):
        """
        Regression test for D1's mode-aware thresholds: a job that doesn't require an
        active buyer (the new default) is judged against AI_SEARCH_GENERAL_PROMOTE_MIN_SCORE,
        not AI_SEARCH_PROMOTE_MIN_SCORE (the narrow active-buyer threshold).
        """
        user = User.objects.create_user(username="scoreuser2", password="x")
        job = AISearchJob.objects.create(
            owner=user, seed_topic="test", status="done", require_active_buyer=False
        )
        mid = AISearchResult.objects.create(
            job=job, domain="mid.example", raw_data={"translation_need_score": 55}
        )
        with self.settings(AI_SEARCH_PROMOTE_MIN_SCORE=80, AI_SEARCH_GENERAL_PROMOTE_MIN_SCORE=50):
            # Would fail the strict active-buyer threshold (80) but passes the general one (50).
            self.assertTrue(result_promotable(mid))


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

    def test_has_active_buyer_signal_rejects_unrelated_grant_tender(self):
        """
        Regression test: a real false positive (pfizer.com's competitive-grants page)
        had generic procurement language ("request for proposals", "closing date")
        about HOSPITAL EQUIPMENT, with no connection to translation/interpretation at
        all. is_buyer_procurement_context alone can't tell subject matter apart from
        any other grant/tender — has_active_buyer_signal must also require a language-
        service signal on the page.
        """
        page = (
            "Pfizer Competitive Grants Program: request for proposals for hospital "
            "equipment upgrades supporting patient care. Closing date: 30 September 2026. "
            "Submit your grant proposal describing the medical equipment needed."
        )
        ok, reason = has_active_buyer_signal(
            page,
            url="https://www.pfizer.com/about/programs-policies/grants/competitive-grants",
        )
        self.assertFalse(ok)
        self.assertIn("not about translation", reason.lower())

    def test_passes_active_buyer_gate_rejects_unrelated_grant_even_with_flags_set(self):
        """
        Even when upstream flags (has_active_procurement=True, buyer_signal_type="tender")
        claim an active opportunity, passes_active_buyer_gate must still require the
        opportunity be about language services before accepting it.
        """
        page = (
            "Pfizer Competitive Grants Program: request for proposals for hospital "
            "equipment upgrades supporting patient care. Closing date: 30 September 2026."
        )
        ok, reason = passes_active_buyer_gate(
            page,
            url="https://www.pfizer.com/about/programs-policies/grants/competitive-grants",
            domain="pfizer.com",
            has_active_procurement=True,
            buyer_signal_type="tender",
            today=date(2026, 6, 19),
        )
        self.assertFalse(ok, reason)

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

    def test_homepage_with_no_lsp_signal_is_still_rejected(self):
        """
        Regression guard for F1's fix: a homepage with genuinely no LSP-relevant
        content (no org type, service, or international signal) should still be
        treated as a generic hub, same as before the fix.
        """
        page = "Welcome to our site. Click here to browse our product catalog and shop now."
        self.assertTrue(is_generic_hub_page("https://widgets-shop.example.com/", page))

    def test_homepage_with_lsp_signal_is_no_longer_blanket_rejected(self):
        """
        Regression test for DISCOVERY_QUALITY_ANALYSIS.md F1: is_org_homepage_or_careers_hub
        used to reject EVERY root-URL hit unconditionally, regardless of content — discarding
        most organic search hits for organizational queries (NGO/university/hospital homepages
        overwhelmingly land on the domain root). A homepage whose own text shows a genuine
        LSP-relevant signal must now pass through to scoring instead of being dropped here.
        """
        page = (
            "We are an international humanitarian NGO working across 40 countries. "
            "Our multilingual teams provide translation and interpretation support "
            "for global health programmes."
        )
        self.assertFalse(is_generic_hub_page("https://global-health-ngo.example.org/", page))

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


class ModeAwareThresholdAndTemplateTests(TestCase):
    """
    Regression tests for D1 (DISCOVERY_QUALITY_ANALYSIS.md): active-buyer mode and
    general-prospect mode (the new default) must use distinct, independently
    configurable score thresholds and query template sets.
    """

    def test_min_score_functions_differ_by_mode(self):
        with self.settings(AI_SEARCH_MIN_SCORE=80, AI_SEARCH_GENERAL_MIN_SCORE=50):
            self.assertEqual(ai_search_min_score(True), 80)
            self.assertEqual(ai_search_min_score(False), 50)

    def test_promote_min_score_functions_differ_by_mode(self):
        with self.settings(AI_SEARCH_PROMOTE_MIN_SCORE=80, AI_SEARCH_GENERAL_PROMOTE_MIN_SCORE=50):
            self.assertEqual(ai_search_promote_min_score(True), 80)
            self.assertEqual(ai_search_promote_min_score(False), 50)

    def test_general_prospect_templates_do_not_require_tender_language(self):
        """
        company_first_query_templates (active-buyer mode) is entirely tender/RFP-hunting.
        general_prospect_query_templates must offer a wide variety of industries without
        forcing tender/RFP phrasing into every query.
        """
        templates = general_prospect_query_templates(region="East Africa", seed="")
        prospect_types = {t["expected_prospect_type"] for t in templates}
        self.assertGreaterEqual(
            len(prospect_types),
            8,
            "expected a wide variety of industries, not just NGOs",
        )
        self.assertIn("law_firm", prospect_types)
        self.assertIn("hospital", prospect_types)
        self.assertIn("diplomatic", prospect_types)
        self.assertIn("financial", prospect_types)
        # None of the general templates should hard-require a tender/RFP phrase —
        # that would defeat the purpose of general (no-active-opportunity) prospecting.
        for t in templates:
            self.assertNotIn("request for proposal", t["query"].lower())
            self.assertNotIn("inurl:tender", t["query"].lower())

    def test_active_buyer_templates_are_still_tender_oriented(self):
        """Sanity check that the pre-existing active-buyer templates are untouched."""
        templates = company_first_query_templates(region="East Africa", seed="")
        queries_text = " ".join(t["query"].lower() for t in templates)
        self.assertIn("tender", queries_text)

    def test_government_site_fragment_matches_selected_region_not_only_kenya(self):
        """
        Regression test for F6: the government-tender template used to hardcode
        site:.go.ke regardless of the selected region. It must now resolve to the
        requested country's own government TLD.
        """
        self.assertEqual(_government_site_fragment("Uganda"), "site:.go.ug")
        self.assertEqual(_government_site_fragment("Kenya"), "site:.go.ke")
        self.assertEqual(_government_site_fragment("Rwanda"), "site:.gov.rw")
        # No specific country mentioned -> falls back to all East Africa gov TLDs.
        fallback = _government_site_fragment("East Africa")
        self.assertIn("site:.go.ke", fallback)
        self.assertIn("site:.go.ug", fallback)

    def test_company_first_templates_use_region_specific_government_site(self):
        templates = company_first_query_templates(region="Uganda", seed="")
        gov_template = next(t for t in templates if t["expected_prospect_type"] == "government" and "site:" in t["query"])
        self.assertIn("site:.go.ug", gov_template["query"])
        self.assertNotIn("site:.go.ke", gov_template["query"])

    def test_company_first_templates_target_tender_procurement_and_event_paths(self):
        """
        User-requested path targeting: search queries should aim at /tender(s) and
        /procurement(s) pages (where live opportunities actually live) and at
        /event(s) pages (where interpretation/translation needs for a specific
        event are often announced).
        """
        templates = company_first_query_templates(region="Kenya", seed="")
        queries_text = " ".join(t["query"] for t in templates)
        self.assertIn("inurl:tender", queries_text)
        self.assertIn("inurl:tenders", queries_text)
        self.assertIn("inurl:procurement", queries_text)
        self.assertIn("inurl:procurements", queries_text)
        self.assertIn("inurl:event", queries_text)
        self.assertIn("inurl:events", queries_text)


class PriorityPathAndProcurementUrlTests(TestCase):
    """
    Regression tests for user-requested path targeting: /tender(s), /procurement(s),
    and /event(s) pages should be prioritized during crawling and recognized as
    procurement-portal-style URLs, matching both singular and plural forms.
    """

    def test_priority_paths_include_tender_procurement_and_event_variants(self):
        from crawler.constants import PRIORITY_PATHS

        for path in ("/tender", "/tenders", "/procurement", "/procurements", "/event", "/events"):
            self.assertIn(path, PRIORITY_PATHS)

    def test_procurement_portal_listing_recognizes_singular_and_plural(self):
        self.assertTrue(is_procurement_portal_listing_url("https://example.org/tender"))
        self.assertTrue(is_procurement_portal_listing_url("https://example.org/tenders"))
        self.assertTrue(is_procurement_portal_listing_url("https://example.org/procurement"))
        self.assertTrue(is_procurement_portal_listing_url("https://example.org/procurements"))

    def test_procurement_portal_listing_still_rejects_single_tender_detail_pages(self):
        """A single tender's own detail page is not a listing page — unchanged behavior."""
        self.assertFalse(
            is_procurement_portal_listing_url("https://example.org/tenders/interpretation-2026")
        )


class AutoDeriveCompetitorSignalsTests(TestCase):
    """
    Regression test for F9 (DISCOVERY_QUALITY_ANALYSIS.md): derive_competitor_signals()
    computes prospect_org_types/prospect_signals (what a good prospect looks like for
    this query) alongside competitor_keywords/competitor_org_types, but the post_save
    signal only ever persisted the competitor half — the prospect half was silently
    discarded on every new CrawlSource.
    """

    @patch("crawler.services.competitor_deriver.derive_competitor_signals")
    @override_settings(GEMINI_API_KEY="test-key", CRAWLER_AUTO_DERIVE_COMPETITOR_SIGNALS=True)
    def test_prospect_signals_are_persisted_alongside_competitor_signals(self, mock_derive):
        from crawler.models import CrawlSource

        mock_derive.return_value = {
            "competitor_keywords": ["translation agency"],
            "competitor_org_types": ["lsp"],
            "prospect_org_types": ["law_firm", "hospital"],
            "prospect_signals": ["multilingual patient information"],
            "reasoning": "test",
        }
        source = CrawlSource.objects.create(
            name="Test source",
            discovery_query="hospital multilingual patient information",
            source_type="search",
        )
        source.refresh_from_db()
        self.assertEqual(source.competitor_org_types, ["lsp"])
        self.assertEqual(source.prospect_org_types, ["law_firm", "hospital"])
        self.assertEqual(source.prospect_signals, ["multilingual patient information"])


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


class CreateOrUpdateProspectAiSearchGuardTests(TestCase):
    """
    Regression test for DISCOVERY_QUALITY_ANALYSIS.md finding F4: create_or_update_prospect
    used to unconditionally overwrite source_name/raw_payload on any matching existing
    Prospect, including one already created via AI Search promotion — silently stripping
    its reviewed evidence (why_needs_translation/evidence_snippet) the moment a much
    weaker web-crawler-derived profile happened to match it by email/website/payload hash.
    """

    def test_does_not_overwrite_existing_ai_search_prospect(self):
        user = User.objects.create_user(username="pp-aisearch", password="x")
        ai_prospect = Prospect.objects.create(
            owner=user,
            source_name="ai_search",
            email="buyer@example.org",
            website="https://example.org",
            company="Original AI Search Find",
            event_name="Live tender: conference interpretation",
            raw_payload={"why_needs_translation": "Live RFP for simultaneous interpretation"},
        )
        discovered = DiscoveredDomain.objects.create(domain="example.org")
        profile = WebsiteProfile.objects.create(
            domain=discovered,
            org_name="Generic Rescore",
            contact_emails=["buyer@example.org"],
        )

        prospect, created = create_or_update_prospect(profile, score=91, owner_id=user.id)

        self.assertFalse(created)
        self.assertEqual(prospect.id, ai_prospect.id)
        prospect.refresh_from_db()
        self.assertEqual(prospect.source_name, "ai_search")
        self.assertEqual(prospect.company, "Original AI Search Find")
        self.assertEqual(
            prospect.raw_payload.get("why_needs_translation"),
            "Live RFP for simultaneous interpretation",
        )

    def test_still_backfills_missing_contact_fields_on_ai_search_prospect(self):
        user = User.objects.create_user(username="pp-aisearch2", password="x")
        ai_prospect = Prospect.objects.create(
            owner=user,
            source_name="ai_search",
            website="https://backfill.example.org",
            company="AI Search Find",
        )
        discovered = DiscoveredDomain.objects.create(domain="backfill.example.org")
        profile = WebsiteProfile.objects.create(
            domain=discovered,
            org_name="Generic Rescore",
            contact_phones=["+254700000000"],
        )

        prospect, created = create_or_update_prospect(profile, score=91, owner_id=user.id)

        self.assertFalse(created)
        self.assertEqual(prospect.id, ai_prospect.id)
        prospect.refresh_from_db()
        self.assertEqual(prospect.source_name, "ai_search")
        self.assertEqual(prospect.phone_e164, "+254700000000")


class ScoreAndCreateProspectSkipsAiSearchDomainsTests(TestCase):
    """
    Regression tests for DISCOVERY_QUALITY_ANALYSIS.md finding F4: score_and_create_prospect_task
    used to auto-create a Prospect for ANY domain scoring above threshold via the generic
    crawler rubric — including domains AI Search had already discovered and evidence-reviewed —
    producing an unowned, evidence-stripped duplicate. The general crawl still refreshes
    WebsiteProfile/CrawlRunDomainResult for these domains (D3 option b); only the
    auto-promote-to-Prospect step is skipped.
    """

    def _profile(self, domain_name: str, score: int = 90) -> WebsiteProfile:
        discovered = DiscoveredDomain.objects.create(domain=domain_name)
        return WebsiteProfile.objects.create(
            domain=discovered,
            org_name="Acme Org",
            gemini_translation_need_score=score,
        )

    def test_skips_auto_create_when_domain_has_ai_search_result(self):
        from crawler.tasks import score_and_create_prospect_task

        profile = self._profile("ai-touched.example.org")
        job = AISearchJob.objects.create(
            owner=User.objects.create_user(username="aiuser", password="x"),
            seed_topic="translation buyers",
        )
        AISearchResult.objects.create(
            job=job, domain=profile.domain.domain, queued_domain=profile.domain
        )
        run = CrawlRun.objects.create(status=CrawlRunStatus.RUNNING, domains_queued=1)

        result = score_and_create_prospect_task.apply(
            kwargs={"domain_id": profile.domain.id, "run_id": run.id, "owner_id": None}
        ).get()

        self.assertFalse(result["created"])
        self.assertEqual(Prospect.objects.count(), 0)

    def test_still_auto_creates_for_domains_without_ai_search_result(self):
        from crawler.tasks import score_and_create_prospect_task

        profile = self._profile("never-touched.example.org")
        run = CrawlRun.objects.create(status=CrawlRunStatus.RUNNING, domains_queued=1)

        result = score_and_create_prospect_task.apply(
            kwargs={"domain_id": profile.domain.id, "run_id": run.id, "owner_id": None}
        ).get()

        self.assertTrue(result["created"])
        self.assertEqual(Prospect.objects.filter(source_name="web_crawler").count(), 1)


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

    @patch("crawler.crawler.extract_internal_links")
    @patch("crawler.crawler._discover_seed_urls")
    @patch("crawler.crawler.is_allowed_by_robots", return_value=True)
    @patch("crawler.crawler.fetch_page")
    def test_priority_paths_are_crawled_before_other_discovered_links(
        self, mock_fetch, mock_robots, mock_seed_urls, mock_links
    ):
        """
        Regression test for F9 (DISCOVERY_QUALITY_ANALYSIS.md): PRIORITY_PATHS was
        defined but never referenced anywhere in the BFS, so within a limited
        max_pages budget a large site could exhaust the budget on low-signal pages
        before ever reaching a high-signal page like /services. Priority-path links
        must now be explored before other discovered links.
        """
        mock_seed_urls.return_value = ["https://priority-test.example.com/"]
        mock_fetch.return_value = ("<html><body>hi</body></html>", "hi")
        mock_links.return_value = [
            "https://priority-test.example.com/random-page-a",
            "https://priority-test.example.com/random-page-b",
            "https://priority-test.example.com/services",
        ]

        result = crawl_domain(self._domain(), max_pages=2, max_depth=1)

        urls_crawled = [p["url"] for p in result["pages"]]
        self.assertEqual(urls_crawled[0], "https://priority-test.example.com/")
        self.assertEqual(urls_crawled[1], "https://priority-test.example.com/services")

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
