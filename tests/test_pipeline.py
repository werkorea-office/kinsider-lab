"""Self-tests run before every publish. Fake API responses are used ONLY here,
inside a temporary directory; they can never reach the published site."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from pipeline import build, cards, collect, datalab, metrics

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 18, 7, 0, tzinfo=KST)


def fake_fetch_factory(fail_keywords=()):
    def fake_fetch(url, headers, category, keywords, start, end):
        if any(k in fail_keywords for k in keywords):
            raise datalab.DataLabError("simulated outage")
        dates = metrics.date_range(start, end)
        out = {}
        for n, kw in enumerate(keywords):
            # anchor flat at 50; others rise for the last week so momentum is positive
            out[kw] = {d: (50.0 if n == 0 else 10.0 + n + (8.0 if i >= len(dates) - 7 else 0.0))
                       for i, d in enumerate(dates)}
        return out
    return fake_fetch


class Sandbox:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "config").mkdir()
        (root / "config" / "watchlist.json").write_text(collect.CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
        self.saved = {k: getattr(collect, k) for k in ("ROOT", "CONFIG", "DATA", "DAILY", "LATEST", "HISTORY")}
        self.saved_build = (build.ROOT, build.DATA)
        collect.ROOT, collect.CONFIG = root, root / "config" / "watchlist.json"
        collect.DATA = root / "data"
        collect.DAILY, collect.LATEST, collect.HISTORY = root / "data" / "daily", root / "data" / "latest.json", root / "data" / "history.csv"
        build.ROOT, build.DATA = root, root / "data"
        self.root = root
        return self

    def __exit__(self, *a):
        for k, v in self.saved.items():
            setattr(collect, k, v)
        build.ROOT, build.DATA = self.saved_build
        self.tmp.cleanup()


CREDS = ("https://example.invalid", {})


class MetricsTest(unittest.TestCase):
    def test_normalize_uses_anchor_mean(self):
        dates = ["2026-01-01", "2026-01-02"]
        out = metrics.normalize_batch({"a": {"2026-01-01": 50, "2026-01-02": 50},
                                       "b": {"2026-01-01": 25}}, "a", dates)
        self.assertEqual(out["a"], [100.0, 100.0])
        self.assertEqual(out["b"], [50.0, 0.0])  # missing day counts as zero, never interpolated

    def test_zero_anchor_rejected(self):
        with self.assertRaises(ValueError):
            metrics.normalize_batch({"a": {}}, "a", ["2026-01-01"])

    def test_momentum(self):
        m = metrics.keyword_metrics([10.0] * 28 + [20.0] * 7, 7, 28, 1.0)
        self.assertEqual(m["momentum"], 1.0)
        low = metrics.keyword_metrics([0.1] * 35, 7, 28, 1.0)
        self.assertIsNone(low["momentum"])  # too little volume to rank


class CollectTest(unittest.TestCase):
    def test_no_credentials_publishes_nothing_numeric(self):
        with Sandbox() as sb:
            original = datalab.credentials_from_env
            collect.datalab.credentials_from_env = lambda: None
            try:
                self.assertEqual(collect.main(now=NOW), 0)
            finally:
                collect.datalab.credentials_from_env = original
            snap = json.loads(collect.LATEST.read_text(encoding="utf-8"))
            self.assertEqual(snap["status"], "not_configured")
            build.build()
            home = (sb.root / "index.html").read_text(encoding="utf-8")
            self.assertIn("first daily brief is published", home)
            self.assertNotIn("Rising in Korea", home)

    def test_full_run_and_build(self):
        with Sandbox() as sb:
            self.assertEqual(collect.main(now=NOW, fetch=fake_fetch_factory(), creds=CREDS), 0)
            snap = json.loads(collect.LATEST.read_text(encoding="utf-8"))
            self.assertEqual(snap["run_date"], "2026-11-18")
            beauty = snap["segments"][0]
            self.assertEqual(beauty["data_end"], "2026-11-17")
            self.assertTrue(all(i["momentum"] is not None for i in beauty["items"] if not i["is_anchor"]))
            build.build()
            home = (sb.root / "index.html").read_text(encoding="utf-8")
            self.assertIn("Rising in Korea", home)
            self.assertTrue((sb.root / "brief" / "2026-11-18.html").exists())
            seg = json.loads(collect.LATEST.read_text(encoding="utf-8"))["segments"][0]
            out = sb.root / "card.png"
            cards.render(snap, seg, out)
            self.assertGreater(out.stat().st_size, 10000)

    def test_partial_outage_keeps_old_data_marked_stale(self):
        with Sandbox() as sb:
            collect.main(now=NOW, fetch=fake_fetch_factory(), creds=CREDS)
            nxt = NOW + dt.timedelta(days=1)
            rc = collect.main(now=nxt, fetch=fake_fetch_factory(fail_keywords=("라면",)), creds=CREDS)
            self.assertEqual(rc, 0)
            snap = json.loads(collect.LATEST.read_text(encoding="utf-8"))
            food = [s for s in snap["segments"] if s["id"] == "food"][0]
            self.assertFalse(food["fresh"])
            self.assertEqual(food["data_end"], "2026-11-17")  # real old date, not relabelled

    def test_total_outage_changes_nothing(self):
        with Sandbox() as sb:
            collect.main(now=NOW, fetch=fake_fetch_factory(), creds=CREDS)
            before = collect.LATEST.read_text(encoding="utf-8")
            rc = collect.main(now=NOW + dt.timedelta(days=1),
                              fetch=fake_fetch_factory(fail_keywords=("선크림", "라면")), creds=CREDS)
            self.assertEqual(rc, 1)
            self.assertEqual(collect.LATEST.read_text(encoding="utf-8"), before)


class RankingFloorTest(unittest.TestCase):
    def test_low_volume_terms_never_ranked(self):
        seg = {"items": [
            {"is_anchor": False, "level": 5.0, "momentum": 2.0, "en": "tiny"},
            {"is_anchor": False, "level": 50.0, "momentum": 0.3, "en": "big"},
            {"is_anchor": False, "level": 3.0, "momentum": -0.9, "en": "tiny2"},
        ]}
        rising, cooling, _ = build.ranked(seg)
        self.assertEqual([i["en"] for i in rising], ["big"])
        self.assertEqual(cooling, [])


class ResponseParsingTest(unittest.TestCase):
    def test_rejects_unexpected_shape(self):
        with self.assertRaises(datalab.DataLabError):
            datalab.parse_response({"results": []}, ["a"])


if __name__ == "__main__":
    unittest.main()


class InstagramSafetyTest(unittest.TestCase):
    def test_no_token_never_posts(self):
        import os
        from pipeline import social_instagram
        saved = os.environ.pop("IG_ACCESS_TOKEN", None)
        try:
            self.assertEqual(social_instagram.publish(), 0)
        finally:
            if saved is not None:
                os.environ["IG_ACCESS_TOKEN"] = saved


class LinkedInSafetyTest(unittest.TestCase):
    def test_no_token_never_posts(self):
        import os
        from pipeline import social_linkedin
        saved = os.environ.pop("LINKEDIN_ACCESS_TOKEN", None)
        try:
            self.assertEqual(social_linkedin.publish(), 0)
        finally:
            if saved is not None:
                os.environ["LINKEDIN_ACCESS_TOKEN"] = saved
