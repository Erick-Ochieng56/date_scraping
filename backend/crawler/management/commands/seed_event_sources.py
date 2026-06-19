from django.core.management.base import BaseCommand

from crawler.models import CrawlSource
from crawler.signals import (
    connect_auto_derive_competitor_signals,
    disconnect_auto_derive_competitor_signals,
)
from crawler.services.competitor_deriver import derive_competitor_signals

EVENT_SOURCES = [
    {
        "name": "Kenya Government Tenders",
        "discovery_query": "site:tenders.go.ke OR site:agpo.go.ke interpretation translation tender Kenya",
        "source_type": "directory",
    },
    {
        "name": "Uganda Procurement Tenders",
        "discovery_query": "site:gov.ug OR site:ppda.go.ug interpretation translation tender Uganda",
        "source_type": "directory",
    },
    {
        "name": "Tanzania Government Tenders",
        "discovery_query": "Tanzania government interpretation translation tender RFP Dar es Salaam",
        "source_type": "directory",
    },
    {
        "name": "Rwanda Events and Tenders",
        "discovery_query": "Rwanda conference interpretation tender Kigali East Africa",
        "source_type": "event_platform",
    },
    {
        "name": "East Africa Medical Congresses",
        "discovery_query": "East Africa medical congress Kenya Uganda Tanzania interpretation services 2026",
        "source_type": "event_platform",
    },
    {
        "name": "East Africa Legal Conferences",
        "discovery_query": "East Africa arbitration conference Kenya Uganda multilingual 2026",
        "source_type": "event_platform",
    },
    {
        "name": "NGO Development Forums East Africa",
        "discovery_query": "East Africa NGO development forum Kenya Uganda interpretation language",
        "source_type": "event_platform",
    },
    {
        "name": "East Africa Trade Summits",
        "discovery_query": "East Africa trade investment summit Kenya Uganda simultaneous interpretation",
        "source_type": "event_platform",
    },
    {
        "name": "UNGM East Africa Tenders",
        "discovery_query": "site:ungm.org interpretation translation tender Kenya Uganda Tanzania",
        "source_type": "directory",
    },
    {
        "name": "ReliefWeb East Africa RFPs",
        "discovery_query": "site:reliefweb.int interpretation translation RFP Kenya Uganda Tanzania Ethiopia",
        "source_type": "directory",
    },
]


class Command(BaseCommand):
    help = "Seed East Africa event and tender focused CrawlSource entries"

    def add_arguments(self, parser):
        parser.add_argument(
            "--derive-competitors",
            action="store_true",
            help="After seeding, derive competitor keywords slowly (one Gemini call every 4s).",
        )

    def handle(self, *args, **options):
        disconnect_auto_derive_competitor_signals()
        try:
            created_sources: list[CrawlSource] = []
            for data in EVENT_SOURCES:
                obj, created = CrawlSource.objects.get_or_create(
                    name=data["name"],
                    defaults={
                        **data,
                        "enabled": True,
                        "priority": 9,
                    },
                )
                status = "Created" if created else "Exists"
                self.stdout.write(f"{status}: {data['name']}")
                if created:
                    created_sources.append(obj)
        finally:
            connect_auto_derive_competitor_signals()

        if options["derive_competitors"] and created_sources:
            self.stdout.write("Deriving competitor signals (slow mode to avoid rate limits)...")
            for idx, source in enumerate(created_sources):
                if source.competitor_keywords:
                    continue
                if idx > 0:
                    import time

                    time.sleep(4)
                try:
                    signals = derive_competitor_signals(source.discovery_query)
                except Exception as exc:
                    if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                        self.stdout.write(
                            self.style.WARNING(
                                "Gemini rate limit reached; remaining sources use default competitor filters."
                            )
                        )
                        break
                    raise
                CrawlSource.objects.filter(pk=source.pk).update(
                    competitor_keywords=signals.get("competitor_keywords", []),
                    competitor_org_types=signals.get("competitor_org_types", []),
                )
                self.stdout.write(f"  Derived: {source.name}")

        self.stdout.write(self.style.SUCCESS("Done seeding event sources."))
