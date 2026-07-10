from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crawler", "0015_aisearchjob_qualification_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="crawlrun",
            name="coordinator_task_id",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="crawlrun",
            name="cycles_completed",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="crawlrun",
            name="duration_minutes",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="crawlrun",
            name="ends_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="crawlrun",
            name="last_cycle_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="crawlrun",
            name="session_mode",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="crawlrun",
            name="trigger",
            field=models.CharField(
                choices=[
                    ("scheduled", "Scheduled"),
                    ("manual", "Manual"),
                    ("session", "Session"),
                ],
                default="scheduled",
                max_length=20,
            ),
        ),
    ]
