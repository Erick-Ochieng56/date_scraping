from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from scraper.models import ScrapeRun, ScrapeRunStatus, ScrapeTarget
from scraper.services.hashing import canonical_json, sha256_of_obj
from scraper.services.normalize import parse_date, parse_datetime
from scraper.tasks import (
    _target_has_run_in_progress,
    _target_is_due,
    enqueue_enabled_targets,
)


class EnqueueDueLogicTests(TestCase):
    """Phase 5: tests for per-target scheduling (run_every_minutes + concurrency guard)."""

    def test_target_is_due_when_never_run(self):
        target = ScrapeTarget(
            name="test-never-run",
            start_url="https://example.com",
            enabled=True,
            run_every_minutes=60,
            last_run_at=None,
        )
        target.save()
        self.assertTrue(_target_is_due(target))

    def test_target_is_due_when_interval_passed(self):
        target = ScrapeTarget(
            name="test-due",
            start_url="https://example.com",
            enabled=True,
            run_every_minutes=60,
            last_run_at=timezone.now() - timezone.timedelta(minutes=61),
        )
        target.save()
        self.assertTrue(_target_is_due(target))

    def test_target_not_due_when_interval_not_passed(self):
        target = ScrapeTarget(
            name="test-not-due",
            start_url="https://example.com",
            enabled=True,
            run_every_minutes=120,
            last_run_at=timezone.now() - timezone.timedelta(minutes=30),
        )
        target.save()
        self.assertFalse(_target_is_due(target))

    def test_target_has_run_in_progress_true(self):
        target = ScrapeTarget(
            name="test-in-progress",
            start_url="https://example.com",
            enabled=True,
            run_every_minutes=60,
        )
        target.save()
        ScrapeRun.objects.create(
            target=target,
            status=ScrapeRunStatus.RUNNING,
            started_at=timezone.now(),
        )
        self.assertTrue(_target_has_run_in_progress(target.id))

    def test_target_has_run_in_progress_false_when_no_run(self):
        target = ScrapeTarget(
            name="test-no-run",
            start_url="https://example.com",
            enabled=True,
            run_every_minutes=60,
        )
        target.save()
        self.assertFalse(_target_has_run_in_progress(target.id))

    def test_target_has_run_in_progress_false_when_run_old(self):
        target = ScrapeTarget(
            name="test-old-run",
            start_url="https://example.com",
            enabled=True,
            run_every_minutes=60,
        )
        target.save()
        # Run started well in the past (beyond concurrency guard)
        ScrapeRun.objects.create(
            target=target,
            status=ScrapeRunStatus.RUNNING,
            started_at=timezone.now() - timezone.timedelta(days=1),
        )
        self.assertFalse(_target_has_run_in_progress(target.id))

    @patch("scraper.tasks.scrape_target")
    def test_enqueue_only_due_targets(self, mock_scrape_target):
        # Ensure only our test targets are enabled (e.g. crawler seed may add targets)
        ScrapeTarget.objects.exclude(
            name__in=["due-target", "not-due-target"]
        ).update(enabled=False)
        due = ScrapeTarget.objects.create(
            name="due-target",
            start_url="https://example.com",
            enabled=True,
            run_every_minutes=60,
            last_run_at=None,
        )
        not_due = ScrapeTarget.objects.create(
            name="not-due-target",
            start_url="https://example.com",
            enabled=True,
            run_every_minutes=120,
            last_run_at=timezone.now() - timezone.timedelta(minutes=30),
        )
        count = enqueue_enabled_targets()
        self.assertEqual(count, 1)
        mock_scrape_target.delay.assert_called_once()
        call_kw = mock_scrape_target.delay.call_args[1]
        self.assertEqual(call_kw["target_id"], due.id)

    @patch("scraper.tasks.scrape_target")
    def test_enqueue_skips_target_with_run_in_progress(self, mock_scrape_target):
        # Ensure only our test target is enabled (e.g. crawler seed may add targets)
        ScrapeTarget.objects.exclude(name="in-progress-target").update(enabled=False)
        target = ScrapeTarget.objects.create(
            name="in-progress-target",
            start_url="https://example.com",
            enabled=True,
            run_every_minutes=60,
            last_run_at=None,
        )
        ScrapeRun.objects.create(
            target=target,
            status=ScrapeRunStatus.RUNNING,
            started_at=timezone.now(),
        )
        count = enqueue_enabled_targets()
        self.assertEqual(count, 0)
        mock_scrape_target.delay.assert_not_called()


class HashingTests(TestCase):
    def test_sha256_of_obj_is_stable_for_key_order(self):
        a = {"b": 2, "a": 1}
        b = {"a": 1, "b": 2}
        self.assertEqual(canonical_json(a), canonical_json(b))
        self.assertEqual(sha256_of_obj(a), sha256_of_obj(b))


class NormalizeTests(TestCase):
    def test_parse_date(self):
        d = parse_date("2026-01-25")
        self.assertIsNotNone(d)
        self.assertEqual(d.isoformat(), "2026-01-25")

    def test_parse_datetime(self):
        dt = parse_datetime("2026-01-25T10:11:12Z")
        self.assertIsNotNone(dt)
