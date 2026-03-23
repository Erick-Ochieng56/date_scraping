# Generated manually for RBAC — creates the "scraper" group for portal users.

from django.db import migrations


def create_scraper_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="scraper")


def remove_scraper_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="scraper").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0002_alter_activitylog_action"),
    ]

    operations = [
        migrations.RunPython(create_scraper_group, remove_scraper_group),
    ]
