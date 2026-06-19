from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crawler", "0014_discovereddomain_source_url_nonnull"),
    ]

    operations = [
        migrations.AddField(
            model_name="aisearchjob",
            name="qualification_log",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
