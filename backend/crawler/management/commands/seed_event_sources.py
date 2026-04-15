from django.core.management.base import BaseCommand

from crawler.models import CrawlSource

EVENT_SOURCES = [
    {
        "name": "Cvent International Conferences",
        "discovery_query": "site:cvent.com international conference 2025 multilingual",
        "source_type": "event_platform",
    },
    {
        "name": "Eventbrite International Events",
        "discovery_query": "site:eventbrite.com international summit conference interpretation 2025",
        "source_type": "event_platform",
    },
    {
        "name": "10times Conference Directory",
        "discovery_query": "site:10times.com international conference Africa 2025",
        "source_type": "event_platform",
    },
    {
        "name": "UN and AU Events",
        "discovery_query": "site:un.org OR site:african-union.org conference 2025 official languages",
        "source_type": "event_platform",
    },
    {
        "name": "Medical Congresses Africa",
        "discovery_query": "international medical congress Africa 2025 interpretation services",
        "source_type": "event_platform",
    },
    {
        "name": "Legal Conferences Africa",
        "discovery_query": "international arbitration conference Africa 2025 multilingual",
        "source_type": "event_platform",
    },
    {
        "name": "NGO Development Forums",
        "discovery_query": "international development forum East Africa 2025 language",
        "source_type": "event_platform",
    },
    {
        "name": "Trade and Investment Summits",
        "discovery_query": "Africa trade investment summit 2025 interpretation simultaneous",
        "source_type": "event_platform",
    },
    {
        "name": "UN Tenders Interpretation",
        "discovery_query": "site:ungm.org interpretation translation services tender 2025",
        "source_type": "directory",
    },
    {
        "name": "USAID World Bank Events RFP",
        "discovery_query": "interpretation services RFP conference 2025 Africa filetype:pdf",
        "source_type": "directory",
    },
]


class Command(BaseCommand):
    help = "Seed event-focused CrawlSource entries"

    def handle(self, *args, **kwargs):
        for data in EVENT_SOURCES:
            _obj, created = CrawlSource.objects.get_or_create(
                name=data["name"],
                defaults={
                    **data,
                    "enabled": True,
                    "priority": 9,
                },
            )
            status = "Created" if created else "Exists"
            self.stdout.write(f"{status}: {data['name']}")
        self.stdout.write(self.style.SUCCESS("Done seeding event sources."))
