# Backfill NULL/empty source_url (SQLite NOT NULL or legacy rows) before strict saves.

from django.db import migrations


def _fallback_source_url(domain: str) -> str:
    d = (domain or "").strip()
    if not d:
        return "https://invalid.invalid"
    if d.startswith("http://") or d.startswith("https://"):
        return d
    return "https://" + d.lower().lstrip("/")


def forwards(apps, schema_editor):
    DiscoveredDomain = apps.get_model("crawler", "DiscoveredDomain")
    for row in DiscoveredDomain.objects.iterator():
        su = getattr(row, "source_url", None)
        if su not in (None, ""):
            continue
        row.source_url = _fallback_source_url(row.domain or "")
        row.save(update_fields=["source_url"])


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("crawler", "0013_alter_discovereddomain_source_url"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards_noop),
    ]
