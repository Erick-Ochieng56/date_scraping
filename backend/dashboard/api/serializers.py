from __future__ import annotations

from rest_framework import serializers

from crawler.models import (
    AISearchJob,
    AISearchResult,
    CrawlRun,
    CrawlRunDomainResult,
    CrawlSource,
    DiscoveredDomain,
)
from leads.models import Lead, Prospect
from scraper.models import ScrapeRun, ScrapeTarget


class ScrapeTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScrapeTarget
        fields = [
            "id",
            "name",
            "enabled",
            "target_type",
            "start_url",
            "run_every_minutes",
            "config",
            "last_run_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "last_run_at", "created_at", "updated_at")


class ScrapeRunSerializer(serializers.ModelSerializer):
    target_name = serializers.CharField(source="target.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ScrapeRun
        fields = [
            "id",
            "target",
            "target_name",
            "trigger",
            "status",
            "status_display",
            "started_at",
            "finished_at",
            "task_id",
            "error_text",
            "item_count",
            "created_leads",
            "updated_leads",
            "stats",
        ]


class CrawlRunSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = CrawlRun
        fields = [
            "id",
            "trigger",
            "status",
            "status_display",
            "started_at",
            "finished_at",
            "task_id",
            "error_text",
            "domains_queued",
            "prospects_created",
            "prospects_updated",
            "stats",
        ]


class CrawlSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrawlSource
        fields = [
            "id",
            "name",
            "discovery_query",
            "source_type",
            "enabled",
            "priority",
            "created_at",
        ]


class DiscoveredDomainSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source="source.name", read_only=True)

    class Meta:
        model = DiscoveredDomain
        fields = [
            "id",
            "domain",
            "source_url",
            "source",
            "source_name",
            "crawl_status",
            "crawl_attempts",
            "priority",
            "first_seen_at",
            "last_crawled_at",
            "next_attempt_at",
            "error_text",
        ]


class CrawlRunDomainResultSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source="domain.domain", read_only=True)

    class Meta:
        model = CrawlRunDomainResult
        fields = [
            "id",
            "domain",
            "domain_name",
            "state",
            "crawl_succeeded",
            "crawl_error",
            "pages_crawled",
            "score",
            "score_label",
            "prospect_created",
            "prospect_updated",
            "processed_at",
            "updated_at",
            "contact_emails",
            "contact_phones",
            "event_names",
            "org_name",
            "org_type",
        ]


class ProspectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prospect
        fields = [
            "id",
            "event_name",
            "company",
            "email",
            "phone_raw",
            "website",
            "status",
            "source_name",
            "source_url",
            "notes",
            "created_at",
            "updated_at",
            "contacted_at",
            "converted_at",
            "rejected_at",
        ]


class AISearchResultSerializer(serializers.ModelSerializer):
    queued_domain_id = serializers.IntegerField(read_only=True, allow_null=True)
    source_url = serializers.SerializerMethodField()
    promoted_prospect_id = serializers.SerializerMethodField()
    translation_need_score = serializers.SerializerMethodField()
    evidence_snippet = serializers.SerializerMethodField()
    buyer_signal_type = serializers.SerializerMethodField()
    action_date = serializers.SerializerMethodField()
    promotable = serializers.SerializerMethodField()

    def get_source_url(self, obj):
        raw = obj.raw_data if isinstance(obj.raw_data, dict) else {}
        src = (raw.get("source_url") or raw.get("landing_url") or "").strip()
        if src:
            return src
        qd = getattr(obj, "queued_domain", None)
        if qd and getattr(qd, "source_url", ""):
            return qd.source_url
        dom = (obj.domain or "").strip()
        return f"https://{dom}" if dom and "://" not in dom else dom

    def get_promoted_prospect_id(self, obj):
        raw = obj.raw_data if isinstance(obj.raw_data, dict) else {}
        pid = raw.get("promoted_prospect_id")
        try:
            return int(pid) if pid is not None else None
        except (TypeError, ValueError):
            return None

    def get_translation_need_score(self, obj):
        from crawler.services.ai_page_extract import result_translation_need_score

        return result_translation_need_score(obj)

    def get_evidence_snippet(self, obj):
        raw = obj.raw_data if isinstance(obj.raw_data, dict) else {}
        return (raw.get("evidence_snippet") or "")[:2000]

    def get_buyer_signal_type(self, obj):
        raw = obj.raw_data if isinstance(obj.raw_data, dict) else {}
        return (raw.get("buyer_signal_type") or "")[:80]

    def get_action_date(self, obj):
        from crawler.services.ai_page_extract import result_action_date

        return result_action_date(obj)

    def get_promotable(self, obj):
        from crawler.services.ai_page_extract import result_promotable

        return result_promotable(obj)

    class Meta:
        model = AISearchResult
        fields = [
            "id",
            "domain",
            "source_url",
            "org_name",
            "org_type",
            "why_needs_translation",
            "international_signals",
            "contact_email",
            "queued_domain_id",
            "promoted_prospect_id",
            "translation_need_score",
            "evidence_snippet",
            "buyer_signal_type",
            "action_date",
            "promotable",
            "created_at",
        ]


class AISearchJobSerializer(serializers.ModelSerializer):
    owner_id = serializers.IntegerField(read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = AISearchJob
        fields = [
            "id",
            "owner_id",
            "owner_username",
            "seed_topic",
            "industry",
            "region",
            "status",
            "error_text",
            "queries_generated",
            "domains_discovered",
            "prospects_created",
            "qualification_log",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner_id",
            "owner_username",
            "status",
            "error_text",
            "queries_generated",
            "domains_discovered",
            "prospects_created",
            "qualification_log",
            "created_at",
            "updated_at",
        ]


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            "id",
            "prospect_id",
            "full_name",
            "company",
            "email",
            "phone_raw",
            "website",
            "event_name",
            "status",
            "source_name",
            "notes",
            "created_at",
            "updated_at",
            "contacted_at",
            "rejected_at",
        ]

