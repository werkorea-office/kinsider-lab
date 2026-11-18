"""Static site generator. Run: python -m pipeline.build

Reads data/latest.json and data/daily/*.json and writes the public site into
the repository root (served by GitHub Pages). Every sentence is produced from
numbers by fixed templates: no AI-written claims, nothing that isn't in the data.
"""
import datetime as dt
import html
import json
from pathlib import Path
from email.utils import format_datetime

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE_URL = "https://www.kinsider-lab.com"
BRAND = "K-INSIDER LAB"
FORM_ACTION = "https://formspree.io/f/mjygjowd"
KST = dt.timezone(dt.timedelta(hours=9))

e = html.escape


# ---------- formatting helpers ----------

def nice_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def pct(m):
    if m is None:
        return "–"
    v = m * 100
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.0f}%"


def pct_class(m):
    if m is None:
        return "flat"
    if m >= 0.05:
        return "up"
    if m <= -0.05:
        return "down"
    return "flat"


def sparkline(series, w=120, h=28):
    if not series:
        return ""
    # weekly averages smooth out weekday noise
    weeks = [sum(series[i:i + 7]) / len(series[i:i + 7]) for i in range(0, len(series), 7)]
    lo, hi = min(weeks), max(weeks)
    span = (hi - lo) or 1.0
    n = len(weeks)
    pts = []
    for i, v in enumerate(weeks):
        x = 2 + (w - 4) * (i / (n - 1 if n > 1 else 1))
        y = h - 3 - (h - 6) * ((v - lo) / span)
        pts.append(f"{x:.1f},{y:.1f}")
    last = pts[-1].split(",")
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="8-week trend"><polyline points="{" ".join(pts)}" fill="none" '
            f'stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
            f'<circle cx="{last[0]}" cy="{last[1]}" r="2.4" fill="currentColor"/></svg>')


# ---------- data views ----------

def slug(seg_id, en):
    import re
    return seg_id + "-" + re.sub(r"[^a-z0-9]+", "-", en.lower()).strip("-")


def rank_min_level():
    cfg = json.loads((ROOT / "config" / "watchlist.json").read_text(encoding="utf-8"))
    return float(cfg.get("rank_min_level", 0))


def ranked(seg):
    # Low-volume terms swing wildly in % terms; they are kept in the data but never ranked.
    floor = rank_min_level()
    items = [i for i in seg["items"] if not i["is_anchor"] and i["level"] >= floor]
    rising = sorted([i for i in items if i["momentum"] is not None and i["momentum"] > 0],
                    key=lambda i: i["momentum"], reverse=True)
    cooling = sorted([i for i in items if i["momentum"] is not None and i["momentum"] < 0],
                     key=lambda i: i["momentum"])
    biggest = sorted(seg["items"], key=lambda i: i["level"], reverse=True)
    return rising, cooling, biggest


def headline(snapshot):
    for seg in snapshot.get("segments", []):
        if seg["id"] == "beauty" and seg.get("status") == "ok":
            rising, _, _ = ranked(seg)
            if rising:
                top = rising[0]
                return (f"{top['en']} leads Korea's rising beauty searches, "
                        f"{pct(top['momentum'])} vs. the prior four weeks")
    return "Korea consumer demand brief"


# ---------- page shell ----------

CSS_VERSION = "7"


def page(title, body, description, path, extra_head=""):
    canonical = SITE_URL + path
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-site-verification" content="IPej6igUojUVcGnqx8ramo7kEpV0j911z2cvqXVXMqk">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonical}">
<link rel="alternate" type="application/rss+xml" title="{BRAND} daily brief" href="/feed.xml">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/style.css?v={CSS_VERSION}">
{extra_head}
</head>
<body>
<header class="top">
  <div class="wrap top-in">
    <a class="logo" href="/"><span class="mark">K</span><span>K-INSIDER <b>LAB</b></span></a>
    <nav>
      <a href="/">Today</a>
      <a href="/signals.html">Signals</a>
      <a href="/exports.html">Exports</a>
      <a href="/reports.html">Reports</a>
      <a href="/archive.html">Archive</a>
      <a href="/methodology.html">Methodology</a>
      <a class="btn-sm" href="/#subscribe">Get the weekly brief</a>
    </nav>
  </div>
</header>
<main>
{body}
</main>
<footer class="foot">
  <div class="wrap foot-in">
    <div>
      <div class="logo small"><span class="mark">K</span><span>K-INSIDER <b>LAB</b></span></div>
      <p>Daily, data-sourced signals on what Korean consumers are shopping for.</p>
    </div>
    <div class="foot-meta">
      <p>Source data: Naver DataLab Shopping Insight. Indices are calculated by {BRAND};
      {BRAND} is not affiliated with or endorsed by Naver.</p>
      <p>Operated by 디시전에스 (DecisionS), Chungju, Republic of Korea.</p>
      <p><a href="/methodology.html">Methodology &amp; limits</a> · <a href="/feed.xml">RSS</a></p>
      <p class="visits" id="kl-visits">Visitors today <b id="kl-today">–</b> · All-time <b id="kl-total">–</b></p>
    </div>
  </div>
</footer>
<script>
/* Daily visitor counter: one count per browser per day (KST), counted by a Cloudflare Worker. */
(function () {{
  var api = "https://kinsider-visitors.werkorea-office.workers.dev";
  var day = new Date(Date.now() + 9 * 3600000).toISOString().slice(0, 10);
  var seen = null;
  try {{ seen = localStorage.getItem("kl_seen"); }} catch (e) {{}}
  var first = seen !== day;
  fetch(api + (first ? "/hit" : "/"), {{ method: first ? "POST" : "GET" }})
    .then(function (r) {{ return r.ok ? r.json() : Promise.reject(r.status); }})
    .then(function (j) {{
      if (first) {{ try {{ localStorage.setItem("kl_seen", day); }} catch (e) {{}} }}
      document.getElementById("kl-today").textContent = Number(j.today).toLocaleString("en-US");
      document.getElementById("kl-total").textContent = Number(j.total).toLocaleString("en-US");
    }})
    .catch(function () {{ document.getElementById("kl-visits").style.display = "none"; }});
}})();
</script>
</body>
</html>
"""


def subscribe_block():
    return f"""
<section class="subscribe" id="subscribe">
  <div class="wrap sub-in">
    <div>
      <h2>The weekly Korea demand brief</h2>
      <p>Every Monday: the categories and ingredients gaining ground in Korean online shopping,
      before they reach export shelves. Free for buyers, distributors and brand teams.</p>
    </div>
    <form action="{FORM_ACTION}" method="POST" class="sub-form">
      <input type="hidden" name="_subject" value="K-INSIDER LAB weekly brief signup">
      <input type="hidden" name="form" value="weekly-brief">
      <label class="sr" for="email">Business email</label>
      <input id="email" type="email" name="email" required placeholder="you@company.com">
      <input type="text" name="company" placeholder="Company (optional)">
      <button type="submit">Subscribe</button>
    </form>
  </div>
</section>"""


# ---------- sections ----------

def table(items, seg, limit, show_rank=True):
    anchor_en = seg["anchor"]["en"]
    rows = []
    for n, it in enumerate(items[:limit], 1):
        tag = ' <span class="anchor-tag">baseline</span>' if it["is_anchor"] else ""
        rows.append(f"""<tr>
  {'<td class="rank">' + str(n) + '</td>' if show_rank else ''}
  <td class="kw"><a class="en" href="/term/{slug(seg['id'], it['en'])}.html">{e(it['en'])}</a>{tag}<span class="kr" lang="ko">{e(it['kw'])}</span></td>
  <td class="type">{e(it['type'])}</td>
  <td class="num {pct_class(it['momentum'])}">{pct(it['momentum'])}</td>
  <td class="num">{it['level']:.0f}</td>
  <td class="trend {pct_class(it['momentum'])}">{sparkline(it['series'])}</td>
</tr>""")
    head_rank = "<th>#</th>" if show_rank else ""
    return f"""<div class="tbl-wrap"><table class="rank-tbl">
<thead><tr>{head_rank}<th>{'Brand' if seg['id'] == 'brands' else 'Search term'}</th><th>Type</th>
<th class="num" title="Average of the last 7 days vs. the 28 days before">Momentum</th>
<th class="num" title="Shopping-search clicks; {e(anchor_en)} 8-week average = 100">Demand index</th>
<th>8 weeks</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>"""


def segment_block(seg, primary, mode=None):
    rising, cooling, biggest = ranked(seg)
    stale = ""
    if seg.get("fresh") is False:
        stale = (f'<p class="stale">This section could not be refreshed today. '
                 f'Showing the last verified data (through {nice_date(seg["data_end"])}).</p>')
    period = f"Naver shopping-search data, {nice_date(seg['data_start'])} – {nice_date(seg['data_end'])}"
    parts = [f'<section class="seg"><div class="wrap">',
             f'<div class="seg-head"><h2>{e(seg["title"])}</h2><p class="period">{e(period)}</p></div>',
             stale]
    if mode == "brands":
        if rising:
            parts.append('<h3>Brands rising in Korea</h3>')
            parts.append(table(rising, seg, 10))
        parts.append('<h3>Most searched brands</h3>')
        parts.append(table(biggest, seg, 10))
    elif rising:
        parts.append('<h3>Rising in Korea</h3>')
        parts.append(table(rising, seg, 10 if primary else 6))
    if primary and mode != "brands":
        parts.append('<h3>Largest demand right now</h3>')
        parts.append(table(biggest, seg, 8))
        if cooling:
            parts.append('<h3>Cooling</h3>')
            parts.append(table(cooling, seg, 5))
    parts.append(f'<p class="note">Demand index: shopping-search clicks in Naver\'s '
                 f'“{e(seg["category_name_kr"])}” category, where {e(seg["anchor"]["en"])}\'s '
                 f'8-week average = 100. Momentum compares the last 7 days with the 28 days before. '
                 f'<a href="/methodology.html">How this is calculated</a></p>')
    parts.append('</div></section>')
    return "\n".join(parts)


def summary_points(snapshot):
    pts = []
    for seg in snapshot.get("segments", []):
        if seg.get("status") != "ok":
            continue
        rising, cooling, biggest = ranked(seg)
        if rising:
            names = ", ".join(f"{i['en']} ({pct(i['momentum'])})" for i in rising[:3])
            pts.append(f"<li><b>{e(seg['title'])} rising:</b> {e(names)}</li>")
        if cooling:
            c = cooling[0]
            pts.append(f"<li><b>{e(seg['title'])} cooling most:</b> {e(c['en'])} ({pct(c['momentum'])})</li>")
    return "".join(pts)


def brief_body(snapshot, is_home):
    if snapshot.get("status") != "ok":
        return f"""
<section class="hero"><div class="wrap">
  <p class="eyebrow">Korea consumer demand · launching</p>
  <h1>See what Korea is shopping for, before it ships abroad.</h1>
  <p class="lede">{BRAND} turns Korean online-shopping search data into a daily demand index
  for K-beauty and K-food categories and ingredients. Built for importers, distributors and brand teams.</p>
  <div class="notice">The first daily brief is published as soon as the data connection goes live.
  Every number on this site will come from Naver DataLab and be dated. Nothing is estimated or filled in.</div>
</div></section>
{subscribe_block()}"""

    run = snapshot["run_date"]
    title = headline(snapshot)
    segs = snapshot["segments"]
    body = [f"""
<section class="hero"><div class="wrap">
  <p class="eyebrow">{'Today’s brief' if is_home else 'Daily brief'} · {nice_date(run)}</p>
  <h1>{e(title)}</h1>
  <ul class="points">{summary_points(snapshot)}</ul>
  <p class="lede small">Measured daily from Korean shopping-search clicks. Each brief is archived, so trends can be checked later.</p>
</div></section>"""]
    for i, seg in enumerate(segs):
        if i == 1 and is_home:
            body.append(breakout_block(snapshot))
        body.append(segment_block(seg, primary=(i == 0), mode="brands" if seg["id"] == "brands" else None))
        if seg["id"] == "brands" and is_home:
            body.append(exports_block())
    if is_home:
        body.append(subscribe_block())
    else:
        body.append(f'<section class="seg"><div class="wrap"><p><a href="/archive.html">← All daily briefs</a> · '
                    f'<a href="/data/daily/{run}.json">Raw data for this brief (JSON)</a></p></div></section>')
    return "\n".join(body)


def load_signals():
    path = DATA / "signals.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"signals": []}


def breakout_block(snapshot):
    led = load_signals()
    run = dt.date.fromisoformat(snapshot["run_date"])
    active = [x for x in led["signals"] if (run - dt.date.fromisoformat(x["called"])).days <= 28]
    active.sort(key=lambda x: x["called"], reverse=True)
    if active:
        rows = "".join(
            f"<tr><td class=\"num\">{nice_date(x['called'])}</td>"
            f"<td class=\"kw\"><a class=\"en\" href=\"/term/{slug(x['segment'], x['en'])}.html\">{e(x['en'])}</a>"
            f"<span class=\"kr\" lang=\"ko\">{e(x['kw'])}</span></td><td class=\"type\">{e(x['segment_title'])}</td>"
            f"<td class=\"num\">{x['level_at_call']:.0f}</td><td class=\"num\">{x['latest']['level']:.0f}</td>"
            f"<td class=\"num {pct_class(x['latest']['level'] / x['level_at_call'] - 1)}\">"
            f"{pct(x['latest']['level'] / x['level_at_call'] - 1)}</td></tr>" for x in active[:10])
        table_html = (f'<div class="tbl-wrap"><table><thead><tr><th class="num">Called</th><th>Term</th><th>Segment</th>'
                      f'<th class="num">Index at call</th><th class="num">Index now</th><th class="num">Since call</th>'
                      f'</tr></thead><tbody>{rows}</tbody></table></div>')
    else:
        table_html = '<p class="note">No term meets the breakout rule today. Calls are only made when a rise lasts two weeks.</p>'
    return f"""<section class="seg signals"><div class="wrap">
<div class="seg-head"><h2>Breakout signals</h2><p class="period">Two-week rises, called on the day and tracked publicly</p></div>
{table_html}
<p class="note">Every call is kept in a public ledger with its result after 7, 14 and 28 days, including the ones that faded.
<a href="/signals.html">See the full track record</a></p></div></section>"""


def signals_page():
    led = load_signals()
    sigs = sorted(led["signals"], key=lambda x: x["called"], reverse=True)

    def cell(x, k):
        c = x["checks"].get(k)
        return f'<td class="num {pct_class(c["change"])}">{pct(c["change"])}</td>' if c else '<td class="num flat">pending</td>'

    rows = "".join(
        f"<tr><td class=\"num\">{nice_date(x['called'])}</td>"
        f"<td class=\"kw\"><a class=\"en\" href=\"/term/{slug(x['segment'], x['en'])}.html\">{e(x['en'])}</a>"
        f"<span class=\"kr\" lang=\"ko\">{e(x['kw'])}</span></td><td class=\"type\">{e(x['segment_title'])}</td>"
        f"<td class=\"num\">{x['level_at_call']:.0f}</td>{cell(x, 'd7')}{cell(x, 'd14')}{cell(x, 'd28')}</tr>" for x in sigs)
    done = [x for x in sigs if "d28" in x["checks"]]
    held = [x for x in done if x["checks"]["d28"]["change"] >= 0]
    score = (f"<p class=\"lede small\">Calls with a 28-day result: {len(done)}. Still at or above the call level after 28 days: "
             f"{len(held)} ({(len(held) / len(done) * 100):.0f}%).</p>" if done else
             "<p class=\"lede small\">The first 28-day results appear four weeks after the first calls.</p>")
    table_html = (f'<div class="tbl-wrap"><table><thead><tr><th class="num">Called</th><th>Term</th><th>Segment</th>'
                  f'<th class="num">Index at call</th><th class="num">+7 days</th><th class="num">+14 days</th>'
                  f'<th class="num">+28 days</th></tr></thead><tbody>{rows}</tbody></table></div>'
                  if sigs else '<p>No calls yet. The ledger starts with the first term that meets the rule.</p>')
    rule = led.get("rule") or {}
    return f"""<section class="hero slim"><div class="wrap"><p class="eyebrow">Track record</p>
<h1>Every breakout call, and what happened next</h1>{score}</div></section>
<section class="seg"><div class="wrap">{table_html}
<h3>The rule</h3><p class="note">A term is called when its last 7 days are at least {rule.get('week_rise', 0.25) * 100:.0f}% above
the three weeks before the prior week, the prior week was already {rule.get('prior_week_rise', 0.1) * 100:.0f}% above that base,
the rise is still holding, and the demand index is at least {rule.get('min_level', 10):.0f}. The same term is not called again
within {rule.get('cooldown_days', 28)} days. Calls are never edited or deleted. Raw ledger:
<a href="/data/signals.json">signals.json</a>.</p></div></section>"""


def term_page(seg, it, history_rows, sigs):
    big = sparkline(it["series"], w=640, h=160)
    hist = [r for r in history_rows if r["segment"] == seg["id"] and r["keyword_kr"] == it["kw"]][-30:]
    hrows = "".join(f"<tr><td class=\"num\">{nice_date(r['run_date'])}</td><td class=\"num\">{float(r['level']):.0f}</td>"
                    f"<td class=\"num\">{pct(float(r['momentum'])) if r['momentum'] else '–'}</td></tr>" for r in reversed(hist))
    calls = [x for x in sigs if x["segment"] == seg["id"] and x["kw"] == it["kw"]]
    call_html = "".join(f"<li>Breakout called {nice_date(x['called'])} at index {x['level_at_call']:.0f}</li>" for x in calls)
    kind = "brand" if seg["id"] == "brands" else "search term"
    return f"""<section class="hero slim"><div class="wrap"><p class="eyebrow">{e(seg['title'])} · {e(it['type'])}</p>
<h1>{e(it['en'])} <span class="kr-title" lang="ko">{e(it['kw'])}</span></h1>
<p class="lede">Korean shopping-search demand for this {kind}, updated daily from Naver DataLab.</p>
<div class="stats"><div><span>Demand index (7 days)</span><b>{it['level']:.0f}</b></div>
<div><span>Momentum vs prior 4 weeks</span><b class="{pct_class(it['momentum'])}">{pct(it['momentum'])}</b></div>
<div><span>Data through</span><b>{nice_date(seg['data_end'])}</b></div></div></div></section>
<section class="seg"><div class="wrap"><h3>Last 8 weeks (weekly average)</h3>
<div class="bigchart {pct_class(it['momentum'])}">{big}</div>
{'<h3>Breakout calls</h3><ul>' + call_html + '</ul>' if calls else ''}
<h3>Daily record</h3>
{'<div class="tbl-wrap"><table><thead><tr><th class="num">Date</th><th class="num">Demand index</th><th class="num">Momentum</th></tr></thead><tbody>' + hrows + '</tbody></table></div>' if hrows else '<p class="note">The daily record starts with the first brief.</p>'}
<p class="note">Index: shopping-search clicks in Naver's “{e(seg['category_name_kr'])}” category, {e(seg['anchor']['en'])} 8-week average = 100.
<a href="/methodology.html">Methodology</a></p></div></section>"""


def reports_page():
    idx_path = ROOT / "reports" / "index.json"
    eds = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else []
    items = "".join(
        f'<li><span class="d">{e(m["title"])}</span><span>Korea K-Beauty &amp; K-Food Demand Report'
        f'{" (interim, data through " + nice_date(m["data_end"]) + ")" if m["interim"] else ""}</span>'
        f'<a class="dl" data-href="{e(m["file"])}" href="#get">PDF</a></li>' for m in eds)
    listing = f'<ul class="archive reports">{items}</ul>' if eds else '<p>The first edition is published on the 1st of the month.</p>'
    return f"""<section class="hero slim"><div class="wrap"><p class="eyebrow">Monthly report</p>
<h1>Korea K-Beauty &amp; K-Food Demand Report</h1>
<p class="lede">A monthly PDF with rising categories, ingredients and brands in Korean online shopping, the breakout
calls of the month and their track record. Free for buyers, distributors and brand teams.</p></div></section>
<section class="seg"><div class="wrap">{listing}
<div class="gate" id="get"><h3>Get the reports</h3>
<p class="note">Leave your business email once. The download links open right after, and new editions arrive by email.</p>
<form id="report-form" class="sub-form light">
<input type="email" name="email" required placeholder="you@company.com">
<input type="text" name="company" placeholder="Company">
<input type="text" name="role" placeholder="Role (e.g. buyer, distributor, brand)">
<button type="submit">Unlock reports</button><p class="form-msg" id="report-msg"></p></form></div>
</div></section>
<script>
(function () {{
  function unlock() {{
    document.querySelectorAll("a.dl").forEach(function (a) {{ a.href = a.dataset.href; a.target = "_blank"; }});
    var g = document.getElementById("get"); if (g) g.style.display = "none";
  }}
  try {{ if (localStorage.getItem("kl_reports") === "1") unlock(); }} catch (e) {{}}
  var f = document.getElementById("report-form");
  if (!f) return;
  f.addEventListener("submit", function (ev) {{
    ev.preventDefault();
    var data = new FormData(f); data.append("_subject", "K-INSIDER LAB report download"); data.append("form", "monthly-report");
    fetch("{FORM_ACTION}", {{ method: "POST", body: data, headers: {{ Accept: "application/json" }} }})
      .then(function (r) {{ if (!r.ok) throw 0; try {{ localStorage.setItem("kl_reports", "1"); }} catch (e) {{}} unlock(); }})
      .catch(function () {{ document.getElementById("report-msg").textContent = "Something went wrong. Please try again."; }});
  }});
}})();
</script>"""


def load_exports():
    path = DATA / "exports.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def month_label(yyyymm):
    return dt.date(int(yyyymm[:4]), int(yyyymm[4:]), 1).strftime("%b %Y")


def export_rows(ex, hs):
    latest = ex.get("latest_month")
    if not latest or hs not in ex["values"]:
        return []
    prev_year = f"{int(latest[:4]) - 1}{latest[4:]}"
    names = {c["code"]: c["name"] for c in ex["countries"]}
    rows = []
    for code, series in ex["values"][hs].items():
        now, before = series.get(latest, 0), series.get(prev_year, 0)
        last12 = sum(series.get(m, 0) for m in ex["months"][-12:])
        yoy = (now / before - 1) if before > 0 else None
        rows.append({"country": names.get(code, code), "now": now, "yoy": yoy, "last12": last12})
    return sorted(rows, key=lambda r: r["now"], reverse=True)


def usd(v):
    return f"${v / 1e6:,.1f}M" if v >= 1e6 else f"${v / 1e3:,.0f}K"


def export_table(ex, hs, limit):
    rows = export_rows(ex, hs)[:limit]
    body = "".join(f"<tr><td>{e(r['country'])}</td><td class=\"num\">{usd(r['now'])}</td>"
                   f"<td class=\"num {pct_class(r['yoy'])}\">{pct(r['yoy'])}</td>"
                   f"<td class=\"num\">{usd(r['last12'])}</td></tr>" for r in rows)
    return (f'<div class="tbl-wrap"><table><thead><tr><th>Destination</th><th class="num">{month_label(ex["latest_month"])}</th>'
            f'<th class="num">vs. year before</th><th class="num">Last 12 months</th></tr></thead><tbody>{body}</tbody></table></div>')


def exports_block():
    ex = load_exports()
    if not ex or not ex.get("latest_month"):
        return ""
    return f"""<section class="seg"><div class="wrap">
<div class="seg-head"><h2>What Korea actually shipped</h2><p class="period">Korea Customs export statistics, {month_label(ex['latest_month'])}</p></div>
<h3>Skin care &amp; make-up (HS 3304) by destination</h3>{export_table(ex, "3304", 8)}
<p class="note">Official export values in US dollars from the Korea Customs Service, revised monthly. Search demand above
shows what Koreans want now; these figures show what is already crossing borders. <a href="/exports.html">All products &amp; markets</a></p>
</div></section>"""


def exports_page():
    ex = load_exports()
    if not ex or not ex.get("latest_month"):
        return '<section class="hero slim"><div class="wrap"><h1>Export statistics</h1><p>Coming soon.</p></div></section>'
    blocks = "".join(f"<h3>{e(p['en'])} (HS {p['hs']})</h3>{export_table(ex, p['hs'], 12)}" for p in ex["products"])
    return f"""<section class="hero slim"><div class="wrap"><p class="eyebrow">Official trade data</p>
<h1>Korean K-beauty &amp; K-food exports by market</h1>
<p class="lede small">Latest month: {month_label(ex['latest_month'])}. Source: {e(ex['source'])}. Refreshed weekly;
Customs revises the previous month around the 15th.</p></div></section>
<section class="seg"><div class="wrap">{blocks}</div></section>"""


# ---------- static pages ----------

METHODOLOGY = f"""
<section class="hero slim"><div class="wrap">
  <p class="eyebrow">Methodology</p>
  <h1>How the numbers are made</h1>
</div></section>
<section class="seg prose"><div class="wrap">
<h2>Source</h2>
<p>All figures come from <b>Naver DataLab Shopping Insight</b>, which reports the relative volume of
shopping-search clicks on Naver, Korea's largest search and shopping platform, within a product category
(for example “화장품/미용”, cosmetics &amp; beauty). We request daily data for a fixed watchlist of Korean
search terms, every day, automatically.</p>
<h2>Demand index</h2>
<p>Naver returns values relative to the highest point inside each request, so raw numbers from different
requests cannot be compared. Every request we send therefore includes the same <b>baseline term</b>
(Sunscreen for beauty, Ramyeon for food). We rescale each request so that the baseline's 8-week average
equals 100. A term with an index of 50 drew about half as many shopping-search clicks as the baseline over
the last 7 days.</p>
<h2>Momentum</h2>
<p>Momentum compares a term's average index over the most recent 7 days with its average over the 28 days
before. Terms whose demand index is below 10 are left out of the rising and cooling rankings and the
headline, because small volumes produce large, misleading percentage swings. Their data is still archived.</p>
<h2>What this is not</h2>
<ul>
<li>It is not sales data and not a count of searches. It shows relative interest.</li>
<li>It covers search terms (categories and ingredients), not individual products or brands.</li>
<li>It reflects Naver users in Korea; other channels can behave differently.</li>
</ul>
<h2>Integrity rules</h2>
<ul>
<li>No number is written by hand or by AI. Text on this site is produced from the data by fixed templates.</li>
<li>If the data source fails on a given day, we show the last verified data with its real date, never a
filled-in value.</li>
<li>Every daily brief is archived with its raw data file so past calls can be checked.</li>
</ul>
<h2>Watchlist</h2>
<p>The current watchlist is public: <a href="/config/watchlist.json">watchlist.json</a>. Terms are added
as new categories and ingredients emerge.</p>
</div></section>
"""


def build():
    latest_path = DATA / "latest.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8")) if latest_path.exists() \
        else {"status": "not_configured", "segments": []}

    briefs = []
    daily_dir = DATA / "daily"
    if daily_dir.exists():
        for p in sorted(daily_dir.glob("*.json"), reverse=True):
            briefs.append(json.loads(p.read_text(encoding="utf-8")))

    desc = ("Daily demand index for K-beauty and K-food categories and ingredients, "
            "measured from Korean shopping-search data. For importers, distributors and brand teams.")

    # home
    home_title = f"{BRAND} | Korea consumer demand, measured daily"
    (ROOT / "index.html").write_text(page(home_title, brief_body(latest, True), desc, "/"), encoding="utf-8")

    # daily brief pages
    out_dir = ROOT / "brief"
    out_dir.mkdir(exist_ok=True)
    for b in briefs:
        run = b["run_date"]
        t = f"{headline(b)} | {nice_date(run)} | {BRAND}"
        (out_dir / f"{run}.html").write_text(
            page(t, brief_body(b, False), f"Korea demand brief for {nice_date(run)}. " + desc, f"/brief/{run}.html"),
            encoding="utf-8")

    # archive
    if briefs:
        items = "".join(f'<li><a href="/brief/{b["run_date"]}.html"><span class="d">{nice_date(b["run_date"])}</span>'
                        f'<span>{e(headline(b))}</span></a></li>' for b in briefs)
        arch = f'<ul class="archive">{items}</ul>'
    else:
        arch = '<p>The archive starts with the first published daily brief.</p>'
    arch_body = f"""<section class="hero slim"><div class="wrap"><p class="eyebrow">Archive</p>
<h1>Every daily brief</h1><p class="lede small">Published automatically each morning (KST). Raw data and a
full history file (<a href="/data/history.csv">history.csv</a>) are kept for every day.</p></div></section>
<section class="seg"><div class="wrap">{arch}</div></section>"""
    (ROOT / "archive.html").write_text(page(f"Archive | {BRAND}", arch_body, desc, "/archive.html"), encoding="utf-8")

    (ROOT / "methodology.html").write_text(
        page(f"Methodology | {BRAND}", METHODOLOGY, "How the K-INSIDER LAB demand index is calculated.",
             "/methodology.html"), encoding="utf-8")

    (ROOT / "signals.html").write_text(
        page(f"Breakout track record | {BRAND}", signals_page(),
             "Every K-beauty and K-food breakout call from Korean shopping data, with results after 7, 14 and 28 days.",
             "/signals.html"), encoding="utf-8")

    (ROOT / "reports.html").write_text(
        page(f"Monthly demand report | {BRAND}", reports_page(),
             "Monthly PDF report on Korean consumer demand for K-beauty and K-food: rising categories, ingredients, "
             "brands and breakout calls.", "/reports.html"), encoding="utf-8")

    (ROOT / "exports.html").write_text(
        page(f"K-beauty & K-food exports by market | {BRAND}", exports_page(),
             "Official Korea Customs export statistics for cosmetics, hair care, noodles and sauces by destination country.",
             "/exports.html"), encoding="utf-8")

    term_urls = []
    if latest.get("status") == "ok":
        import csv
        hist_path = DATA / "history.csv"
        history_rows = list(csv.DictReader(hist_path.open(encoding="utf-8"))) if hist_path.exists() else []
        sigs = load_signals()["signals"]
        tdir = ROOT / "term"
        tdir.mkdir(exist_ok=True)
        for seg in latest["segments"]:
            for it in seg["items"]:
                sl = slug(seg["id"], it["en"])
                (tdir / f"{sl}.html").write_text(page(
                    f"{it['en']} demand in Korea | {BRAND}", term_page(seg, it, history_rows, sigs),
                    f"Daily Korean shopping-search demand for {it['en']} ({it['kw']}): index, momentum and 8-week trend.",
                    f"/term/{sl}.html"), encoding="utf-8")
                term_urls.append(f"/term/{sl}.html")

    nf = '<section class="hero slim"><div class="wrap"><h1>Page not found</h1><p><a href="/">Go to today’s brief</a></p></div></section>'
    (ROOT / "404.html").write_text(page(f"Not found | {BRAND}", nf, desc, "/404.html"), encoding="utf-8")

    # rss
    rss_items = []
    for b in briefs[:30]:
        run = b["run_date"]
        pub = dt.datetime.fromisoformat(run).replace(hour=7, tzinfo=KST)
        summary = html.unescape(summary_points(b)).replace("<li>", "").replace("</li>", "\n") \
            .replace("<b>", "").replace("</b>", "")
        rss_items.append(f"""<item><title>{e(headline(b))}</title>
<link>{SITE_URL}/brief/{run}.html</link><guid>{SITE_URL}/brief/{run}.html</guid>
<pubDate>{format_datetime(pub)}</pubDate><description>{e(summary.strip())}</description></item>""")
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>{BRAND} daily brief</title><link>{SITE_URL}/</link>
<description>Korea consumer demand, measured daily.</description><language>en</language>
{''.join(rss_items)}
</channel></rss>
"""
    (ROOT / "feed.xml").write_text(rss, encoding="utf-8")

    # sitemap + robots
    urls = (["/", "/signals.html", "/exports.html", "/reports.html", "/archive.html", "/methodology.html"]
             + [f"/brief/{b['run_date']}.html" for b in briefs] + term_urls)
    sm = "".join(f"<url><loc>{SITE_URL}{u}</loc></url>" for u in urls)
    (ROOT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>\n',
        encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    print(f"Built site: home + {len(briefs)} brief page(s)")


if __name__ == "__main__":
    build()
