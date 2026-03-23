from __future__ import annotations

from django.db import migrations


DEFAULT_SOURCES = [
    (
        "international conference 2026",
        "search",
        "Interpretation, Rapporteuring",
    ),
    (
        "global summit Africa 2026",
        "search",
        "Interpretation, Equipment",
    ),
    (
        "call for papers symposium 2026",
        "search",
        "Rapporteuring, Translation",
    ),
    (
        "NGO development programs Africa",
        "search",
        "Translation, Publishing",
    ),
    (
        "international forum workshops 2026",
        "search",
        "Interpretation, Equipment",
    ),
    (
        "multilingual event services needed",
        "search",
        "All services",
    ),
    (
        "university international conference",
        "search",
        "Rapporteuring, Interpretation",
    ),
    (
        "government multilingual program",
        "search",
        "Translation, Sign Language",
    ),
    (
        "export company international expansion",
        "search",
        "Translation, Localization",
    ),
    (
        "academic publishing multilingual",
        "search",
        "Copy-editing, Translation",
    ),
]


def seed_sources(apps, schema_editor) -> None:
    CrawlSource = apps.get_model("crawler", "CrawlSource")

    for query, source_type, target_service in DEFAULT_SOURCES:
        name = f"Seed: {query} ({target_service})"
        CrawlSource.objects.get_or_create(
            discovery_query=query,
            source_type=source_type,
            defaults={"name": name, "enabled": True, "priority": 5},
        )


def seed_crawler_target(apps, schema_editor) -> None:
    ScrapeTarget = apps.get_model("scraper", "ScrapeTarget")

    # We cannot add a new enum choice without modifying existing model code.
    # Instead, we create a dedicated ScrapeTarget with a stable name and config.
    ScrapeTarget.objects.get_or_create(
        name="translation_lead_crawler",
        defaults={
            "enabled": True,
            "target_type": "html",
            "start_url": "https://bing.com",
            "run_every_minutes": 720,
            "config": {
                "max_domains_per_run": 500,
                "min_score_threshold": 40,
                "rate_limit_seconds": 1.5,
            },
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("crawler", "0001_initial"),
        ("scraper", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_sources, migrations.RunPython.noop),
        migrations.RunPython(seed_crawler_target, migrations.RunPython.noop),
    ]

