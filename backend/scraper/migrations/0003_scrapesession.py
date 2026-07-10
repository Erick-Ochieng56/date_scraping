from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("scraper", "0002_owner_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ScrapeSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[("running", "Running"), ("success", "Success"), ("failed", "Failed")],
                        default="running",
                        max_length=20,
                    ),
                ),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("duration_minutes", models.PositiveIntegerField(blank=True, null=True)),
                ("coordinator_task_id", models.CharField(blank=True, default="", max_length=255)),
                ("cycles_completed", models.PositiveIntegerField(default=0)),
                ("last_cycle_at", models.DateTimeField(blank=True, null=True)),
                ("error_text", models.TextField(blank=True, default="")),
                ("stats", models.JSONField(blank=True, default=dict)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scrape_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-started_at"],
                "indexes": [
                    models.Index(fields=["status", "owner"], name="scraper_scr_status__a1f0d0_idx"),
                    models.Index(fields=["-started_at"], name="scraper_scr_started_8e2f1a_idx"),
                ],
            },
        ),
    ]
