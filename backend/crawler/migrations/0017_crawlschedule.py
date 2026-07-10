from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("crawler", "0016_crawlrun_session_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CrawlSchedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("enabled", models.BooleanField(default=True)),
                ("interval_minutes", models.PositiveIntegerField(help_text="Minutes between session starts (e.g. 720 = 12 hours).")),
                (
                    "session_duration_minutes",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Optional per-run duration; uses CRAWLER_SCHEDULE_DEFAULT_SESSION_MINUTES when null.",
                        null=True,
                    ),
                ),
                ("last_started_at", models.DateTimeField(blank=True, null=True)),
                (
                    "source_filter",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Optional source constraints (reserved for future use).",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crawl_schedules",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["enabled", "owner"], name="crawler_cra_enabled_8f1a2b_idx"),
                    models.Index(fields=["last_started_at"], name="crawler_cra_last_st_9c3d4e_idx"),
                ],
            },
        ),
    ]
