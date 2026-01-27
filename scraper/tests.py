from django.test import TestCase

from scraper.services.hashing import canonical_json, sha256_of_obj
from scraper.services.normalize import parse_date, parse_datetime


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
