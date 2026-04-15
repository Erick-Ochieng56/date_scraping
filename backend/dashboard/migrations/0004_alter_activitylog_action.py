from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0003_scraper_group"),
    ]

    operations = [
        migrations.AlterField(
            model_name="activitylog",
            name="action",
            field=models.CharField(
                max_length=50,
                choices=[
                    ("prospect_created", "Prospect Created"),
                    ("prospect_contacted", "Prospect Marked Contacted"),
                    ("prospect_converted", "Prospect Converted to Lead"),
                    ("prospect_rejected", "Prospect Rejected"),
                    ("lead_created", "Lead Created"),
                    ("lead_interested", "Lead Marked Interested"),
                    ("lead_synced", "Lead Synced to CRM"),
                    ("lead_rejected", "Lead Rejected"),
                    ("target_created", "Target Created"),
                    ("target_updated", "Target Updated"),
                    ("target_enabled", "Target Enabled"),
                    ("target_disabled", "Target Disabled"),
                    ("scrape_triggered", "Scrape Triggered"),
                    ("scrape_completed", "Scrape Completed"),
                    ("scrape_failed", "Scrape Failed"),
                    ("crawl_triggered", "Crawl Discovery Triggered"),
                    ("user_created", "User Created"),
                    ("user_updated", "User Updated"),
                    ("ownership_transferred", "Ownership Transferred"),
                    ("admin_scrape_triggered", "Admin Scrape Triggered"),
                    ("admin_scrape_retry", "Admin Scrape Retry"),
                ],
            ),
        ),
    ]
