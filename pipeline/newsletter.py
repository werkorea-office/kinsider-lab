"""Weekly Korea demand brief by email (Kit). Run: python -m pipeline.newsletter [--force] [--draft]

Monday's daily run builds the brief from the same verified data as the site and
schedules it in Kit for Monday 9:00 AM US Eastern (23:00 KST). Fixed structure,
so readers learn where to look:

  lead finding · K-beauty rising · brands rising · K-food rising ·
  breakout calls & results · what Korea shipped (customs) · links

Also writes newsletter/<date>.html (public web copy, linked from the email) and
keeps a ledger (data/newsletter.json) so a week is never sent twice.
Without KIT_API_KEY it only writes the web copy.
"""
import datetime as dt
import html
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from . import build

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "newsletter.json"
WEB = ROOT / "newsletter"
SITE = "https://www.kinsider-lab.com"
KST = dt.timezone(dt.timedelta(hours=9))
LAUNCH = dt.date(2026, 11, 23)  # first Monday brief = No. 1
e = html.escape

INK, MUTED, LINE, ACCENT, UP, DOWN = "#0f1420", "#667085", "#e2dfd8", "#e0521f", "#0e7a50", "#c0321f"
FONT = "font-family:Inter,Helvetica,Arial,sans-serif;"


def issue_no(day):
    return max(1, (day - LAUNCH).days // 7 + 1)


def seg(snapshot, sid):
    s = next((x for x in snapshot["segments"] if x["id"] == sid), None)
    return s if s and s.get("status") == "ok" else None


def notes():
    cfg = json.loads((ROOT / "config" / "watchlist.json").read_text(encoding="utf-8"))
    return {(s["id"], k["kw"]): k.get("note", "") for s in cfg["segments"] for k in [s["anchor"]] + s["keywords"]}


def h2(text, kicker):
    return (f'<p style="{FONT}margin:34px 0 4px;font-size:12px;font-weight:700;letter-spacing:.08em;color:{ACCENT}">'
            f'{e(kicker)}</p><h2 style="{FONT}margin:0 0 12px;font-size:22px;line-height:1.25;color:{INK}">{e(text)}</h2>')


def rows_html(rows):
    """rows: (name, sub, value_text, color, href)"""
    out = []
    for name, sub, val, color, href in rows:
        out.append(
            f'<tr><td style="{FONT}padding:10px 0;border-top:1px solid {LINE}">'
            f'<a href="{href}" style="color:{INK};font-weight:700;font-size:16px;text-decoration:none">{e(name)}</a>'
            f'<div style="color:{MUTED};font-size:13px;margin-top:2px">{e(sub)}</div></td>'
            f'<td style="{FONT}padding:10px 0;border-top:1px solid {LINE};text-align:right;font-weight:800;'
            f'font-size:18px;color:{color};white-space:nowrap">{e(val)}</td></tr>')
    return f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{"".join(out)}</table>'


def p(text, size=16, color=INK):
    return f'<p style="{FONT}margin:0 0 12px;font-size:{size}px;line-height:1.55;color:{color}">{text}</p>'


def rising_section(snapshot, sid, kicker, title, nm, n=5):
    s = seg(snapshot, sid)
    if not s:
        return "", None
    rising, cooling, _ = build.ranked(s)
    if not rising:
        return "", None
    rising = [i for i in rising if i["momentum"] >= 0.02]  # flat terms are not "rising"
    if not rising:
        return "", None
    rows = [(i["en"], f"{i['type']}" + (f" · searched as {i['kw']}" if i["kw"] != i["en"] else "")
             + f" · index {i['level']:.0f}", build.pct(i["momentum"]), UP,
             f"{SITE}/term/{build.slug(sid, i['en'])}.html") for i in rising[:n]]
    if cooling:
        c = cooling[0]
        rows.append((f"Cooling: {c['en']}", f"{c['type']} · index {c['level']:.0f}", build.pct(c["momentum"]), DOWN,
                     f"{SITE}/term/{build.slug(sid, c['en'])}.html"))
    top = rising[0]
    note = nm.get((sid, top["kw"]), "")
    lead = p(f"<b>{e(top['en'])}</b> leads at {build.pct(top['momentum'])}. {e(note)}", 15, MUTED) if note else ""
    return h2(title, kicker) + lead + rows_html(rows), top


def signals_section(run):
    led = build.load_signals()
    new = [x for x in led["signals"] if 0 <= (run - dt.date.fromisoformat(x["called"])).days < 7]
    checked = [x for x in led["signals"] if x["checks"]]
    if not new and not checked:
        return ""
    out = h2("Breakout calls and how they did", "SIGNALS")
    out += p("A call needs a rise that holds for two weeks. Every call is checked after 7, 14 and 28 days "
             "and stays public, hits and misses.", 14, MUTED)
    if new:
        rows = [(x["en"], f"{x['segment_title']} · called {build.nice_date(x['called'])} · week vs. prior 4 weeks",
                 build.pct(x["momentum_at_call"]), ACCENT, f"{SITE}/signals.html") for x in new[:6]]
        out += p("<b>New this week</b>", 14) + rows_html(rows)
    if checked:
        def latest(x):
            k = "d28" if "d28" in x["checks"] else ("d14" if "d14" in x["checks"] else "d7")
            return k, x["checks"][k]["change"]
        rows = []
        for x in sorted(checked, key=lambda x: x["called"], reverse=True)[:6]:
            k, ch = latest(x)
            rows.append((("✓ " if ch > 0 else "✗ ") + x["en"], f"called {build.nice_date(x['called'])} · {k[1:]} days later",
                         build.pct(ch), UP if ch > 0 else DOWN, f"{SITE}/signals.html"))
        out += p("<b>Results so far</b>", 14) + rows_html(rows)
    return out


def exports_section():
    ex = build.load_exports()
    if not ex or not ex.get("latest_month"):
        return ""
    rows = [(r["country"], f"{build.month_label(ex['latest_month'])} · last 12 months {build.usd(r['last12'])}",
             f"{build.usd(r['now'])}  {build.pct(r['yoy'])}", UP if (r["yoy"] or 0) >= 0 else DOWN, f"{SITE}/exports.html")
            for r in build.export_rows(ex, "3304")[:5]]
    return (h2("What Korea actually shipped", "EXPORTS · KOREA CUSTOMS")
            + p("Skin care &amp; make-up (HS 3304) exports by destination, with change vs. the same month a year before.",
                14, MUTED) + rows_html(rows))


def creator_section(items):
    """Ready-to-film angles for creators and sellers: the Korean search term is the research shortcut."""
    items = [i for i in items if i]
    if not items:
        return ""
    lines = "".join(
        p(f"<b>{e(i['en'])}</b> ({e(i['kw'])}), {build.pct(i['momentum'])} in Korean shopping searches. "
          f"Angle: \"What Koreans are buying right now: {e(i['en'])}\". Research tip: search "
          f"<b>{e(i['kw'])}</b> on Olive Young or Naver Shopping to see the exact products Koreans are clicking.", 15)
        for i in items)
    return (h2("Content angles this week", "FOR CREATORS & SELLERS") + lines
            + p("Free to use with credit: \"Data: K-INSIDER LAB (kinsider-lab.com)\".", 13, MUTED))


def build_brief(snapshot, day):
    nm = notes()
    run = dt.date.fromisoformat(snapshot["run_date"])
    beauty, top_b = rising_section(snapshot, "beauty", "K-BEAUTY", "Products and ingredients rising in Korea", nm)
    brands, top_br = rising_section(snapshot, "brands", "K-BEAUTY BRANDS", "Brands gaining search demand", nm)
    food, top_f = rising_section(snapshot, "food", "K-FOOD", "K-food rising in Korea", nm, n=4)
    lead_item = top_b or top_br or top_f
    if not lead_item:
        return None
    no = issue_no(day)
    subject = f"Korea this week: {lead_item['en']} {build.pct(lead_item['momentum'])}"
    if top_br and top_br is not lead_item:
        subject += f", {top_br['en']} {build.pct(top_br['momentum'])}"
    preview = "What Korean shoppers searched more (and less) this week, before it reaches export shelves."
    web_url = f"{SITE}/newsletter/{day.isoformat()}.html"
    cover = f"{SITE}/newsletter/{day.isoformat()}-cover.jpg"
    body = (
        f'<p style="{FONT}margin:0 0 6px;font-size:12px;font-weight:700;letter-spacing:.08em;color:{ACCENT}">'
        f'K-INSIDER LAB WEEKLY · No. {no:03d} · {build.nice_date(day.isoformat()).upper()}</p>'
        f'<h1 style="{FONT}margin:0 0 14px;font-size:28px;line-height:1.2;color:{INK}">{e(subject.replace("Korea this week: ", "This week in Korea: "))}</h1>'
        + p("Every Monday: what is gaining ground in Korean online shopping, measured from Naver shopping-search "
            "clicks, plus official export figures. Change = last 7 days vs. the prior 28 days.", 15, MUTED)
        + (f'<a href="{SITE}"><img src="{cover}" width="100%" alt="This week\'s Korea demand signal" '
           f'style="display:block;width:100%;max-width:600px;border-radius:8px;margin:18px 0 6px"></a>' if (WEB / f"{day.isoformat()}-cover.jpg").exists() else "")
        + beauty + brands + food + creator_section([top_b, top_br, top_f]) + signals_section(run) + exports_section()
        + h2("Go deeper", "K-INSIDER LAB")
        + p(f'<a href="{SITE}" style="color:{ACCENT};font-weight:700">Daily data for every tracked term</a> · '
            f'<a href="{SITE}/reports.html" style="color:{ACCENT};font-weight:700">Monthly PDF report</a> · '
            f'<a href="{SITE}/exports.html" style="color:{ACCENT};font-weight:700">Export statistics</a>', 15)
        + p("Know a buyer, distributor or brand team who should see this? Forward it. "
            f'<a href="{web_url}" style="color:{MUTED}">View in browser</a>', 14, MUTED)
        + p("Data: Naver DataLab Shopping Insight (Korea), Korea Customs Service via data.go.kr. Index: each "
            "segment's baseline term = 100 over 8 weeks; terms below index 10 are not ranked.", 12, MUTED)
    )
    return {"subject": subject, "preview": preview, "html": body, "issue": no, "web_url": web_url}


def web_page(brief, day):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(brief['subject'])} | K-INSIDER LAB Weekly</title>
<meta name="description" content="{e(brief['preview'])}">
<link rel="canonical" href="{brief['web_url']}"><link rel="icon" href="/assets/favicon.svg">
</head><body style="margin:0;background:#f6f4ef">
<div style="max-width:640px;margin:0 auto;padding:28px 20px 60px;background:#fff">
<p style="{FONT}font-size:13px"><a href="/" style="color:{INK};font-weight:800;text-decoration:none">K-INSIDER <span style="color:{ACCENT}">LAB</span></a></p>
{brief['html']}
<p style="{FONT}margin-top:30px;font-size:15px"><a href="/#subscribe" style="color:#fff;background:{ACCENT};padding:12px 18px;border-radius:8px;text-decoration:none;font-weight:700">Get this brief every Monday, free</a></p>
</div></body></html>"""


def kit(method, path, key, body=None):
    req = urllib.request.Request("https://api.kit.com" + path, method=method,
                                 data=None if body is None else json.dumps(body).encode())
    req.add_header("X-Kit-Api-Key", key)
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"Kit HTTP {err.code}: {err.read().decode('utf-8', 'replace')[:400]}")


def ensure_fields(key):
    """Custom fields the site forms send (company, source); Kit drops unknown fields."""
    have = {f.get("key") for f in kit("GET", "/v4/custom_fields", key).get("custom_fields", [])}
    for label in ("Company", "Source"):
        if label.lower() not in have:
            kit("POST", "/v4/custom_fields", key, {"label": label})


def send_time(day):
    """Monday 9:00 AM New York time, expressed in UTC (handles daylight saving)."""
    from zoneinfo import ZoneInfo
    local = dt.datetime(day.year, day.month, day.day, 9, 0, tzinfo=ZoneInfo("America/New_York"))
    return local.astimezone(dt.timezone.utc)


def load_ledger():
    return json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {"issues": []}


def main(force=False, draft=False):
    latest = ROOT / "data" / "latest.json"
    if not latest.exists():
        print("No data; no brief.")
        return 0
    snapshot = json.loads(latest.read_text(encoding="utf-8"))
    if snapshot.get("status") != "ok":
        print("Data not configured; no brief.")
        return 0
    day = dt.datetime.now(KST).date()
    if day.weekday() != 0 and not (force or draft):
        print("Not Monday (KST); weekly brief not due.")
        return 0
    ledger = load_ledger()
    if not draft and any(x["date"] == day.isoformat() and x.get("status") == "scheduled" for x in ledger["issues"]):
        print(f"Brief for {day} already scheduled.")
        return 0
    WEB.mkdir(exist_ok=True)
    cover_src = ROOT / "cards" / snapshot["run_date"] / "01.jpg"
    if cover_src.exists():  # permanent copy: carousels are pruned after 3 weeks, emails are read later
        (WEB / f"{day.isoformat()}-cover.jpg").write_bytes(cover_src.read_bytes())
    brief = build_brief(snapshot, day)
    if not brief:
        print("Not enough fresh data for a brief.")
        return 0
    (WEB / f"{day.isoformat()}.html").write_text(web_page(brief, day), encoding="utf-8")
    key = os.environ.get("KIT_API_KEY", "").strip()
    if not key:
        print(f"Web copy written (newsletter/{day}.html); KIT_API_KEY not set, nothing sent.")
        return 0
    try:
        ensure_fields(key)
    except RuntimeError as err:
        print(f"Custom fields not checked: {err}")
    when = None if draft else send_time(day)
    if when and when < dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10):
        when = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15)
    payload = {
        "subject": brief["subject"], "preview_text": brief["preview"], "content": brief["html"],
        "description": f"Weekly brief No. {brief['issue']:03d} ({day})", "public": True,
        "published_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "send_at": when.isoformat(timespec="seconds") if when else None,
    }
    res = kit("POST", "/v4/broadcasts", key, payload)
    b = res.get("broadcast", res)
    status = "draft" if draft else "scheduled"
    if not draft:
        ledger["issues"].append({"date": day.isoformat(), "issue": brief["issue"], "broadcast": b.get("id"),
                                 "send_at": payload["send_at"], "subject": brief["subject"], "status": status})
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(ledger, indent=1), encoding="utf-8")
    print(f"Kit broadcast {b.get('id')} {status}: {brief['subject']} (send_at {payload['send_at']})")
    return 0


def status():
    """Prints list health: subscriber states (no addresses) and sender setup."""
    key = os.environ.get("KIT_API_KEY", "").strip()
    if not key:
        print("KIT_API_KEY not set.")
        return 1
    acct = kit("GET", "/v4/account", key)
    a = acct.get("account", {})
    print(f"Account plan: {a.get('plan_type')}, primary email set: {bool(a.get('primary_email_address'))}")
    counts = {}
    for state in ("active", "inactive", "bounced", "complained", "cancelled"):
        res = kit("GET", f"/v4/subscribers?status={state}&per_page=500", key)
        counts[state] = len(res.get("subscribers", []))
    print("Subscribers by state:", counts)
    for b in kit("GET", "/v4/broadcasts?per_page=10", key).get("broadcasts", []):
        print(f"Broadcast {b.get('id')}: {b.get('subject')!r} send_at={b.get('send_at')} public={b.get('public')}")
    return 0


if __name__ == "__main__":
    if "--status" in sys.argv:
        sys.exit(status())
    sys.exit(main(force="--force" in sys.argv, draft="--draft" in sys.argv))
