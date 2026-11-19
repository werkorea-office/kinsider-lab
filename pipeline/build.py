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
FORM_ACTION = "https://formspree.io/f/mjygjowd"  # lead record (company, role)
SITE_CFG = json.loads((Path(__file__).resolve().parent.parent / "config" / "site.json").read_text(encoding="utf-8"))
KIT_FORM = SITE_CFG.get("kit_form_id") or ""      # newsletter list (double opt-in, unsubscribe handled by Kit)


def kit_alert_tag():
    """Kit tag id for breakout alerts, written by `python -m pipeline.alerts --setup`."""
    path = Path(__file__).resolve().parent.parent / "data" / "kit.json"
    return str(json.loads(path.read_text()).get("alert_tag_id", "")) if path.exists() else ""
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

CSS_VERSION = "13"


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
      <a href="/import-guide.html">Import guide</a>
      <a href="/calendar.html">Calendar</a>
      <a href="/market/">Markets</a>
      <a href="/sourcing-guide.html">Sourcing</a>
      <a href="/reports.html">Reports</a>
      <a href="/archive.html">Archive</a>
      <a href="/methodology.html">Methodology</a>
      <a class="btn-sm" href="/#subscribe" aria-label="Get the free weekly brief"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg><span class="l">Get the weekly brief</span><span class="s">Free brief</span></a>
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
      <p><a href="/about.html">About</a> · <a href="/methodology.html">Methodology &amp; limits</a> · <a href="/privacy.html">Privacy</a> · <a href="/terms.html">Terms</a> · <a href="/feed.xml">RSS</a></p>
      <p class="biz">Operated by DecisionS (디시전에스) · 3F, 235-1 Gaenggogae-ro, Chungju-si, Chungcheongbuk-do, Republic of Korea · Business reg. 666-45-01149 · <a href="mailto:brief@kinsider-lab.com">brief@kinsider-lab.com</a></p>
      <p class="visits" id="kl-visits" hidden>Visitors today <b id="kl-today">–</b> · All-time <b id="kl-total">–</b></p>
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
function klSubscribe(email, company, source, alerts) {{
  var d = new FormData();
  d.append("email_address", email);
  if (alerts) d.append("fields[alerts]", "yes");
  if (company) d.append("fields[company]", company);
  d.append("fields[source]", source);
  return fetch("https://app.kit.com/forms/{KIT_FORM}/subscriptions", {{ method: "POST", body: d, headers: {{ Accept: "application/json" }} }});
}}
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
    <form action="{FORM_ACTION}" method="POST" class="sub-form" id="sub-form">
      <input type="hidden" name="_subject" value="K-INSIDER LAB weekly brief signup">
      <input type="hidden" name="form" value="weekly-brief">
      <label class="sr" for="email">Business email</label>
      <input id="email" type="email" name="email" required placeholder="you@company.com">
      <input type="text" name="company" placeholder="Company (optional)">
      {'<label class="opt"><input type="checkbox" name="alerts" value="yes"> Also email me breakout alerts the day they are called (a few a month)</label>' if KIT_FORM and kit_alert_tag() else ''}
      <button type="submit">Subscribe</button>
      <p class="form-msg" id="sub-msg"></p>
    </form>
  </div>
</section>
<script>
(function () {{
  var f = document.getElementById("sub-form"), kit = "{KIT_FORM}";
  if (!f) return;
  f.addEventListener("submit", function (ev) {{
    ev.preventDefault();
    var data = new FormData(f), msg = document.getElementById("sub-msg");
    var jobs = [fetch("{FORM_ACTION}", {{ method: "POST", body: data, headers: {{ Accept: "application/json" }} }})];
    if (kit) jobs.push(klSubscribe(data.get("email"), data.get("company"), "weekly-brief", data.get("alerts") === "yes"));
    Promise.all(jobs).then(function (rs) {{
      if (!rs.every(function (r) {{ return r.ok; }})) throw 0;
      f.reset();
      msg.textContent = kit ? "Almost done: check your inbox and confirm your subscription." : "Thank you. You're on the list.";
    }}).catch(function () {{ msg.textContent = "Something went wrong. Please try again."; }});
  }});
}})();
</script>"""


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


_COMPLIANCE = None


def compliance():
    global _COMPLIANCE
    if _COMPLIANCE is None:
        # editorial config ships with the code (like site.json), not with the data directory
        path = Path(__file__).resolve().parent.parent / "config" / "compliance.json"
        _COMPLIANCE = json.loads(path.read_text(encoding="utf-8"))
    return _COMPLIANCE


def src_links(sources):
    return " · ".join(f'<a href="{e(u)}" rel="noopener">{e(t)}</a>' for t, u in sources)


def checklist_html(kind, compact=False):
    c = compliance()
    blocks = []
    for m in c["markets"].get(kind, []):
        steps = "".join(f"<li>{e(s)}</li>" for s in m["steps"])
        if compact:
            blocks.append(f"<details><summary>{e(m['market'])}</summary><ul>{steps}</ul>"
                          f"<p class=\"note\">Source: {src_links(m['sources'])}</p></details>")
        else:
            blocks.append(f"<h3>{e(m['market'])}</h3><ul>{steps}</ul><p class=\"note\">Source: {src_links(m['sources'])}</p>")
    return "".join(blocks)


def flags_for(en):
    return [f for f in compliance()["flags"] if en in f["applies_to"]]


def buyer_section(seg, it):
    kind = "food" if seg["id"] == "food" else "cosmetics"
    c = compliance()
    flags = "".join(f'<div class="flag"><b>{e(f["title"])}</b><p>{e(f["text"])}</p>'
                    f'<p class="note">Source: {src_links(f["sources"])}</p></div>' for f in flags_for(it["en"]))
    return (f'<h3>Before you import</h3>{flags}{checklist_html(kind, compact=True)}'
            f'<p class="note">{e(c.get("disclaimer", ""))} Reviewed {nice_date(c["reviewed"])}. '
            f'<a href="/import-guide.html">Full import checklist</a></p>{cite_block(seg, it)}')


def cite_block(seg, it):
    """Free reuse with attribution: every citation is a backlink and a new buyer."""
    url = f"{SITE_URL}/term/{slug(seg['id'], it['en'])}.html"
    ref = f"K-INSIDER LAB, \"{it['en']} in Korea: shopping demand trend\", {url}"
    return (f'<h3>Cite or reuse this data</h3><p class="note">Free to quote and chart in articles, decks and '
            f'reports under CC BY 4.0 — just credit and link K-INSIDER LAB.</p>'
            f'<pre class="cite">{e(ref)}</pre>')


def static_page(eyebrow, title, html_body):
    return (f'<section class="hero slim"><div class="wrap"><p class="eyebrow">{e(eyebrow)}</p><h1>{e(title)}</h1></div></section>'
            f'<section class="seg"><div class="wrap prose">{html_body}</div></section>')


ABOUT = """<p>K-INSIDER LAB measures what Korean consumers are shopping for, every day, and publishes it in English for
buyers, distributors, retailers and brand teams outside Korea. Korea is where many beauty and food trends start;
our job is to show that demand early, with numbers you can check.</p>
<h2>What we publish</h2><ul>
<li>A daily demand index for K-beauty products, ingredients and brands and for K-food, from Naver shopping-search clicks.</li>
<li>Breakout calls when a rise holds for two weeks, with every result checked after 7, 14 and 28 days and kept public.</li>
<li>Official Korea Customs export figures by product and destination market.</li>
<li>An import checklist for the US, EU and UK, with sources.</li></ul>
<h2>Principles</h2><ul>
<li>Data first: we report measured demand and official figures, never paid placements.</li>
<li>No product verdicts: we do not tell you a product is good or bad; we show what Korean shoppers do.</li>
<li>Nothing hidden: methods, watchlist and the full breakout ledger are public, misses included.</li></ul>
<h2>Who we are</h2><p>K-INSIDER LAB is operated by DecisionS (디시전에스), a Korean company based in Chungju, Republic of Korea
(business registration 666-45-01149). Contact: <a href="mailto:brief@kinsider-lab.com">brief@kinsider-lab.com</a>.
Data partners and custom research requests are welcome.</p>"""

PRIVACY = """<p>Last updated 19 November 2026. This policy explains what personal data K-INSIDER LAB (operated by DecisionS,
3F, 235-1 Gaenggogae-ro, Chungju-si, Chungcheongbuk-do, Republic of Korea; contact
<a href="mailto:brief@kinsider-lab.com">brief@kinsider-lab.com</a>) collects and why.</p>
<h2>What we collect</h2><ul>
<li><b>Email subscription:</b> your email address and, if you give them, company and role. We use them to send the weekly
brief, breakout alerts you opted into, and report links. You confirm by email before anything is sent (double opt-in).</li>
<li><b>Visit counts:</b> the site counts visits per day without cookies; your browser stores a local flag so a visit is counted once a day.
No IP addresses or identifiers are stored by us.</li></ul>
<h2>Service providers</h2><p>Kit (email delivery and list management), Formspree (form submissions), GitHub Pages (hosting) and
Cloudflare (network and visit counter) process data on our behalf, some of them in the United States.</p>
<h2>Your choices and rights</h2><ul>
<li>Every email has an unsubscribe link; unsubscribing stops all emails at once.</li>
<li>You can ask to see, correct or delete your data at any time by writing to brief@kinsider-lab.com.
Depending on where you live (for example the EU/UK under the GDPR, or Korea under PIPA) you may also object to processing
or complain to your data protection authority.</li>
<li>We keep subscriber data while you are subscribed and delete it within 30 days of a deletion request.</li></ul>
<p>We do not sell personal data and do not use it for advertising.</p>"""

TERMS = """<p>Last updated 19 November 2026. By using kinsider-lab.com you agree to these terms.</p>
<h2>Information, not advice</h2><p>Indices, breakout calls, export figures and import checklists are provided for information.
They are not investment, legal or regulatory advice. Search demand indicates interest, not sales. Confirm regulatory
requirements with a qualified specialist before importing or selling products.</p>
<h2>Sources</h2><p>Search data: Naver DataLab Shopping Insight (relative click indices, not absolute volumes).
Trade data: Korea Customs Service via data.go.kr. Figures may be revised by their sources.</p>
<h2>Use of our content</h2><p>You may quote and share charts and figures with credit and a link to kinsider-lab.com.
Bulk copying or resale of the data requires written permission from brief@kinsider-lab.com.</p>
<h2>Liability</h2><p>The site is provided as is. DecisionS is not liable for decisions made on the basis of the information,
to the extent permitted by law. These terms are governed by the laws of the Republic of Korea.</p>"""


def calendar_page(today):
    cal = json.loads((Path(__file__).resolve().parent.parent / "config" / "calendar.json").read_text(encoding="utf-8"))
    rows = []
    for ev in sorted(cal["events"], key=lambda x: x["start"]):
        if ev["end"] < today:
            continue
        when = nice_date(ev["start"]) + ("" if ev["start"] == ev["end"] else f" – {nice_date(ev['end'])}")
        now = ' <span class="tag">Now</span>' if ev["start"] <= today else ""
        tag = "" if ev["status"] == "fixed" else ' <span class="note">(expected)</span>'
        rows.append(f'<tr><td>{when}{tag}</td><td><b>{e(ev["name"])}</b>{now}<br><span class="note">{e(ev["kind"])}</span></td>'
                    f'<td>{e(ev["why"])}</td><td>{e(ev["act"])}</td></tr>')
    return f"""<section class="hero slim"><div class="wrap"><p class="eyebrow">For buyers, sellers and creators</p>
<h1>Korea commerce calendar</h1>
<p class="lede small">The dates that move Korean beauty and food demand, prices and shipping, and what to do before each one.
{e(cal['note'])} Reviewed {nice_date(cal['reviewed'])}.</p></div></section>
<section class="seg"><div class="wrap"><div class="tbl-wrap"><table><thead><tr><th>When</th><th>Event</th><th>Why it matters</th>
<th>What to do</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></div></section>{subscribe_block()}"""


def import_guide_page():
    c = compliance()
    flags = "".join(f'<div class="flag"><b>{e(f["title"])}</b> <span class="note">({e(", ".join(f["applies_to"]))})</span>'
                    f'<p>{e(f["text"])}</p><p class="note">Source: {src_links(f["sources"])}</p></div>' for f in c["flags"])
    return f"""<section class="hero slim"><div class="wrap"><p class="eyebrow">For buyers and distributors</p>
<h1>Importing K-beauty and K-food: the checklist</h1>
<p class="lede small">What has to be in place before Korean cosmetics or food can be sold in the US, EU and UK, and what
to ask the supplier for. Reviewed {nice_date(c['reviewed'])}. {e(c['disclaimer'])}</p></div></section>
<section class="seg"><div class="wrap">
<h2>Cosmetics</h2>{checklist_html("cosmetics")}
<h2>Product-specific flags</h2>{flags}
<h2>Food</h2>{checklist_html("food")}
</div></section>{subscribe_block()}"""


_NOTES = None


def note_for(seg_id, kw):
    global _NOTES
    if _NOTES is None:
        cfg = json.loads((ROOT / "config" / "watchlist.json").read_text(encoding="utf-8"))
        _NOTES = {(s["id"], k["kw"]): k.get("note", "") for s in cfg["segments"] for k in [s["anchor"]] + s["keywords"]}
    return _NOTES.get((seg_id, kw), "")


def term_page(seg, it, history_rows, sigs):
    big = sparkline(it["series"], w=640, h=160)
    note = note_for(seg["id"], it["kw"])
    hist = [r for r in history_rows if r["segment"] == seg["id"] and r["keyword_kr"] == it["kw"]][-30:]
    hrows = "".join(f"<tr><td class=\"num\">{nice_date(r['run_date'])}</td><td class=\"num\">{float(r['level']):.0f}</td>"
                    f"<td class=\"num\">{pct(float(r['momentum'])) if r['momentum'] else '–'}</td></tr>" for r in reversed(hist))
    calls = [x for x in sigs if x["segment"] == seg["id"] and x["kw"] == it["kw"]]
    call_html = "".join(f"<li>Breakout called {nice_date(x['called'])} at index {x['level_at_call']:.0f}</li>" for x in calls)
    kind = "brand" if seg["id"] == "brands" else "search term"
    return f"""<section class="hero slim"><div class="wrap"><p class="eyebrow">{e(seg['title'])} · {e(it['type'])}</p>
<h1>{e(it['en'])} <span class="kr-title" lang="ko">{e(it['kw'])}</span></h1>
{f'<p class="lede">{e(note)}</p>' if note else ''}
<p class="lede small">Korean shopping-search demand for this {kind}, updated daily from Naver DataLab.</p>
<div class="stats"><div><span>Demand index (7 days)</span><b>{it['level']:.0f}</b></div>
<div><span>Momentum vs prior 4 weeks</span><b class="{pct_class(it['momentum'])}">{pct(it['momentum'])}</b></div>
<div><span>Data through</span><b>{nice_date(seg['data_end'])}</b></div></div></div></section>
<section class="seg"><div class="wrap"><h3>Last 8 weeks (weekly average)</h3>
<div class="bigchart {pct_class(it['momentum'])}">{big}</div>
{'<h3>Breakout calls</h3><ul>' + call_html + '</ul>' if calls else ''}
{buyer_section(seg, it)}
<h3>Daily record</h3>
{'<div class="tbl-wrap"><table><thead><tr><th class="num">Date</th><th class="num">Demand index</th><th class="num">Momentum</th></tr></thead><tbody>' + hrows + '</tbody></table></div>' if hrows else '<p class="note">The daily record starts with the first brief.</p>'}
<p class="note">Index: shopping-search clicks in Naver's “{e(seg['category_name_kr'])}” category, {e(seg['anchor']['en'])} 8-week average = 100.
<a href="/methodology.html">Methodology</a></p></div></section>
{subscribe_block()}"""


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
<label class="opt"><input type="checkbox" name="brief" value="yes" checked> Also send me the free weekly brief</label>
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
    var jobs = [fetch("{FORM_ACTION}", {{ method: "POST", body: data, headers: {{ Accept: "application/json" }} }})];
    if ("{KIT_FORM}" && data.get("brief") === "yes") jobs.push(klSubscribe(data.get("email"), data.get("company"), "monthly-report"));
    Promise.all(jobs).then(function (rs) {{ return rs[0]; }})
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
        kg = ex.get("weights_kg", {}).get(hs, {}).get(code, {})
        kg12 = sum(kg.get(m, 0) for m in ex["months"][-12:])
        kg_prev12 = sum(kg.get(m, 0) for m in ex["months"][-24:-12])
        usd_prev12 = sum(series.get(m, 0) for m in ex["months"][-24:-12])
        unit = last12 / kg12 if kg12 > 0 else None            # US$ per kg, trailing 12 months
        unit_prev = usd_prev12 / kg_prev12 if kg_prev12 > 0 else None
        growth12 = (last12 / usd_prev12 - 1) if usd_prev12 > 0 else None
        rows.append({"code": code, "country": names.get(code, code), "now": now, "yoy": yoy, "last12": last12,
                     "unit": unit, "unit_change": (unit / unit_prev - 1) if unit and unit_prev else None,
                     "growth12": growth12})
    return sorted(rows, key=lambda r: r["now"], reverse=True)


def usd(v):
    return f"${v / 1e6:,.1f}M" if v >= 1e6 else f"${v / 1e3:,.0f}K"


def has_weights(ex, hs):
    return any(v for c in ex.get("weights_kg", {}).get(hs, {}).values() for v in c.values())


def export_table(ex, hs, limit):
    rows = export_rows(ex, hs)[:limit]
    unit = has_weights(ex, hs)
    def unit_cells(r):
        if not unit:
            return ""
        val = f"${r['unit']:,.1f}" if r["unit"] else "–"
        return (f"<td class=\"num\">{val}</td>"
                f"<td class=\"num {pct_class(r['unit_change'])}\">{pct(r['unit_change'])}</td>")
    body = "".join(f"<tr><td>{e(r['country'])}</td><td class=\"num\">{usd(r['now'])}</td>"
                   f"<td class=\"num {pct_class(r['yoy'])}\">{pct(r['yoy'])}</td>"
                   f"<td class=\"num\">{usd(r['last12'])}</td>{unit_cells(r)}</tr>" for r in rows)
    unit_head = ('<th class="num">US$ per kg (12 mo.)</th><th class="num">Price per kg vs. prior 12 mo.</th>'
                 if unit else "")
    return (f'<div class="tbl-wrap"><table><thead><tr><th>Destination</th><th class="num">{month_label(ex["latest_month"])}</th>'
            f'<th class="num">vs. year before</th><th class="num">Last 12 months</th>{unit_head}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def growth_table(ex, hs, limit=8):
    """Fastest-growing destinations: last 12 months vs. the 12 before (min. US$1M a year)."""
    rows = [r for r in export_rows(ex, hs) if r["growth12"] is not None and r["last12"] >= 1e6]
    rows.sort(key=lambda r: r["growth12"], reverse=True)
    body = "".join(f"<tr><td>{n}</td><td>{e(r['country'])}</td>"
                   f"<td class=\"num {pct_class(r['growth12'])}\">{pct(r['growth12'])}</td>"
                   f"<td class=\"num\">{usd(r['last12'])}</td></tr>" for n, r in enumerate(rows[:limit], 1))
    return (f'<div class="tbl-wrap"><table><thead><tr><th>#</th><th>Market</th><th class="num">Growth, last 12 mo.</th>'
            f'<th class="num">Exports, last 12 mo.</th></tr></thead><tbody>{body}</tbody></table></div>')


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
    growth = "".join(f"<h3>{e(p['en'])}</h3>{growth_table(ex, p['hs'])}" for p in ex["products"])
    blocks = (f'<h2>Fastest-growing markets</h2><p class="note">Export value in the last 12 months vs. the 12 months '
              f'before; markets above US$1M a year.</p>{growth}<h2>By destination</h2>'
              f'<p class="note">US$ per kg is export value divided by declared net weight: a read on whether Korea is '
              f'shipping higher- or lower-priced goods to each market. It moves with product mix as well as price.</p>{blocks}')
    return f"""<section class="hero slim"><div class="wrap"><p class="eyebrow">Official trade data</p>
<h1>Korean K-beauty &amp; K-food exports by market</h1>
<p class="lede small">Latest month: {month_label(ex['latest_month'])}. Source: {e(ex['source'])}. Refreshed weekly;
Customs revises the previous month around the 15th.</p></div></section>
<section class="seg"><div class="wrap">{blocks}</div></section>"""


def market_slug(code):
    return f"/market/{code.lower()}.html"


def market_page(ex, code, name):
    rows, total = [], 0
    for prod in ex["products"]:
        all_rows = export_rows(ex, prod["hs"])
        r = next((x for x in all_rows if x["code"] == code), None)
        if not r:
            continue
        rank = 1 + sorted([x["last12"] for x in all_rows], reverse=True).index(r["last12"])
        total += r["last12"]
        unit = f"${r['unit']:,.1f}" if r["unit"] else "–"
        rows.append(f"<tr><td>{e(prod['en'])} <span class=\"note\">HS {prod['hs']}</span></td>"
                    f"<td class=\"num\">{usd(r['last12'])}</td><td class=\"num {pct_class(r['growth12'])}\">{pct(r['growth12'])}</td>"
                    f"<td class=\"num {pct_class(r['yoy'])}\">{pct(r['yoy'])}</td><td class=\"num\">{unit}</td>"
                    f"<td class=\"num\">#{rank} of {len(all_rows)}</td></tr>")
    body = (f'<div class="tbl-wrap"><table><thead><tr><th>Product</th><th class="num">Exports, last 12 mo.</th>'
            f'<th class="num">vs. prior 12 mo.</th><th class="num">{month_label(ex["latest_month"])} vs. year before</th>'
            f'<th class="num">US$ per kg</th><th class="num">Rank among tracked markets</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')
    others = " · ".join(f'<a href="{market_slug(c["code"])}">{e(c["name"])}</a>' for c in ex["countries"] if c["code"] != code)
    return total, f"""<section class="hero slim"><div class="wrap"><p class="eyebrow">Market profile · official trade data</p>
<h1>Korean beauty &amp; food exports to {e(name)}</h1>
<p class="lede small">How much Korean skin care, hair care, noodles and sauces ship to {e(name)}, how fast it is growing,
and the price level per kg. Latest month {month_label(ex['latest_month'])}. Source: {e(ex['source'])}.</p></div></section>
<section class="seg"><div class="wrap">{body}
<p class="note">Growth above +20% with a rising US$ per kg usually means a market is trading up to premium Korean goods;
falling US$ per kg points to volume and price competition. Pair this with what Koreans are searching now on the
<a href="/">daily dashboard</a> and the <a href="/calendar.html">commerce calendar</a>.</p>
<h3>Other markets</h3><p class="note">{others}</p></div></section>{subscribe_block()}"""


def markets_index(ex, totals):
    rows = "".join(f'<tr><td><a href="{market_slug(c)}">{e(n)}</a></td><td class="num">{usd(t)}</td></tr>'
                   for c, n, t in sorted(totals, key=lambda x: x[2], reverse=True))
    return f"""<section class="hero slim"><div class="wrap"><p class="eyebrow">Market profiles</p>
<h1>Where Korean beauty &amp; food exports go</h1>
<p class="lede small">One page per market: tracked Korean beauty and food exports, growth and price per kg.
Latest month {month_label(ex['latest_month'])}.</p></div></section>
<section class="seg"><div class="wrap"><div class="tbl-wrap"><table><thead><tr><th>Market</th>
<th class="num">Tracked exports, last 12 mo.</th></tr></thead><tbody>{rows}</tbody></table></div></div></section>{subscribe_block()}"""


def guide_page(name):
    g = json.loads((Path(__file__).resolve().parent.parent / "config" / f"{name}.json").read_text(encoding="utf-8"))
    secs = "".join(f"<h2>{e(x['h'])}</h2>" + "".join(f"<p>{x_}</p>" for x_ in x["p"]) for x in g["sections"])
    return f"""<section class="hero slim"><div class="wrap"><p class="eyebrow">{e(g['eyebrow'])}</p><h1>{e(g['title'])}</h1>
<p class="lede small">{e(g['lede'])} Reviewed {nice_date(g['reviewed'])}.</p></div></section>
<section class="seg"><div class="wrap prose">{secs}</div></section>{subscribe_block()}"""


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

    nl_dir = ROOT / "newsletter"
    nl_dir.mkdir(exist_ok=True)
    issues = sorted([f.stem for f in nl_dir.glob("20*.html")], reverse=True)
    items = "".join(f'<li><a href="/newsletter/{d}.html">{nice_date(d)}</a></li>' for d in issues) or \
        "<li>The first weekly brief goes out on Monday, 23 November 2026.</li>"
    (nl_dir / "index.html").write_text(
        page(f"Weekly brief archive | {BRAND}",
             f'''<section class="hero slim"><div class="wrap"><p class="eyebrow">Weekly brief</p>
<h1>Every weekly Korea demand brief</h1><p class="lede small">Sent every Monday, 9:00 AM US Eastern.</p></div></section>
<section class="seg"><div class="wrap"><ul class="archive-list">{items}</ul></div></section>{subscribe_block()}''',
             "Archive of the K-INSIDER LAB weekly Korea demand brief.", "/newsletter/"), encoding="utf-8")

    for fname, title, eyebrow, body, desc in [
        ("about.html", "About K-INSIDER LAB", "About", ABOUT, "Who runs K-INSIDER LAB, what we publish and how."),
        ("privacy.html", "Privacy policy", "Legal", PRIVACY, "How K-INSIDER LAB handles subscriber data."),
        ("terms.html", "Terms of use", "Legal", TERMS, "Terms of use for kinsider-lab.com data and content.")]:
        (ROOT / fname).write_text(page(f"{title} | {BRAND}", static_page(eyebrow, title, body), desc, f"/{fname}"),
                                  encoding="utf-8")

    ex = load_exports()
    if ex and ex.get("latest_month"):
        (ROOT / "market").mkdir(exist_ok=True)
        totals = []
        for c in ex["countries"]:
            total, html_ = market_page(ex, c["code"], c["name"])
            totals.append((c["code"], c["name"], total))
            (ROOT / market_slug(c["code"]).lstrip("/")).write_text(
                page(f"Korean cosmetics & food exports to {c['name']}: size, growth, price | {BRAND}", html_,
                     f"Official Korea Customs data on K-beauty and K-food exports to {c['name']}: last 12 months, "
                     f"growth and US$ per kg.", market_slug(c["code"])), encoding="utf-8")
        (ROOT / "market" / "index.html").write_text(
            page(f"Korean beauty & food exports by market | {BRAND}", markets_index(ex, totals),
                 "Market-by-market profiles of Korean cosmetics and food exports from official customs data.",
                 "/market/"), encoding="utf-8")
    for name, fname, title, desc in [
        ("lag", "korea-to-world.html", "From Korea to the world: how K-trends travel",
         "Documented cases of Korean beauty and food trends that reached US and European shelves, and how long it took."),
        ("odm", "sourcing-guide.html", "How to make your own K-beauty brand: Korean OEM/ODM sourcing guide",
         "How Korean cosmetic OEM/ODM manufacturing works: major makers, minimum orders, timelines and documents.")]:
        (ROOT / fname).write_text(page(f"{title} | {BRAND}", guide_page(name), desc, f"/{fname}"), encoding="utf-8")
    (ROOT / "calendar.html").write_text(
        page(f"Korea commerce calendar: K-beauty & K-food sales, holidays, shipping | {BRAND}",
             calendar_page(dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()),
             "Olive Young sales, Seollal and Chuseok shutdowns, Kimjang and gifting peaks: the Korean dates "
             "that move beauty and food demand, with what buyers should do before each.", "/calendar.html"),
        encoding="utf-8")
    (ROOT / "import-guide.html").write_text(
        page(f"Importing K-beauty & K-food: US, EU, UK checklist | {BRAND}", import_guide_page(),
             "What must be in place before Korean cosmetics or food can be sold in the US, EU and UK: MoCRA, "
             "CPNP, SCPN, FDA food registration, sunscreen and retinol rules.", "/import-guide.html"),
        encoding="utf-8")

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
                    f"{it['en']} in Korea: shopping demand trend {seg['data_end'][:4]} | {BRAND}",
                    term_page(seg, it, history_rows, sigs),
                    (note_for(seg["id"], it["kw"]) + " " if note_for(seg["id"], it["kw"]) else "")
                    + f"Daily Korean shopping-search demand for {it['en']} ({it['kw']}): index, momentum and 8-week trend.",
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
    urls = (["/", "/signals.html", "/exports.html", "/import-guide.html", "/calendar.html", "/market/", "/korea-to-world.html", "/sourcing-guide.html", "/about.html", "/reports.html", "/newsletter/", "/archive.html", "/methodology.html"]
             + [f"/brief/{b['run_date']}.html" for b in briefs] + term_urls
             + [f"/market/{c['code'].lower()}.html" for c in (load_exports() or {}).get("countries", [])])
    sm = "".join(f"<url><loc>{SITE_URL}{u}</loc></url>" for u in urls)
    (ROOT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>\n',
        encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    print(f"Built site: home + {len(briefs)} brief page(s)")


if __name__ == "__main__":
    build()
