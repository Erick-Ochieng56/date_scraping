from __future__ import annotations

import os

from rest_framework import serializers
from django.utils import timezone

from crawler.models import (
    AISearchJob,
    AISearchResult,
    CrawlRun,
    CrawlRunDomainResult,
    CrawlRunStatus,
    CrawlRunTrigger,
    CrawlSource,
    DiscoveredDomain,
    EventProspect,
)
from crawler.models import CrawlSchedule
from leads.models import Lead, Prospect
from scraper.models import ScrapeRun, ScrapeSession, ScrapeSessionStatus, ScrapeTarget


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
    time_remaining_seconds = serializers.SerializerMethodField()
    is_session_active = serializers.SerializerMethodField()

    class Meta:
        model = CrawlRun
        fields = [
            "id",
            "trigger",
            "status",
            "status_display",
            "started_at",
            "finished_at",
            "ends_at",
            "duration_minutes",
            "cycles_completed",
            "last_cycle_at",
            "time_remaining_seconds",
            "is_session_active",
            "task_id",
            "error_text",
            "domains_queued",
            "prospects_created",
            "prospects_updated",
            "stats",
        ]

    def get_time_remaining_seconds(self, obj: CrawlRun) -> int | None:
        if not obj.ends_at or obj.status != CrawlRunStatus.RUNNING:
            return None
        remaining = (obj.ends_at - timezone.now()).total_seconds()
        return max(0, int(remaining))

    def get_is_session_active(self, obj: CrawlRun) -> bool:
        if obj.trigger != CrawlRunTrigger.SESSION or obj.status != CrawlRunStatus.RUNNING:
            return False
        if obj.ends_at and timezone.now() >= obj.ends_at:
            return False
        return True


CRAWL_SESSION_PRESET_MINUTES = {
    "30m": 30,
    "1h": 60,
    "3h": 180,
    "6h": 360,
    "12h": 720,
    "24h": 1440,
}


class CrawlSessionStartSerializer(serializers.Serializer):
    duration_minutes = serializers.IntegerField(required=False, min_value=15, max_value=1440)
    preset = serializers.ChoiceField(
        choices=list(CRAWL_SESSION_PRESET_MINUTES.keys()),
        required=False,
    )

    def validate(self, attrs: dict) -> dict:
        preset = attrs.get("preset")
        duration = attrs.get("duration_minutes")
        if preset:
            attrs["duration_minutes"] = CRAWL_SESSION_PRESET_MINUTES[preset]
        elif duration is None:
            raise serializers.ValidationError(
                "Provide duration_minutes or preset."
            )
        min_d = int(os.getenv("CRAWLER_SESSION_MIN_DURATION_MINUTES", "15") or "15")
        max_d = int(os.getenv("CRAWLER_SESSION_MAX_DURATION_MINUTES", "1440") or "1440")
        final = int(attrs["duration_minutes"])
        if final < min_d or final > max_d:
            raise serializers.ValidationError(
                f"duration_minutes must be between {min_d} and {max_d}."
            )
        attrs["duration_minutes"] = final
        return attrs


class ScrapeSessionStartSerializer(serializers.Serializer):
    duration_minutes = serializers.IntegerField(required=False, min_value=15, max_value=1440)
    preset = serializers.ChoiceField(
        choices=list(CRAWL_SESSION_PRESET_MINUTES.keys()),
        required=False,
    )

    def validate(self, attrs: dict) -> dict:
        preset = attrs.get("preset")
        duration = attrs.get("duration_minutes")
        if preset:
            attrs["duration_minutes"] = CRAWL_SESSION_PRESET_MINUTES[preset]
        elif duration is None:
            raise serializers.ValidationError(
                "Provide duration_minutes or preset."
            )
        min_d = int(os.getenv("SCRAPER_SESSION_MIN_DURATION_MINUTES", "15") or "15")
        max_d = int(os.getenv("SCRAPER_SESSION_MAX_DURATION_MINUTES", "1440") or "1440")
        final = int(attrs["duration_minutes"])
        if final < min_d or final > max_d:
            raise serializers.ValidationError(
                f"duration_minutes must be between {min_d} and {max_d}."
            )
        attrs["duration_minutes"] = final
        return attrs


class ScrapeSessionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    time_remaining_seconds = serializers.SerializerMethodField()
    is_session_active = serializers.SerializerMethodField()
    targets_enqueued = serializers.SerializerMethodField()
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = ScrapeSession
        fields = [
            "id",
            "status",
            "status_display",
            "started_at",
            "finished_at",
            "ends_at",
            "duration_minutes",
            "cycles_completed",
            "last_cycle_at",
            "time_remaining_seconds",
            "is_session_active",
            "targets_enqueued",
            "coordinator_task_id",
            "error_text",
            "stats",
            "owner_id",
            "owner_username",
        ]

    def get_time_remaining_seconds(self, obj: ScrapeSession) -> int | None:
        if not obj.ends_at or obj.status != ScrapeSessionStatus.RUNNING:
            return None
        remaining = (obj.ends_at - timezone.now()).total_seconds()
        return max(0, int(remaining))

    def get_is_session_active(self, obj: ScrapeSession) -> bool:
        if obj.status != ScrapeSessionStatus.RUNNING:
            return False
        if obj.ends_at and timezone.now() >= obj.ends_at:
            return False
        return True

    def get_targets_enqueued(self, obj: ScrapeSession) -> int:
        return int((obj.stats or {}).get("targets_enqueued", 0))


class CrawlScheduleSerializer(serializers.ModelSerializer):
    is_due = serializers.SerializerMethodField()
    next_run_at = serializers.SerializerMethodField()
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = CrawlSchedule
        fields = [
            "id",
            "name",
            "enabled",
            "interval_minutes",
            "session_duration_minutes",
            "last_started_at",
            "source_filter",
            "created_at",
            "updated_at",
            "owner_id",
            "owner_username",
            "is_due",
            "next_run_at",
        ]
        read_only_fields = ["id", "last_started_at", "created_at", "updated_at", "owner_id", "owner_username"]

    def get_is_due(self, obj) -> bool:
        if not obj.enabled:
            return False
        if not obj.last_started_at:
            return True
        elapsed = (timezone.now() - obj.last_started_at).total_seconds() / 60
        return elapsed >= int(obj.interval_minutes or 0)

    def get_next_run_at(self, obj):
        if not obj.enabled:
            return None
        if not obj.last_started_at:
            return timezone.now().isoformat()
        from datetime import timedelta as td

        nxt = obj.last_started_at + td(minutes=int(obj.interval_minutes or 0))
        return nxt.isoformat()

    def validate_interval_minutes(self, value: int) -> int:
        min_i = int(os.getenv("CRAWLER_SCHEDULE_MIN_INTERVAL_MINUTES", "60") or "60")
        max_i = int(os.getenv("CRAWLER_SCHEDULE_MAX_INTERVAL_MINUTES", "10080") or "10080")
        if value < min_i or value > max_i:
            raise serializers.ValidationError(
                f"interval_minutes must be between {min_i} and {max_i}."
            )
        return value

    def validate_session_duration_minutes(self, value: int | None) -> int | None:
        if value is None:
            return None
        min_d = int(os.getenv("CRAWLER_SESSION_MIN_DURATION_MINUTES", "15") or "15")
        max_d = int(os.getenv("CRAWLER_SESSION_MAX_DURATION_MINUTES", "1440") or "1440")
        if value < min_d or value > max_d:
            raise serializers.ValidationError(
                f"session_duration_minutes must be between {min_d} and {max_d}."
            )
        return value

    def validate_source_filter(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("source_filter must be a JSON object.")
        return value


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
    prospect_id = serializers.SerializerMethodField()

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
            "prospect_id",
            "processed_at",
            "updated_at",
            "contact_emails",
            "contact_phones",
            "event_names",
            "org_name",
            "org_type",
        ]

    def get_prospect_id(self, obj):
        if not obj.prospect_created and not obj.prospect_updated:
            return None
        from crawler.utils import normalize_domain_url
        from leads.models import Prospect

        domain_name = getattr(obj.domain, "domain", "") or ""
        website = normalize_domain_url(domain_name)
        if not website:
            return None
        qs = Prospect.objects.filter(website=website)
        owner_id = None
        if obj.crawl_run_id and getattr(obj, "crawl_run", None):
            owner_id = obj.crawl_run.owner_id
        if owner_id:
            qs = qs.filter(owner_id=owner_id)
        prospect = qs.order_by("-updated_at").first()
        return prospect.id if prospect else None


class EventProspectSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventProspect
        fields = [
            "id",
            "event_name",
            "event_type",
            "organizer_name",
            "organizer_domain",
            "event_url",
            "event_date",
            "event_date_raw",
            "event_location",
            "is_virtual",
            "is_hybrid",
            "languages_involved",
            "countries_involved",
            "translation_services_needed",
            "translation_need_score",
            "urgency_score",
            "contact_name",
            "contact_email",
            "contact_phone",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]


class ProspectWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prospect
        fields = [
            "event_name",
            "company",
            "email",
            "phone_raw",
            "website",
            "source_name",
            "source_url",
            "notes",
            "status",
        ]


class LeadWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            "full_name",
            "company",
            "email",
            "phone_raw",
            "website",
            "position",
            "event_name",
            "address",
            "city",
            "state",
            "country_code",
            "notes",
            "status",
            "lead_value",
        ]


class ProspectSerializer(serializers.ModelSerializer):
    translation_need_score = serializers.SerializerMethodField()
    score_label = serializers.SerializerMethodField()
    score_reasoning = serializers.SerializerMethodField()

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
            "translation_need_score",
            "score_label",
            "score_reasoning",
            "created_at",
            "updated_at",
            "contacted_at",
            "converted_at",
            "rejected_at",
        ]

    def get_translation_need_score(self, obj):
        from dashboard.api.prospect_quality import prospect_translation_need_score

        return prospect_translation_need_score(obj)

    def get_score_label(self, obj):
        from dashboard.api.prospect_quality import prospect_score_label

        return prospect_score_label(obj)

    def get_score_reasoning(self, obj):
        from dashboard.api.prospect_quality import prospect_score_reasoning

        return prospect_score_reasoning(obj)


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
            "lead_value",
            "created_at",
            "updated_at",
            "contacted_at",
            "rejected_at",
        ]

