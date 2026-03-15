from __future__ import annotations

import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from crawler.models import CrawlSource, DiscoveredDomain, WebsiteProfile
from crawler.models import (
    CrawlRun,
    CrawlRunStatus,
    CrawlRunTrigger,
    CrawlSource,
    DiscoveredDomain,
)
from dashboard.forms import CrawlSourceForm, LeadCreateForm, ProspectCreateForm, TargetEditForm
from dashboard.models import ActivityLog
from dashboard.utils import log_activity
from leads.models import Lead, LeadStatus, Prospect, ProspectStatus
from scraper.models import ScrapeRun, ScrapeRunStatus, ScrapeTarget


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    """Main dashboard home page with real-time stats."""

    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Prospect stats
        prospect_total = Prospect.objects.count()
        prospect_new = Prospect.objects.filter(status=ProspectStatus.NEW).count()
        prospect_contacted = Prospect.objects.filter(
            status=ProspectStatus.CONTACTED
        ).count()
        prospect_converted = Prospect.objects.filter(
            status=ProspectStatus.CONVERTED
        ).count()
        prospect_rejected = Prospect.objects.filter(
            status=ProspectStatus.REJECTED
        ).count()

        # Lead stats
        lead_total = Lead.objects.count()
        lead_contacted = Lead.objects.filter(status=LeadStatus.CONTACTED).count()
        lead_interested = Lead.objects.filter(status=LeadStatus.INTERESTED).count()
        lead_synced = Lead.objects.filter(status=LeadStatus.SYNCED).count()
        lead_rejected = Lead.objects.filter(status=LeadStatus.REJECTED).count()

        # Target stats
        target_total = ScrapeTarget.objects.count()
        target_enabled = ScrapeTarget.objects.filter(enabled=True).count()
        target_disabled = ScrapeTarget.objects.filter(enabled=False).count()

        # Recent runs (last 24 hours) — scraper
        last_24h = timezone.now() - timedelta(hours=24)
        runs_24h = ScrapeRun.objects.filter(started_at__gte=last_24h).count()
        runs_success_24h = ScrapeRun.objects.filter(
            started_at__gte=last_24h, status=ScrapeRunStatus.SUCCESS
        ).count()
        runs_failed_24h = ScrapeRun.objects.filter(
            started_at__gte=last_24h, status=ScrapeRunStatus.FAILED
        ).count()

        # Crawl runs (last 24 hours) — crawler pipeline
        crawl_runs_24h = CrawlRun.objects.filter(started_at__gte=last_24h).count()
        crawl_runs_success_24h = CrawlRun.objects.filter(
            started_at__gte=last_24h, status=CrawlRunStatus.SUCCESS
        ).count()
        crawl_runs_failed_24h = CrawlRun.objects.filter(
            started_at__gte=last_24h, status=CrawlRunStatus.FAILED
        ).count()

        # Recent prospects (last 10)
        recent_prospects = Prospect.objects.order_by("-created_at")[:10]

        # Recent scrape runs (last 10)
        recent_runs = ScrapeRun.objects.select_related("target").order_by(
            "-started_at"
        )[:10]

        # Recent crawl runs (last 10)
        recent_crawl_runs = CrawlRun.objects.order_by("-started_at")[:10]

        # Crawler summary (last run + last 24h)
        crawler_target = ScrapeTarget.objects.filter(name="translation_lead_crawler").first()
        crawler_last_run = None
        crawler_last_stats = None
        crawler_services = []
        crawler_runs_24h = 0
        crawler_prospects_24h = 0
        if crawler_target:
            crawler_last_run = (
                ScrapeRun.objects.filter(target=crawler_target)
                .order_by("-started_at")
                .first()
            )
            if crawler_last_run and crawler_last_run.stats:
                crawler_last_stats = crawler_last_run.stats
                svc = dict((crawler_last_run.stats or {}).get("services_detected") or {})
                crawler_services = sorted(
                    [(k, int(v or 0)) for k, v in svc.items() if int(v or 0) > 0],
                    key=lambda kv: kv[1],
                    reverse=True,
                )[:7]

            crawler_last_24h = timezone.now() - timedelta(hours=24)
            crawler_runs_24h = ScrapeRun.objects.filter(
                target=crawler_target, started_at__gte=crawler_last_24h
            ).count()
            # More actionable: total created+updated from runs in last 24h
            crawler_prospects_24h = sum(
                (r.created_leads or 0) + (r.updated_leads or 0)
                for r in ScrapeRun.objects.filter(
                    target=crawler_target, started_at__gte=crawler_last_24h
                ).only("created_leads", "updated_leads")
            )

        # Recent activity (for timeline widget)
        recent_activity = (
            ActivityLog.objects.select_related("user")
            .order_by("-created_at")[:15]
        )

        # Chart data - Prospect status distribution (serialized for template)
        prospect_status_labels = ['New', 'Contacted', 'Converted', 'Rejected']
        prospect_status_data = [prospect_new, prospect_contacted, prospect_converted, prospect_rejected]

        # Chart data - Lead status distribution (serialized for template)
        lead_error_count = Lead.objects.filter(status=LeadStatus.ERROR).count()
        lead_status_labels = ['Contacted', 'Interested', 'Synced', 'Rejected', 'Error']
        lead_status_data = [lead_contacted, lead_interested, lead_synced, lead_rejected, lead_error_count]

        # Chart data - Runs over time (last 7 days)
        runs_by_day = []
        for i in range(6, -1, -1):
            day_start = timezone.now() - timedelta(days=i + 1)
            day_end = timezone.now() - timedelta(days=i)
            count = ScrapeRun.objects.filter(
                started_at__gte=day_start, started_at__lt=day_end
            ).count()
            runs_by_day.append({
                'date': day_end.strftime('%Y-%m-%d'),
                'label': day_end.strftime('%b %d'),
                'count': count
            })

        context.update(
            {
                # Prospect stats
                "prospect_total": prospect_total,
                "prospect_new": prospect_new,
                "prospect_contacted": prospect_contacted,
                "prospect_converted": prospect_converted,
                "prospect_rejected": prospect_rejected,
                # Lead stats
                "lead_total": lead_total,
                "lead_contacted": lead_contacted,
                "lead_interested": lead_interested,
                "lead_synced": lead_synced,
                "lead_rejected": lead_rejected,
                # Target stats
                "target_total": target_total,
                "target_enabled": target_enabled,
                "target_disabled": target_disabled,
                # Run stats (scraper)
                "runs_24h": runs_24h,
                "runs_success_24h": runs_success_24h,
                "runs_failed_24h": runs_failed_24h,
                # Crawl run stats (crawler pipeline)
                "crawl_runs_24h": crawl_runs_24h,
                "crawl_runs_success_24h": crawl_runs_success_24h,
                "crawl_runs_failed_24h": crawl_runs_failed_24h,
                # Recent activity
                "recent_prospects": recent_prospects,
                "recent_runs": recent_runs,
                "recent_crawl_runs": recent_crawl_runs,
                "recent_activity": recent_activity,
                # Crawler summary
                "crawler_target": crawler_target,
                "crawler_last_run": crawler_last_run,
                "crawler_last_stats": crawler_last_stats,
                "crawler_services": crawler_services,
                "crawler_runs_24h": crawler_runs_24h,
                "crawler_prospects_24h": crawler_prospects_24h,
            # Chart data (serialized as JSON for JavaScript)
            "prospect_status_labels_json": json.dumps(prospect_status_labels),
            "prospect_status_data_json": json.dumps(prospect_status_data),
            "lead_status_labels_json": json.dumps(lead_status_labels),
            "lead_status_data_json": json.dumps(lead_status_data),
            "runs_by_day_json": json.dumps(runs_by_day),
            }
        )

        return context


class CrawlerHomeView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/crawler_home.html"


class CrawlSourceListView(LoginRequiredMixin, ListView):
    model = CrawlSource
    template_name = "dashboard/crawler_sources.html"
    context_object_name = "sources"
    ordering = ["priority", "id"]

    def get_queryset(self):
        return super().get_queryset().order_by("priority", "id")


class CrawlSourceCreateView(LoginRequiredMixin, CreateView):
    model = CrawlSource
    form_class = CrawlSourceForm
    template_name = "dashboard/crawler_source_form.html"
    success_url = reverse_lazy("dashboard:crawler_sources")


class CrawlSourceUpdateView(LoginRequiredMixin, UpdateView):
    model = CrawlSource
    form_class = CrawlSourceForm
    template_name = "dashboard/crawler_source_form.html"
    success_url = reverse_lazy("dashboard:crawler_sources")


class DiscoveredDomainListView(LoginRequiredMixin, ListView):
    model = DiscoveredDomain
    template_name = "dashboard/crawler_domains.html"
    context_object_name = "domains"
    ordering = ["crawl_status", "priority", "-first_seen_at"]
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset().select_related("source").order_by(
            "crawl_status", "priority", "-first_seen_at"
        )
        status_filter = (self.request.GET.get("status") or "").strip()
        if status_filter in {"pending", "crawling", "completed", "failed"}:
            qs = qs.filter(crawl_status=status_filter)
        source_id = (self.request.GET.get("source") or "").strip()
        if source_id.isdigit():
            qs = qs.filter(source_id=int(source_id))
        search = (self.request.GET.get("search") or "").strip()
        if search:
            qs = qs.filter(domain__icontains=search)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sources"] = CrawlSource.objects.all().order_by("priority", "name")
        context["status"] = (self.request.GET.get("status") or "").strip()
        context["source_selected"] = (self.request.GET.get("source") or "").strip()
        context["search"] = (self.request.GET.get("search") or "").strip()
        return context


class CrawlerDiscoverView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/crawler_discover.html"


class TargetWizardView(LoginRequiredMixin, TemplateView):
    """Wizard for creating scrape targets with auto-detection."""
    template_name = 'dashboard/target_wizard.html'


class TargetEditView(LoginRequiredMixin, UpdateView):
    """Edit an existing scrape target in the dashboard."""
    model = ScrapeTarget
    form_class = TargetEditForm
    template_name = "dashboard/target_edit.html"
    context_object_name = "target"

    def get_success_url(self):
        return reverse_lazy("dashboard:target_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        log_activity(
            action="target_updated",
            object_type="target",
            object_id=self.object.pk,
            description=f"Target «{self.object.name}» updated",
            user=self.request.user,
        )
        messages.success(self.request, f"Target «{self.object.name}» updated.")
        return super().form_valid(form)


class TargetListView(LoginRequiredMixin, ListView):
    """List all scrape targets."""

    model = ScrapeTarget
    template_name = "dashboard/targets.html"
    context_object_name = "targets"
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by enabled status
        enabled_filter = self.request.GET.get("enabled")
        if enabled_filter == "true":
            queryset = queryset.filter(enabled=True)
        elif enabled_filter == "false":
            queryset = queryset.filter(enabled=False)

        # Search by name
        search = self.request.GET.get("search")
        if search and search.strip():
            queryset = queryset.filter(name__icontains=search.strip())

        return queryset.annotate(
            total_runs=Count("runs"),
            success_runs=Count("runs", filter=Q(runs__status=ScrapeRunStatus.SUCCESS)),
            failed_runs=Count("runs", filter=Q(runs__status=ScrapeRunStatus.FAILED)),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["enabled_count"] = ScrapeTarget.objects.filter(enabled=True).count()
        context["disabled_count"] = ScrapeTarget.objects.filter(enabled=False).count()
        return context


class TargetDetailView(LoginRequiredMixin, DetailView):
    """View and edit scrape target details."""

    model = ScrapeTarget
    template_name = "dashboard/target_detail.html"
    context_object_name = "target"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target = self.get_object()

        # Get recent runs for this target
        recent_runs = target.runs.order_by("-started_at")[:10]

        # Calculate stats
        total_runs = target.runs.count()
        success_runs = target.runs.filter(status=ScrapeRunStatus.SUCCESS).count()
        failed_runs = target.runs.filter(status=ScrapeRunStatus.FAILED).count()
        success_rate = (success_runs / total_runs * 100) if total_runs > 0 else 0

        # Total items scraped
        total_items = sum(run.item_count for run in target.runs.all())

        # Serialize config JSON for safe template rendering
        config_json = json.dumps(target.config, indent=2)

        context.update(
            {
                "recent_runs": recent_runs,
                "total_runs": total_runs,
                "success_runs": success_runs,
                "failed_runs": failed_runs,
                "success_rate": round(success_rate, 1),
                "total_items": total_items,
                "config_json": config_json,
            }
        )

        return context


class CrawlTargetListView(LoginRequiredMixin, ListView):
    """List all crawl targets (CrawlSource). Separate from scrape targets."""

    model = CrawlSource
    template_name = "dashboard/crawl_targets.html"
    context_object_name = "crawl_targets"
    ordering = ["priority", "id"]

    def get_queryset(self):
        queryset = super().get_queryset()
        enabled_filter = self.request.GET.get("enabled")
        if enabled_filter == "true":
            queryset = queryset.filter(enabled=True)
        elif enabled_filter == "false":
            queryset = queryset.filter(enabled=False)
        search = self.request.GET.get("search")
        if search and search.strip():
            queryset = queryset.filter(
                Q(name__icontains=search.strip())
                | Q(discovery_query__icontains=search.strip())
            )
        return queryset.annotate(domain_count=Count("domains"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["enabled_count"] = CrawlSource.objects.filter(enabled=True).count()
        context["disabled_count"] = CrawlSource.objects.filter(enabled=False).count()
        return context


class CrawlTargetDetailView(LoginRequiredMixin, DetailView):
    """View a single crawl target (CrawlSource) and recent domains from it."""

    model = CrawlSource
    template_name = "dashboard/crawl_target_detail.html"
    context_object_name = "crawl_target"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        source = self.get_object()
        recent_domains = DiscoveredDomain.objects.filter(source=source).order_by(
            "-first_seen_at"
        )[:20]
        context["recent_domains"] = recent_domains
        context["domain_count"] = DiscoveredDomain.objects.filter(source=source).count()
        return context


class RunListView(LoginRequiredMixin, ListView):
    """List all scrape runs."""

    model = ScrapeRun
    template_name = "dashboard/runs.html"
    context_object_name = "runs"
    ordering = ["-started_at"]
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset().select_related("target")

        # Preset filter: crawler only
        crawler_only = (self.request.GET.get("crawler") or "").strip().lower()
        if crawler_only in {"1", "true", "t", "yes", "y", "on"}:
            queryset = queryset.filter(target__name="translation_lead_crawler")

        # Filter by status
        status_filter = self.request.GET.get("status")
        if status_filter in [s[0] for s in ScrapeRunStatus.choices]:
            queryset = queryset.filter(status=status_filter)

        # Filter by target
        target_id = self.request.GET.get("target")
        if target_id:
            queryset = queryset.filter(target_id=target_id)

        # Search by target name
        search = self.request.GET.get("search")
        if search and search.strip():
            queryset = queryset.filter(target__name__icontains=search.strip())

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["targets"] = ScrapeTarget.objects.all().order_by("name")
        context["status_choices"] = ScrapeRunStatus.choices
        crawler_only = (self.request.GET.get("crawler") or "").strip().lower()
        context["crawler_only"] = crawler_only in {"1", "true", "t", "yes", "y", "on"}
        return context


class RunDetailView(LoginRequiredMixin, DetailView):
    """View scrape run details."""

    model = ScrapeRun
    template_name = "dashboard/run_detail.html"
    context_object_name = "run"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        run = self.get_object()

        # Calculate duration
        duration = None
        if run.finished_at and run.started_at:
            duration = run.finished_at - run.started_at

        # Serialize stats JSON for safe template rendering
        stats_json = json.dumps(run.stats, indent=2) if run.stats else None

        is_crawler_run = bool(run.target and run.target.name == "translation_lead_crawler")
        crawler_stats = dict(run.stats or {}) if is_crawler_run else {}
        services_detected = dict((crawler_stats.get("services_detected") or {})) if is_crawler_run else {}
        services_detected_items = sorted(
            [(k, int(v or 0)) for k, v in services_detected.items()],
            key=lambda kv: kv[1],
            reverse=True,
        )

        crawler_progress = None
        crawler_failures = []
        domain_results_page_obj = None
        if is_crawler_run:
            try:
                from crawler.models import CrawlRunDomainResult

                state_counts = (
                    CrawlRunDomainResult.objects.filter(run_id=run.id)
                    .values("state")
                    .annotate(count=Count("id"))
                )
                counts = {row["state"]: int(row["count"] or 0) for row in state_counts}
                processed = CrawlRunDomainResult.objects.filter(
                    run_id=run.id, processed_at__isnull=False
                ).count()
                failed = CrawlRunDomainResult.objects.filter(
                    run_id=run.id, state="failed"
                ).count()
                crawler_progress = {
                    "expected": int(run.item_count or 0),
                    "processed": int(processed or 0),
                    "failed": int(failed or 0),
                    "states": counts,
                }

                crawler_failures = list(
                    CrawlRunDomainResult.objects.filter(run_id=run.id, state="failed")
                    .select_related("domain")
                    .order_by("-updated_at")[:10]
                    .values("domain__domain", "crawl_error", "pages_crawled", "updated_at")
                )

                # Per-domain results (paginated)
                dpage = self.request.GET.get("dpage") or "1"
                domain_qs = (
                    CrawlRunDomainResult.objects.filter(run_id=run.id)
                    .select_related("domain")
                    .order_by("-score", "domain__domain")
                )
                paginator = Paginator(domain_qs, 50)
                domain_results_page_obj = paginator.get_page(dpage)
            except Exception:
                crawler_progress = None
                crawler_failures = []
                domain_results_page_obj = None

        context.update(
            {
                "duration": duration,
                "stats_json": stats_json,
                "is_crawler_run": is_crawler_run,
                "crawler_stats": crawler_stats,
                "services_detected_items": services_detected_items,
                "crawler_progress": crawler_progress,
                "crawler_failures": crawler_failures,
                "domain_results_page_obj": domain_results_page_obj,
            }
        )
        return context


class CrawlRunListView(LoginRequiredMixin, ListView):
    """List all crawler discovery runs (CrawlRun)."""

    model = CrawlRun
    template_name = "dashboard/crawl_runs.html"
    context_object_name = "crawl_runs"
    ordering = ["-started_at"]
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.GET.get("status")
        if status_filter in [s[0] for s in CrawlRunStatus.choices]:
            queryset = queryset.filter(status=status_filter)
        trigger_filter = self.request.GET.get("trigger")
        if trigger_filter in [s[0] for s in CrawlRunTrigger.choices]:
            queryset = queryset.filter(trigger=trigger_filter)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = CrawlRunStatus.choices
        context["trigger_choices"] = CrawlRunTrigger.choices
        return context


class CrawlRunDetailView(LoginRequiredMixin, DetailView):
    """View crawler run details."""

    model = CrawlRun
    template_name = "dashboard/crawl_run_detail.html"
    context_object_name = "crawl_run"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        run = self.get_object()
        duration = None
        if run.finished_at and run.started_at:
            duration = run.finished_at - run.started_at
        stats_json = json.dumps(run.stats, indent=2) if run.stats else None
        config_json = json.dumps(run.config, indent=2) if run.config else None
        context["duration"] = duration
        context["stats_json"] = stats_json
        context["config_json"] = config_json
        return context


class ProspectCreateView(LoginRequiredMixin, CreateView):
    """Add a new prospect from the dashboard."""
    model = Prospect
    form_class = ProspectCreateForm
    template_name = "dashboard/prospect_form.html"

    def get_success_url(self):
        return reverse_lazy("dashboard:prospect_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        log_activity(
            action="prospect_created",
            object_type="prospect",
            object_id=self.object.pk,
            description=f"Prospect #{self.object.pk} created",
            user=self.request.user,
        )
        messages.success(self.request, "Prospect created.")
        return response


class ProspectListView(LoginRequiredMixin, ListView):
    """List all prospects with filtering and search."""

    model = Prospect
    template_name = "dashboard/prospects.html"
    context_object_name = "prospects"
    ordering = ["-created_at"]
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by status
        status_filter = self.request.GET.get("status")
        if status_filter in [s[0] for s in ProspectStatus.choices]:
            queryset = queryset.filter(status=status_filter)

        # Filter by source
        source_filter = self.request.GET.get("source")
        if source_filter:
            queryset = queryset.filter(source_name__icontains=source_filter)

        # Search (event, company, email, phone, source)
        search = self.request.GET.get("search")
        if search and search.strip():
            queryset = queryset.filter(
                Q(event_name__icontains=search)
                | Q(company__icontains=search)
                | Q(email__icontains=search)
                | Q(phone_e164__icontains=search)
                | Q(source_name__icontains=search)
            )

        # Date range filter (inclusive: whole day for from/to)
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = ProspectStatus.choices
        context["sources"] = (
            Prospect.objects.values_list("source_name", flat=True)
            .distinct()
            .order_by("source_name")
        )
        return context


class ProspectDetailView(LoginRequiredMixin, DetailView):
    """View prospect details."""

    model = Prospect
    template_name = "dashboard/prospect_detail.html"
    context_object_name = "prospect"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        prospect = self.get_object()

        # Serialize raw payload JSON
        raw_payload_json = (
            json.dumps(prospect.raw_payload, indent=2) if prospect.raw_payload else None
        )

        # Check if converted to lead (Lead.prospect has related_name="leads")
        converted_lead = None
        if prospect.status == ProspectStatus.CONVERTED:
            try:
                converted_lead = prospect.leads.first()
            except Exception:
                pass

        context.update(
            {
                "raw_payload_json": raw_payload_json,
                "converted_lead": converted_lead,
            }
        )
        return context


class LeadCreateView(LoginRequiredMixin, CreateView):
    """Add a new lead from the dashboard."""
    model = Lead
    form_class = LeadCreateForm
    template_name = "dashboard/lead_form.html"

    def get_success_url(self):
        return reverse_lazy("dashboard:lead_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        log_activity(
            action="lead_created",
            object_type="lead",
            object_id=self.object.pk,
            description=f"Lead #{self.object.pk} created",
            user=self.request.user,
        )
        messages.success(self.request, "Lead created.")
        return response


class LeadListView(LoginRequiredMixin, ListView):
    """List all leads with filtering and search."""

    model = Lead
    template_name = "dashboard/leads.html"
    context_object_name = "leads"
    ordering = ["-created_at"]
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset().select_related("prospect")

        # Filter by status
        status_filter = self.request.GET.get("status")
        if status_filter in [s[0] for s in LeadStatus.choices]:
            queryset = queryset.filter(status=status_filter)

        # Filter by source
        source_filter = self.request.GET.get("source")
        if source_filter:
            queryset = queryset.filter(source_name__icontains=source_filter)

        # Search (name, company, email, phone, event, source)
        search = self.request.GET.get("search")
        if search and search.strip():
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(company__icontains=search)
                | Q(email__icontains=search)
                | Q(phone_e164__icontains=search)
                | Q(event_name__icontains=search)
                | Q(source_name__icontains=search)
            )

        # Date range filter (inclusive: whole day for from/to)
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = LeadStatus.choices
        context["sources"] = (
            Lead.objects.values_list("source_name", flat=True)
            .distinct()
            .order_by("source_name")
        )
        return context


class LeadDetailView(LoginRequiredMixin, DetailView):
    """View lead details."""

    model = Lead
    template_name = "dashboard/lead_detail.html"
    context_object_name = "lead"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lead = self.get_object()

        # Serialize raw payload JSON
        raw_payload_json = (
            json.dumps(lead.raw_payload, indent=2) if lead.raw_payload else None
        )

        # Check Perfex sync status (PerfexLeadSync uses last_sync_at)
        perfex_synced = False
        perfex_sync_date = None
        try:
            from crm_integration.models import PerfexLeadSync

            sync = PerfexLeadSync.objects.filter(lead=lead).first()
            if sync and sync.last_sync_at:
                perfex_synced = True
                perfex_sync_date = sync.last_sync_at
        except Exception:
            pass

        context.update(
            {
                "raw_payload_json": raw_payload_json,
                "perfex_synced": perfex_synced,
                "perfex_sync_date": perfex_sync_date,
            }
        )
        return context


class ErrorMonitoringView(LoginRequiredMixin, TemplateView):
    """Dedicated view for failed scrape runs, failed crawl runs, and error summary."""

    template_name = "dashboard/error_monitoring.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)

        # Failed scrape runs
        failed_runs = (
            ScrapeRun.objects.filter(status=ScrapeRunStatus.FAILED)
            .select_related("target")
            .order_by("-started_at")[:50]
        )
        failed_24h = ScrapeRun.objects.filter(
            status=ScrapeRunStatus.FAILED, started_at__gte=last_24h
        ).count()
        failed_7d = ScrapeRun.objects.filter(
            status=ScrapeRunStatus.FAILED, started_at__gte=last_7d
        ).count()

        # Failed crawl runs (crawler pipeline)
        failed_crawl_runs = (
            CrawlRun.objects.filter(status=CrawlRunStatus.FAILED)
            .order_by("-started_at")[:50]
        )
        failed_crawl_24h = CrawlRun.objects.filter(
            status=CrawlRunStatus.FAILED, started_at__gte=last_24h
        ).count()
        failed_crawl_7d = CrawlRun.objects.filter(
            status=CrawlRunStatus.FAILED, started_at__gte=last_7d
        ).count()

        context.update(
            {
                "failed_runs": failed_runs,
                "failed_24h": failed_24h,
                "failed_7d": failed_7d,
                "failed_crawl_runs": failed_crawl_runs,
                "failed_crawl_24h": failed_crawl_24h,
                "failed_crawl_7d": failed_crawl_7d,
            }
        )
        return context


class ActivityLogListView(LoginRequiredMixin, ListView):
    """View activity log (audit trail) with optional filters."""

    model = ActivityLog
    template_name = "dashboard/activity_log.html"
    context_object_name = "activity_list"
    paginate_by = 50
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("user")
        action = self.request.GET.get("action")
        object_type = self.request.GET.get("object_type")
        search = self.request.GET.get("search")
        if action:
            queryset = queryset.filter(action=action)
        if object_type:
            queryset = queryset.filter(object_type=object_type)
        if search and search.strip():
            queryset = queryset.filter(description__icontains=search.strip())
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action_choices"] = ActivityLog.ACTION_CHOICES
        context["object_types"] = ["prospect", "lead", "target", "run"]
        return context
