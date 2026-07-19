from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from scraper.models import ScrapeRun, ScrapeRunStatus, ScrapeTarget
from scraper.services.fetch import fetch_html
from scraper.services.hashing import canonical_json, sha256_of_obj
from scraper.services.normalize import parse_date, parse_datetime
from scraper.services.upsert import upsert_prospect_from_item
from scraper.services.url_safety import check_public_url
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


class UpsertProspectFieldMappingTests(TestCase):
    """
    Regression tests for the bug where every auto-detected platform config
    (scraper/services/auto_discover.py) extracts the listing title under the
    "full_name" key and the date under "event_date", but upsert.py's field
    mapping never read either — so Prospect.event_name ended up blank (or
    holding whatever the "event_name" key happened to contain, usually an
    empty description snippet) and the date was dropped entirely for every
    wizard-created target.
    """

    def _target(self, **kwargs) -> ScrapeTarget:
        defaults = {"name": "test-target", "start_url": "https://example.com"}
        defaults.update(kwargs)
        target = ScrapeTarget(**defaults)
        target.save()
        return target

    def test_full_name_is_used_for_event_name(self):
        target = self._target()
        item = {
            "full_name": "Regional Health Summit 2026",
            "event_date": "2026-09-15",
            "source_url": "https://example.com/e/1",
        }
        prospect, created = upsert_prospect_from_item(target, item)
        self.assertTrue(created)
        self.assertEqual(prospect.event_name, "Regional Health Summit 2026")

    def test_event_date_is_parsed_and_stored(self):
        target = self._target()
        item = {
            "full_name": "Regional Health Summit 2026",
            "event_date": "September 15, 2026",
            "source_url": "https://example.com/e/1",
        }
        prospect, _ = upsert_prospect_from_item(target, item)
        self.assertIsNotNone(prospect.event_date)
        self.assertEqual(prospect.event_date.isoformat(), "2026-09-15")

    def test_title_key_is_also_accepted(self):
        """The frontend's default manual-JSON template uses "title" as the key."""
        target = self._target()
        item = {"title": "Manual Config Event", "source_url": "https://example.com/e/2"}
        prospect, _ = upsert_prospect_from_item(target, item)
        self.assertEqual(prospect.event_name, "Manual Config Event")

    def test_legacy_event_name_key_still_works(self):
        """Backward compatibility: existing targets that used "event_name" directly."""
        target = self._target()
        item = {"event_name": "Legacy Config Event", "source_url": "https://example.com/e/3"}
        prospect, _ = upsert_prospect_from_item(target, item)
        self.assertEqual(prospect.event_name, "Legacy Config Event")

    def test_full_name_takes_priority_over_event_name(self):
        target = self._target()
        item = {
            "full_name": "The Real Title",
            "event_name": "A description snippet, not the title",
            "source_url": "https://example.com/e/4",
        }
        prospect, _ = upsert_prospect_from_item(target, item)
        self.assertEqual(prospect.event_name, "The Real Title")

    def test_missing_or_unparseable_date_leaves_event_date_null(self):
        target = self._target()
        item = {"full_name": "No Date Event", "source_url": "https://example.com/e/5"}
        prospect, _ = upsert_prospect_from_item(target, item)
        self.assertIsNone(prospect.event_date)

    def test_update_of_existing_prospect_fills_in_previously_missing_title_and_date(self):
        target = self._target()
        first_item = {"email": "org@example.com", "source_url": "https://example.com/e/6"}
        prospect, created = upsert_prospect_from_item(target, first_item)
        self.assertTrue(created)
        self.assertEqual(prospect.event_name, "")
        self.assertIsNone(prospect.event_date)

        second_item = {
            "email": "org@example.com",
            "full_name": "Now With A Title",
            "event_date": "2026-11-01",
            "source_url": "https://example.com/e/6",
        }
        updated, created_again = upsert_prospect_from_item(target, second_item)
        self.assertFalse(created_again)
        self.assertEqual(updated.id, prospect.id)
        self.assertEqual(updated.event_name, "Now With A Title")
        self.assertEqual(updated.event_date.isoformat(), "2026-11-01")


class UrlSafetyTests(TestCase):
    """
    Regression tests for the SSRF guard (scraper/services/url_safety.py). These use
    IP-literal URLs so ipaddress parsing happens with no real DNS lookup — fast and
    deterministic in CI. The "public host" cases mock socket.getaddrinfo instead of
    depending on real DNS resolution of an external domain.
    """

    def test_rejects_loopback(self):
        ok, reason = check_public_url("http://127.0.0.1/")
        self.assertFalse(ok)
        self.assertIn("127.0.0.1", reason)

    def test_rejects_localhost_hostname(self):
        ok, _ = check_public_url("http://localhost:8000/")
        self.assertFalse(ok)

    def test_rejects_cloud_metadata_address(self):
        ok, reason = check_public_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(ok)
        self.assertIn("169.254.169.254", reason)

    def test_rejects_rfc1918_private_ranges(self):
        for host in ["10.0.0.5", "172.16.0.5", "192.168.1.5"]:
            with self.subTest(host=host):
                ok, _ = check_public_url(f"http://{host}/")
                self.assertFalse(ok)

    def test_rejects_ipv6_loopback(self):
        ok, _ = check_public_url("http://[::1]/")
        self.assertFalse(ok)

    def test_rejects_ipv4_mapped_ipv6_loopback(self):
        """Known SSRF filter bypass: ::ffff:127.0.0.1 isn't caught by IPv6Address.is_loopback."""
        ok, _ = check_public_url("http://[::ffff:127.0.0.1]/")
        self.assertFalse(ok)

    def test_rejects_disallowed_scheme(self):
        ok, reason = check_public_url("ftp://example.com/")
        self.assertFalse(ok)
        self.assertIn("scheme", reason.lower())

    def test_rejects_missing_host(self):
        ok, _ = check_public_url("http:///path")
        self.assertFalse(ok)

    def test_accepts_public_host(self):
        with patch("scraper.services.url_safety.socket.getaddrinfo") as mock_resolve:
            mock_resolve.return_value = [(2, 1, 6, "", ("93.184.216.34", 0))]
            ok, reason = check_public_url("https://example.com/events")
        self.assertTrue(ok, reason)

    def test_rejects_dns_rebinding_to_private_ip(self):
        """A hostname that resolves to a private address must be rejected even
        though its scheme/format look completely normal."""
        with patch("scraper.services.url_safety.socket.getaddrinfo") as mock_resolve:
            mock_resolve.return_value = [(2, 1, 6, "", ("10.1.2.3", 0))]
            ok, reason = check_public_url("https://attacker-controlled.example/")
        self.assertFalse(ok)
        self.assertIn("10.1.2.3", reason)


class FetchHtmlSsrfTests(TestCase):
    """fetch_html is the real enforcement boundary: it re-validates on every
    request, including redirect hops, closing the TOCTOU gap that target-creation
    -time-only validation would leave open."""

    def test_refuses_to_fetch_private_url_directly(self):
        with self.assertRaises(ValueError):
            fetch_html("http://127.0.0.1/admin")

    @patch("scraper.services.fetch.requests.get")
    def test_follows_safe_redirect_chain(self, mock_get):
        with patch("scraper.services.fetch.check_public_url", return_value=(True, "")):
            redirect_resp = type(
                "R",
                (),
                {
                    "is_redirect": True,
                    "is_permanent_redirect": False,
                    "headers": {"Location": "https://example.com/final"},
                },
            )()
            final_resp = type(
                "R",
                (),
                {
                    "is_redirect": False,
                    "is_permanent_redirect": False,
                    "headers": {},
                    "text": "<html>ok</html>",
                    "raise_for_status": lambda self=None: None,
                },
            )()
            mock_get.side_effect = [redirect_resp, final_resp]
            html = fetch_html("https://example.com/start")
        self.assertEqual(html, "<html>ok</html>")
        self.assertEqual(mock_get.call_count, 2)

    @patch("scraper.services.fetch.requests.get")
    def test_refuses_redirect_to_private_address(self, mock_get):
        redirect_resp = type(
            "R",
            (),
            {
                "is_redirect": True,
                "is_permanent_redirect": False,
                "headers": {"Location": "http://169.254.169.254/latest/meta-data/"},
            },
        )()
        with patch(
            "scraper.services.fetch.check_public_url",
            side_effect=[(True, ""), (False, "blocked: private address")],
        ):
            mock_get.return_value = redirect_resp
            with self.assertRaises(ValueError):
                fetch_html("https://example.com/start")
        # Only the first hop's GET should have been attempted — the second hop
        # must be rejected before requests.get is ever called for it.
        self.assertEqual(mock_get.call_count, 1)
