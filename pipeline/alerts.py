"""Breakout alerts by email (Kit). Run: python -m pipeline.alerts [--setup]

--setup  makes sure the Kit tag "Breakout alerts" exists and stores its id in
         data/kit.json, so the site forms can offer the opt-in checkbox.
(default) after the daily collection: if today's run made new breakout calls,
         send one email (all of today's calls together) to subscribers tagged
         "Breakout alerts". Never more than one alert a day; each day is sent at
         most once (data/alerts.json). Without KIT_API_KEY it does nothing.

Alerts carry facts only: the term, its rise, what it is, and the call rule.
"""
import datetime as dt
import html
import json
import os
import sys
from pathlib import Path

from . import build, signals
from .newsletter import FONT, INK, MUTED, ACCENT, UP, h2, kit, p, rows_html, SITE

ROOT = Path(__file__).resolve().parent.parent
KIT_FILE = ROOT / "data" / "kit.json"
LEDGER = ROOT / "data" / "alerts.json"
TAG_NAME = "Breakout alerts"
e = html.escape


def setup(key):
    tags = kit("GET", "/v4/tags?per_page=1000", key).get("tags", [])
    tag = next((t for t in tags if t.get("name") == TAG_NAME), None)
    if not tag:
        tag = kit("POST", "/v4/tags", key, {"name": TAG_NAME}).get("tag", {})
    if not tag.get("id"):
        raise RuntimeError("Kit did not return a tag id")
    info = json.loads(KIT_FILE.read_text()) if KIT_FILE.exists() else {}
    if info.get("alert_tag_id") != tag["id"]:
        info["alert_tag_id"] = tag["id"]
        KIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        KIT_FILE.write_text(json.dumps(info, indent=1))
    print(f"Kit tag '{TAG_NAME}' ready (id {tag['id']}).")
    sync_optins(key, tag["id"])
    return tag["id"]


def sync_optins(key, tag_id):
    """Site forms record the opt-in as custom field alerts=yes; tag those subscribers (documented API only)."""
    fields = {f.get("key") for f in kit("GET", "/v4/custom_fields", key).get("custom_fields", [])}
    if "alerts" not in fields:
        kit("POST", "/v4/custom_fields", key, {"label": "Alerts"})
        return
    tagged, cursor = 0, None
    while True:
        res = kit("GET", "/v4/subscribers?status=active&per_page=1000" + (f"&after={cursor}" if cursor else ""), key)
        for sub in res.get("subscribers", []):
            if (sub.get("fields") or {}).get("alerts") == "yes":
                kit("POST", f"/v4/tags/{tag_id}/subscribers/{sub['id']}", key, {})
                tagged += 1
        pg = res.get("pagination", {})
        if not pg.get("has_next_page"):
            break
        cursor = pg.get("end_cursor")
    print(f"Breakout-alert opt-ins tagged: {tagged}")


def change_of(x):
    return x["level_at_call"] / x["early_baseline"] - 1 if x.get("early_baseline") else x.get("momentum_at_call") or 0


def build_alert(calls, day):
    calls = sorted(calls, key=change_of, reverse=True)
    top = calls[0]
    if len(calls) == 1:
        subject = f"Breakout in Korea: {top['en']} {build.pct(change_of(top))}"
    else:
        subject = f"{len(calls)} breakout signals in Korea today, led by {top['en']} {build.pct(change_of(top))}"
    rows = [(x["en"], f"{x['segment_title']} · {x['type']} · searched as {x['kw']}" if x["kw"] != x["en"]
             else f"{x['segment_title']} · {x['type']}", build.pct(change_of(x)), UP,
             f"{SITE}/term/{build.slug(x['segment'], x['en'])}.html") for x in calls]
    notes = ""
    for x in calls[:3]:
        n = build.note_for(x["segment"], x["kw"])
        if n:
            notes += p(f"<b>{e(x['en'])}</b>: {e(n)}", 15, MUTED)
    body = (
        f'<p style="{FONT}margin:0 0 6px;font-size:12px;font-weight:700;letter-spacing:.08em;color:{ACCENT}">'
        f'K-INSIDER LAB · BREAKOUT ALERT · {build.nice_date(day).upper()}</p>'
        f'<h1 style="{FONT}margin:0 0 14px;font-size:26px;line-height:1.2;color:{INK}">{e(subject)}</h1>'
        + p("These Korean shopping searches just held a rise for two weeks running: the last 7 days are at least "
            "25% above their 3-week base, and the week before was already up 10%. One-week spikes do not count.", 15, MUTED)
        + rows_html(rows) + notes
        + h2("What happens next", "TRACK RECORD")
        + p("Every call is checked after 7, 14 and 28 days and stays public, hits and misses: "
            f'<a href="{SITE}/signals.html" style="color:{ACCENT};font-weight:700">see the ledger</a>.', 15)
        + p("You get this because you asked for breakout alerts from K-INSIDER LAB. At most one alert a day.", 12, MUTED)
    )
    return subject, body


def main(setup_only=False):
    key = os.environ.get("KIT_API_KEY", "").strip()
    if not key:
        print("KIT_API_KEY not set; no alerts.")
        return 0
    tag_id = setup(key)
    if setup_only:
        return 0
    latest = ROOT / "data" / "latest.json"
    if not latest.exists():
        return 0
    day = json.loads(latest.read_text(encoding="utf-8"))["run_date"]
    calls = signals.new_on(signals.load(), day)
    if not calls:
        print(f"No new breakout calls on {day}; no alert.")
        return 0
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"alerts": []}
    if any(a["date"] == day for a in ledger["alerts"]):
        print(f"Alert for {day} already sent.")
        return 0
    subject, body = build_alert(calls, day)
    now = dt.datetime.now(dt.timezone.utc)
    res = kit("POST", "/v4/broadcasts", key, {
        "subject": subject, "preview_text": "A two-week rise in Korean shopping searches, called today.",
        "content": body, "description": f"Breakout alert {day}", "public": False,
        "published_at": now.isoformat(timespec="seconds"),
        "send_at": (now + dt.timedelta(minutes=15)).isoformat(timespec="seconds"),
        "subscriber_filter": [{"all": [{"type": "tag", "ids": [tag_id]}], "any": None, "none": None}],
    })
    b = res.get("broadcast", res)
    ledger["alerts"].append({"date": day, "broadcast": b.get("id"), "calls": [x["id"] for x in calls], "subject": subject})
    LEDGER.write_text(json.dumps(ledger, indent=1))
    print(f"Breakout alert scheduled ({len(calls)} call(s)): {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main(setup_only="--setup" in sys.argv))
