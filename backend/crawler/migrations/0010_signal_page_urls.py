from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crawler", "0009_gemini_ai_and_events"),
    ]

    operations = [
        migrations.AddField(
            model_name="websiteprofile",
            name="signal_page_url",
            field=models.URLField(
                max_length=2048,
                blank=True,
                default="",
                help_text="Best-matching crawled page URL (e.g. event/meeting) for display and prospect source.",
            ),
        ),
        migrations.AddField(
            model_name="aisearchresult",
            name="source_page_url",
            field=models.URLField(
                max_length=2048,
                blank=True,
                default="",
                help_text="SERP or grounded-search URL where the prospect was surfaced.",
            ),
        ),
        migrations.AddField(
            model_name="crawlrundomainresult",
            name="signal_page_url",
            field=models.URLField(
                max_length=2048,
                blank=True,
                default="",
                help_text="Page on the domain that best matched events / translation signals.",
            ),
        ),
    ]
