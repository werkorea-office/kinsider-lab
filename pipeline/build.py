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

def ranked(seg):
    items = [i for i in seg["items"] if not i["is_anchor"]]
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

CSS_VERSION = "3"


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
    </div>
  </div>
</footer>
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
  <td class="kw"><span class="en">{e(it['en'])}</span>{tag}<span class="kr" lang="ko">{e(it['kw'])}</span></td>
  <td class="type">{e(it['type'])}</td>
  <td class="num {pct_class(it['momentum'])}">{pct(it['momentum'])}</td>
  <td class="num">{it['level']:.0f}</td>
  <td class="trend {pct_class(it['momentum'])}">{sparkline(it['series'])}</td>
</tr>""")
    head_rank = "<th>#</th>" if show_rank else ""
    return f"""<div class="tbl-wrap"><table>
<thead><tr>{head_rank}<th>Search term</th><th>Type</th>
<th class="num" title="Average of the last 7 days vs. the 28 days before">Momentum</th>
<th class="num" title="Shopping-search clicks; {e(anchor_en)} 8-week average = 100">Demand index</th>
<th>8 weeks</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>"""


def segment_block(seg, primary):
    rising, cooling, biggest = ranked(seg)
    stale = ""
    if seg.get("fresh") is False:
        stale = (f'<p class="stale">This section could not be refreshed today. '
                 f'Showing the last verified data (through {nice_date(seg["data_end"])}).</p>')
    period = f"Naver shopping-search data, {nice_date(seg['data_start'])} – {nice_date(seg['data_end'])}"
    parts = [f'<section class="seg"><div class="wrap">',
             f'<div class="seg-head"><h2>{e(seg["title"])}</h2><p class="period">{e(period)}</p></div>',
             stale]
    if rising:
        parts.append('<h3>Rising in Korea</h3>')
        parts.append(table(rising, seg, 10 if primary else 6))
    if primary:
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
        body.append(segment_block(seg, primary=(i == 0)))
    if is_home:
        body.append(subscribe_block())
    else:
        body.append(f'<section class="seg"><div class="wrap"><p><a href="/archive.html">← All daily briefs</a> · '
                    f'<a href="/data/daily/{run}.json">Raw data for this brief (JSON)</a></p></div></section>')
    return "\n".join(body)


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
before. Terms with very low volume are left out of momentum rankings to avoid noise.</p>
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
    urls = ["/", "/archive.html", "/methodology.html"] + [f"/brief/{b['run_date']}.html" for b in briefs]
    sm = "".join(f"<url><loc>{SITE_URL}{u}</loc></url>" for u in urls)
    (ROOT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>\n',
        encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    print(f"Built site: home + {len(briefs)} brief page(s)")


if __name__ == "__main__":
    build()
