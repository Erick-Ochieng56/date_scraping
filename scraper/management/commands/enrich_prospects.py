"""
Management command to enrich prospects with detail page data.

This implements Stage 2 of two-stage scraping:
- Stage 1: Scrape listing pages (already done)
- Stage 2: Visit detail pages to extract contact info and additional details
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from leads.models import Prospect
from scraper.services.enrichment import enrich_prospects_batch


class Command(BaseCommand):
    help = "Enrich prospects by visiting their detail pages to extract additional information"

    def add_arguments(self, parser):
        parser.add_argument(
            "--prospect-ids",
            nargs="+",
            type=int,
            help="Specific prospect IDs to enrich (space-separated)",
        )

        parser.add_argument(
            "--platform",
            type=str,
            default="generic",
            choices=[
                "eventbrite",
                "meetup",
                "linkedin",
                "twitter",
                "facebook",
                "generic",
            ],
            help="Platform type for optimized extraction (default: generic)",
        )

        parser.add_argument(
            "--use-playwright",
            action="store_true",
            help="Use Playwright browser automation (required for JS-heavy sites like LinkedIn)",
        )

        parser.add_argument(
            "--delay",
            type=float,
            default=2.0,
            help="Delay in seconds between requests to avoid rate limiting (default: 2.0)",
        )

        parser.add_argument(
            "--max-prospects",
            type=int,
            default=50,
            help="Maximum number of prospects to enrich (default: 50)",
        )

        parser.add_argument(
            "--filter",
            type=str,
            choices=["unenriched", "all", "no-contact"],
            default="unenriched",
            help="Which prospects to enrich: unenriched (no email/company), all, or no-contact (no email)",
        )

        parser.add_argument(
            "--source",
            type=str,
            help="Filter by source name (e.g., 'Eventbrite - Tech Events')",
        )

        parser.add_argument(
            "--async",
            dest="use_async",
            action="store_true",
            help="Queue enrichment tasks in Celery instead of processing synchronously",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which prospects would be enriched without actually enriching them",
        )

    def handle(self, *args, **options):
        prospect_ids = options.get("prospect_ids")
        platform = options["platform"]
        use_playwright = options["use_playwright"]
        delay = options["delay"]
        max_prospects = options["max_prospects"]
        filter_type = options["filter"]
        source = options.get("source")
        use_async = options.get("use_async", False)
        dry_run = options["dry_run"]

        self.stdout.write("=" * 80)
        self.stdout.write(
            self.style.SUCCESS("Two-Stage Scraping - Detail Page Enrichment")
        )
        self.stdout.write("=" * 80)
        self.stdout.write("")

        # Build queryset
        if prospect_ids:
            prospects_qs = Prospect.objects.filter(id__in=prospect_ids)
        else:
            # Auto-discover prospects based on filter
            prospects_qs = Prospect.objects.filter(source_url__isnull=False).exclude(
                source_url=""
            )

            if filter_type == "unenriched":
                # No email AND no company
                prospects_qs = prospects_qs.filter(
                    Q(email__isnull=True) | Q(email=""),
                    Q(company="") | Q(company__isnull=True),
                )
            elif filter_type == "no-contact":
                # No email (but may have company)
                prospects_qs = prospects_qs.filter(Q(email__isnull=True) | Q(email=""))

            if source:
                prospects_qs = prospects_qs.filter(source_name__icontains=source)

            prospects_qs = prospects_qs[:max_prospects]

        # Get the prospect IDs
        prospect_count = prospects_qs.count()

        if prospect_count == 0:
            self.stdout.write(
                self.style.WARNING("No prospects found matching the criteria.")
            )
            return

        self.stdout.write(f"Found {prospect_count} prospects to enrich")
        self.stdout.write(f"Platform: {platform}")
        self.stdout.write(f"Use Playwright: {use_playwright}")
        self.stdout.write(f"Delay: {delay}s between requests")
        self.stdout.write(f"Filter: {filter_type}")
        if source:
            self.stdout.write(f"Source filter: {source}")
        self.stdout.write("")

        # Dry run mode
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )
            self.stdout.write("")
            self.stdout.write("Prospects that would be enriched:")
            for i, prospect in enumerate(prospects_qs[:10], 1):
                self.stdout.write(
                    f"  {i}. ID {prospect.id}: {prospect.event_name or '(no name)'} - "
                    f"{prospect.source_url[:60]}..."
                )
            if prospect_count > 10:
                self.stdout.write(f"  ... and {prospect_count - 10} more")
            return

        # Async mode (queue Celery tasks)
        if use_async:
            from scraper.tasks import enrich_prospects_batch_task

            self.stdout.write("Queueing enrichment tasks in Celery...")

            # Queue the batch task
            task = enrich_prospects_batch_task.delay(
                prospect_ids=list(prospects_qs.values_list("id", flat=True)),
                platform=platform,
                use_playwright=use_playwright,
                delay_seconds=delay,
                max_prospects=max_prospects,
            )

            self.stdout.write(
                self.style.SUCCESS(f"✓ Queued enrichment task: {task.id}")
            )
            self.stdout.write("Check Celery worker logs for progress and results.")
            return

        # Synchronous mode (process immediately)
        self.stdout.write("Starting enrichment (this may take a while)...")
        self.stdout.write("")

        try:
            results = enrich_prospects_batch(
                prospect_ids=list(prospects_qs.values_list("id", flat=True)),
                platform=platform,
                use_playwright=use_playwright,
                delay_seconds=delay,
                max_prospects=max_prospects,
            )

            # Display results
            self.stdout.write("")
            self.stdout.write("=" * 80)
            self.stdout.write(self.style.SUCCESS("Enrichment Complete"))
            self.stdout.write("=" * 80)
            self.stdout.write(f"Total prospects: {results['total']}")
            self.stdout.write(
                self.style.SUCCESS(f"✓ Successfully enriched: {results['success']}")
            )
            if results["skipped"] > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"⊘ Skipped (already enriched): {results['skipped']}"
                    )
                )
            if results["failed"] > 0:
                self.stdout.write(self.style.ERROR(f"✗ Failed: {results['failed']}"))

            # Show errors if any
            if results.get("errors"):
                self.stdout.write("")
                self.stdout.write("Errors:")
                for error in results["errors"][:10]:  # Show first 10 errors
                    self.stdout.write(
                        f"  Prospect {error['prospect_id']}: {error['error']}"
                    )
                if len(results["errors"]) > 10:
                    self.stdout.write(
                        f"  ... and {len(results['errors']) - 10} more errors"
                    )

        except Exception as e:
            raise CommandError(f"Enrichment failed: {e}")
