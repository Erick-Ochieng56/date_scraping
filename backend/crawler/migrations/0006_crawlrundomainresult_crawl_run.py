# Generated manually for CrawlRun-backed domain results

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("crawler", "0005_merge_20260315_merge"),
    ]

    operations = [
        # Add FK to CrawlRun so pipeline can attach domain results to CrawlRun
        migrations.AddField(
            model_name="crawlrundomainresult",
            name="crawl_run",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="domain_results",
                to="crawler.crawlrun",
            ),
        ),
        # Allow run (ScrapeRun) to be null for CrawlRun-only results
        migrations.AlterField(
            model_name="crawlrundomainresult",
            name="run",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="crawler_domain_results",
                to="scraper.scraperun",
            ),
        ),
        # Replace single unique constraint with conditional ones (one of run/crawl_run must be set per row)
        migrations.RemoveConstraint(
            model_name="crawlrundomainresult",
            name="uniq_crawler_run_domain",
        ),
        migrations.AddConstraint(
            model_name="crawlrundomainresult",
            constraint=models.UniqueConstraint(
                condition=Q(run_id__isnull=False),
                fields=("run", "domain"),
                name="uniq_crawler_run_domain",
            ),
        ),
        migrations.AddConstraint(
            model_name="crawlrundomainresult",
            constraint=models.UniqueConstraint(
                condition=Q(crawl_run_id__isnull=False),
                fields=("crawl_run", "domain"),
                name="uniq_crawler_crawl_run_domain",
            ),
        ),
        migrations.AddIndex(
            model_name="crawlrundomainresult",
            index=models.Index(fields=["crawl_run", "state"], name="crawler_cra_crawl_r_state_idx"),
        ),
    ]
