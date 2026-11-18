"""Daily asset ledger. Run: python -m pipeline.assets

Records the numbers that make K-INSIDER LAB worth something to a buyer or
partner, one row per KST day in data/assets.csv:

  site visitors (today / all time), weekly-brief subscribers (confirmed / pending),
  Instagram followers and posts, LinkedIn posts published, breakout calls and hits.

Each source is optional; a missing key or an outage leaves that cell empty and
never fails the run. Values are counts only — no subscriber addresses.
"""
import csv
import datetime as dt
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "assets.csv"
KST = dt.timezone(dt.timedelta(hours=9))
FIELDS = ["date", "visitors_today", "visitors_total", "subscribers_confirmed", "subscribers_pending",
          "ig_followers", "ig_posts", "linkedin_posts", "breakout_calls", "breakout_hits"]


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers={"Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def visitors():
    j = get_json("https://kinsider-visitors.werkorea-office.workers.dev/")
    return j.get("today"), j.get("total")


def subscribers():
    key = os.environ.get("KIT_API_KEY", "").strip()
    if not key:
        return None, None
    h = {"X-Kit-Api-Key": key}
    def count(status):
        n, cursor = 0, None
        while True:
            url = f"https://api.kit.com/v4/subscribers?status={status}&per_page=1000" + (f"&after={cursor}" if cursor else "")
            j = get_json(url, h)
            n += len(j.get("subscribers", []))
            pg = j.get("pagination", {})
            if not pg.get("has_next_page"):
                return n
            cursor = pg.get("end_cursor")
    return count("active"), count("inactive")


def instagram():
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not token:
        return None, None
    j = get_json(f"https://graph.instagram.com/v23.0/me?fields=followers_count,media_count&access_token={token}")
    return j.get("followers_count"), j.get("media_count")


def local_counts():
    li = ROOT / "data" / "social" / "linkedin.json"
    li_posts = len(json.loads(li.read_text())["posts"]) if li.exists() else 0
    sig = ROOT / "data" / "signals.json"
    calls = hits = 0
    if sig.exists():
        for x in json.loads(sig.read_text())["signals"]:
            calls += 1
            checks = x.get("checks") or {}
            last = checks.get("d28") or checks.get("d14") or checks.get("d7")
            hits += 1 if last and last.get("change", 0) > 0 else 0
    return li_posts, calls, hits


def safe(fn):
    try:
        return fn()
    except Exception as err:  # one source down must not lose the rest of the row
        print(f"{fn.__name__} unavailable: {str(err)[:120]}")
        return None, None


def main():
    today = dt.datetime.now(KST).date().isoformat()
    v_today, v_total = safe(visitors)
    s_conf, s_pend = safe(subscribers)
    ig_f, ig_p = safe(instagram)
    li_posts, calls, hits = local_counts()
    row = {"date": today, "visitors_today": v_today, "visitors_total": v_total,
           "subscribers_confirmed": s_conf, "subscribers_pending": s_pend, "ig_followers": ig_f, "ig_posts": ig_p,
           "linkedin_posts": li_posts, "breakout_calls": calls, "breakout_hits": hits}
    rows = []
    if LEDGER.exists():
        with LEDGER.open(encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r["date"] != today]
    rows.append({k: ("" if row[k] is None else row[k]) for k in FIELDS})
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["date"]))
    print("Asset ledger:", {k: v for k, v in row.items() if k != "date"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
