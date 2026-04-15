# Generated manually for Serper landing URL preservation

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crawler", "0011_remove_aisearchresult_source_page_url_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="discovereddomain",
            name="source_url",
            field=models.URLField(
                blank=True,
                default="",
                max_length=2048,
                help_text="Full URL from discovery (e.g. Serper) that led to this domain; crawl starts here when set.",
            ),
        ),
    ]
