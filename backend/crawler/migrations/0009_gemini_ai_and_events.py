# Generated manually for Gemini AI, competitor fields, AI search jobs, event prospects.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crawler", "0008_owner_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="crawlsource",
            name="competitor_keywords",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Keywords that indicate a site IS a competitor. Auto-derived from discovery_query if empty.",
            ),
        ),
        migrations.AddField(
            model_name="crawlsource",
            name="competitor_org_types",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Org types to exclude e.g. ['translation_agency', 'lsp', 'localization_vendor']",
            ),
        ),
        migrations.AddField(
            model_name="websiteprofile",
            name="excluded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="websiteprofile",
            name="gemini_translation_need_score",
            field=models.IntegerField(
                blank=True,
                help_text="When set, scoring pipeline prefers this value over rule-based score_website().",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="websiteprofile",
            name="is_competitor",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="websiteprofile",
            name="is_competitor_reason",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="crawlrundomainresult",
            name="is_competitor",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="crawlrundomainresult",
            name="is_competitor_reason",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddIndex(
            model_name="websiteprofile",
            index=models.Index(fields=["is_competitor"], name="crawler_web_is_comp_7a1b2c_idx"),
        ),
        migrations.CreateModel(
            name="AISearchJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("seed_topic", models.CharField(max_length=500)),
                ("industry", models.CharField(blank=True, default="", max_length=200)),
                ("region", models.CharField(blank=True, default="", max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("generating", "Generating Queries"),
                            ("searching", "Searching"),
                            ("done", "Done"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("error_text", models.TextField(blank=True, default="")),
                ("queries_generated", models.JSONField(default=list)),
                ("domains_discovered", models.PositiveIntegerField(default=0)),
                ("prospects_created", models.PositiveIntegerField(default=0)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_search_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AISearchResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("domain", models.CharField(max_length=255)),
                ("org_name", models.CharField(blank=True, default="", max_length=255)),
                ("org_type", models.CharField(blank=True, default="", max_length=100)),
                ("why_needs_translation", models.TextField(blank=True, default="")),
                ("international_signals", models.JSONField(default=list)),
                ("contact_email", models.CharField(blank=True, default="", max_length=255)),
                ("raw_data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="crawler.aisearchjob",
                    ),
                ),
                (
                    "queued_domain",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ai_search_results",
                        to="crawler.discovereddomain",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="EventProspect",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_name", models.CharField(max_length=500)),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("conference", "Conference"),
                            ("summit", "Summit"),
                            ("trade_show", "Trade Show"),
                            ("workshop", "Workshop"),
                            ("diplomatic", "Diplomatic Meeting"),
                            ("legal", "Legal Proceeding"),
                            ("medical", "Medical Congress"),
                            ("ngo", "NGO/Development Forum"),
                            ("government", "Government Event"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=50,
                    ),
                ),
                ("organizer_name", models.CharField(blank=True, default="", max_length=255)),
                ("organizer_domain", models.CharField(blank=True, default="", max_length=255)),
                ("event_url", models.URLField(blank=True, default="")),
                ("event_date", models.DateField(blank=True, null=True)),
                ("event_date_raw", models.CharField(blank=True, default="", max_length=200)),
                ("event_location", models.CharField(blank=True, default="", max_length=255)),
                ("is_virtual", models.BooleanField(default=False)),
                ("is_hybrid", models.BooleanField(default=False)),
                ("languages_involved", models.JSONField(default=list)),
                ("countries_involved", models.JSONField(default=list)),
                ("expected_attendee_count", models.CharField(blank=True, default="", max_length=100)),
                ("translation_services_needed", models.JSONField(default=list)),
                ("translation_need_score", models.IntegerField(default=0)),
                ("contact_name", models.CharField(blank=True, default="", max_length=255)),
                ("contact_email", models.CharField(blank=True, default="", max_length=255)),
                ("contact_phone", models.CharField(blank=True, default="", max_length=100)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("contacted", "Contacted"),
                            ("qualified", "Qualified"),
                            ("converted", "Converted"),
                            ("expired", "Expired"),
                            ("irrelevant", "Irrelevant"),
                        ],
                        default="new",
                        max_length=20,
                    ),
                ),
                ("urgency_score", models.IntegerField(default=0)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "ai_search_result",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="event_prospects",
                        to="crawler.aisearchresult",
                    ),
                ),
                (
                    "discovered_domain",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="event_prospects",
                        to="crawler.discovereddomain",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="event_prospects",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-urgency_score", "event_date"],
            },
        ),
        migrations.AddIndex(
            model_name="eventprospect",
            index=models.Index(fields=["event_date"], name="crawler_eve_event_d_8d3e4f_idx"),
        ),
        migrations.AddIndex(
            model_name="eventprospect",
            index=models.Index(fields=["status"], name="crawler_eve_status_9e4f5a_idx"),
        ),
        migrations.AddIndex(
            model_name="eventprospect",
            index=models.Index(fields=["urgency_score"], name="crawler_eve_urgency_a0b1c2_idx"),
        ),
        migrations.AddIndex(
            model_name="eventprospect",
            index=models.Index(fields=["event_type", "status"], name="crawler_eve_event_t_d3e4f5_idx"),
        ),
    ]
