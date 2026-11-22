"""Daily social carousel. Run: python -m pipeline.cards

One fixed, recognisable format every day (the Exploding Topics / Chartr lesson:
a standard structure readers learn to expect), built as a carousel because
carousels out-perform single images on both Instagram and LinkedIn:

  1  Cover      a finding written as a sentence + the hero trend's chart
  2-4 Profiles  one trend per slide: name, the Korean search term, status,
                change, an annotated 8-week chart and what the thing is
  5  Ranking    the full list behind the story
  6  Close      what K-INSIDER LAB tracks and where to get it free

Output: cards/<date>/01.jpg ... NN.jpg, caption.txt, meta.json
Story by KST weekday: Mon trend, Tue Koreans-actually-use, Wed explained, Thu buy smart, Fri K-food,
Sat track record, other days K-beauty products & ingredients. Wed/Sat fall
back to K-beauty when there is not enough to show. Only fresh data is used and
the ranking rules match the website (index floor, no anchors).
"""
import datetime as dt
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import build

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
OUT = ROOT / "cards"
CONFIG = ROOT / "config" / "watchlist.json"
LAUNCH = dt.date(2026, 11, 18)          # issue No. 1
KEEP_DAYS = 21                          # older carousels are removed from the site

W, H, SC = 1080, 1350, 2                # drawn at 2x, downscaled for smooth edges
INK, INK2, PAPER = "#0f1420", "#1b2232", "#f6f4ef"
TEXT, MUTED, FAINT, LINE = "#0f1420", "#667085", "#98a2b3", "#e2dfd8"
ACCENT, UP, DOWN, STEADY = "#e0521f", "#0e7a50", "#c0321f", "#667085"
HANDLE = "@kinsiderlab_official"

FONT_FILES = {
    "reg": "Inter-Regular.otf", "med": "Inter-Medium.otf", "semi": "Inter-SemiBold.otf",
    "bold": "Inter-Bold.otf", "xbold": "InterDisplay-ExtraBold.otf", "black": "InterDisplay-Black.otf",
    "kr": "NotoSansKR-Bold-subset.otf", "serif": "PlayfairDisplay-VF.ttf",
}
_font_cache = {}


def font(kind, size):
    key = (kind, size)
    if key not in _font_cache:
        f = ImageFont.truetype(str(FONTS / FONT_FILES[kind]), int(size * SC))
        if kind == "serif":
            f.set_variation_by_name("Bold")
        _font_cache[key] = f
    return _font_cache[key]


# ---------------------------------------------------------------- data helpers

def notes():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    out = {}
    for seg in cfg["segments"]:
        for k in [seg["anchor"]] + seg["keywords"]:
            if k.get("note"):
                out[(seg["id"], k["kw"])] = k["note"]
    return out


def tracked_counts(snapshot):
    return {s["id"]: len([i for i in s["items"] if not i["is_anchor"]]) for s in snapshot["segments"]}


def seg_by_id(snapshot, sid):
    seg = next((s for s in snapshot["segments"] if s["id"] == sid), None)
    return seg if seg and seg.get("status") == "ok" and seg.get("fresh") is not False else None


def rolling(series, n=7):
    out = []
    for i in range(len(series)):
        win = series[max(0, i - n + 1):i + 1]
        out.append(sum(win) / len(win))
    return out


def status_for(item, active_kws):
    if item["kw"] in active_kws:
        return "BREAKOUT SIGNAL", ACCENT
    m = item.get("momentum")
    if m is None:
        return "STEADY", STEADY
    if m >= 0.10:
        return "RISING", UP
    if m <= -0.10:
        return "COOLING", DOWN
    return "STEADY", STEADY


def active_breakouts(run):
    led = build.load_signals()
    return [x for x in led["signals"] if 0 <= (run - dt.date.fromisoformat(x["called"])).days <= 28]


# ---------------------------------------------------------------- drawing primitives

class Slide:
    def __init__(self, dark):
        self.dark = dark
        self.img = Image.new("RGB", (W * SC, H * SC), INK if dark else PAPER)
        self.d = ImageDraw.Draw(self.img)

    def text(self, xy, s, kind, size, fill, anchor="la"):
        self.d.text((xy[0] * SC, xy[1] * SC), s, font=font(kind, size), fill=fill, anchor=anchor)

    def width(self, s, kind, size):
        return self.d.textlength(s, font=font(kind, size)) / SC

    def fit(self, s, kind, size, max_w, min_size=24):
        while size > min_size and self.width(s, kind, size) > max_w:
            size -= 2
        return size

    def wrap(self, s, kind, size, max_w):
        lines, cur = [], ""
        for word in s.split():
            trial = (cur + " " + word).strip()
            if self.width(trial, kind, size) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def paragraph(self, xy, s, kind, size, fill, max_w, leading=1.28, max_lines=None):
        lines = self.wrap(s, kind, size, max_w)
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip(".,;") + "…"
        y = xy[1]
        for line in lines:
            self.text((xy[0], y), line, kind, size, fill)
            y += size * leading
        return y

    def rect(self, box, fill=None, outline=None, width=1, radius=0):
        b = [v * SC for v in box]
        if radius:
            self.d.rounded_rectangle(b, radius=radius * SC, fill=fill, outline=outline, width=width * SC)
        else:
            self.d.rectangle(b, fill=fill, outline=outline, width=width * SC)

    def line(self, pts, fill, width=2):
        self.d.line([(x * SC, y * SC) for x, y in pts], fill=fill, width=int(width * SC), joint="curve")

    def pill(self, x, y, label, color, filled=True):
        size = 19
        w = self.width(label, "bold", size) + 32
        if filled:
            self.rect((x, y, x + w, y + 40), fill=color, radius=20)
            self.text((x + 16, y + 20), label, "bold", size, "white", anchor="lm")
        else:
            self.rect((x, y, x + w, y + 40), outline=color, width=2, radius=20)
            self.text((x + 16, y + 20), label, "bold", size, color, anchor="lm")
        return x + w

    def save(self, path):
        self.img.resize((W, H), Image.LANCZOS).save(path, "JPEG", quality=90, subsampling=0, optimize=True)


def chrome(s, issue, run_date, page, pages, source="Source: Naver shopping-search clicks, Korea"):
    """Masthead and footer shared by every slide."""
    fg = "white" if s.dark else TEXT
    sub = "#9aa3b5" if s.dark else MUTED
    s.rect((64, 56, 104, 96), fill=ACCENT, radius=9)
    s.text((84, 76), "K", "black", 26, "white", anchor="mm")
    s.text((118, 76), "K-INSIDER", "xbold", 24, fg, anchor="lm")
    s.text((118 + s.width("K-INSIDER ", "xbold", 24), 76), "LAB", "xbold", 24, ACCENT, anchor="lm")
    s.text((W - 64, 76), f"No. {issue:03d}  ·  {build.nice_date(run_date).upper()}", "semi", 19, sub, anchor="rm")
    s.line([(64, H - 92), (W - 64, H - 92)], "#2a3346" if s.dark else LINE, 1.5)
    s.text((64, H - 58), f"{source}  ·  kinsider-lab.com", "med", 18, sub, anchor="lm")
    s.text((W - 64, H - 58), f"{page} / {pages}", "semi", 18, sub, anchor="rm")


def chart(s, box, values, dark, marker_idx=None, marker_label=None, highlight_last=7, color=ACCENT,
          end_label=None, baseline=None, baseline_label=None, dates=None):
    """Annotated line chart: 7-day average, last week shaded, end point labelled."""
    x0, y0, x1, y1 = box
    grid = "#2a3346" if dark else LINE
    sub = "#9aa3b5" if dark else MUTED
    sm = rolling(values)
    lo = 0.0
    hi = max(sm + ([baseline] if baseline else [])) * 1.18 or 1
    n = len(sm)

    def px(i):
        return x0 + (x1 - x0) * i / max(n - 1, 1)

    def py(v):
        return y1 - (y1 - y0) * (v - lo) / (hi - lo)

    for frac in (0.0, 0.5, 1.0):
        y = y1 - (y1 - y0) * frac
        s.line([(x0, y), (x1, y)], grid, 1)
    if highlight_last:
        xs = px(n - highlight_last)
        s.rect((xs, y0 - 10, x1 + 6, y1), fill="#252e42" if dark else "#efe6dc")
        s.text((xs + 8, y0 - 4), "LAST 7 DAYS", "bold", 15, ACCENT)
    if baseline:
        y = py(baseline)
        x = x0
        while x < x1:
            s.line([(x, y), (min(x + 10, x1), y)], sub, 2)
            x += 20
    pts = [(px(i), py(v)) for i, v in enumerate(sm)]
    area = [(x * SC, y * SC) for x, y in pts] + [(x1 * SC, y1 * SC), (x0 * SC, y1 * SC)]
    overlay = Image.new("RGBA", s.img.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).polygon(area, fill=_rgba(color, 46))
    s.img.paste(Image.alpha_composite(s.img.convert("RGBA"), overlay).convert("RGB"))
    s.d = ImageDraw.Draw(s.img)
    s.line(pts, color, 5)
    ex, ey = pts[-1]
    s.d.ellipse([(ex - 9) * SC, (ey - 9) * SC, (ex + 9) * SC, (ey + 9) * SC], fill=color,
                outline=INK if dark else PAPER, width=3 * SC)
    if baseline and baseline_label:
        y = py(baseline)
        lw = s.width(baseline_label, "semi", 16)
        s.rect((x0, y - 34, x0 + lw + 16, y - 8), fill=INK if dark else PAPER, radius=4)
        s.text((x0 + 8, y - 21), baseline_label, "semi", 16, sub, anchor="lm")
    if end_label:
        s.text((ex - 14, ey - 18), end_label, "bold", 22, color, anchor="rb")
    if marker_idx is not None and 0 <= marker_idx < n:
        mx = px(marker_idx)
        s.line([(mx, y0), (mx, y1)], TEXT if not dark else "white", 2)
        if marker_label:
            s.text((mx + 8, y0 + 4), marker_label, "bold", 16, TEXT if not dark else "white")
    if dates:
        s.text((x0, y1 + 14), build.nice_date(dates[0]), "med", 16, sub)
        s.text((x1, y1 + 14), build.nice_date(dates[-1]), "med", 16, sub, anchor="ra")


def _rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


# ---------------------------------------------------------------- slides

def magazine_title(story):
    """Story-style headline and one-line dek for the photo cover (the data stays on the inside slides)."""
    seg = story.get("segment")
    if story.get("price"):
        return f"What Koreans Actually Pay For {story['prices'][0]['brand']} This Week", "Reference prices from Naver Shopping, Korea. Swipe for three brands."
    if story.get("editorial"):
        return story["headline"], story.get("sub", "")
    it = story["items"][0]
    name, ch = it["name"], it["change_text"]
    if seg == "food":
        return f"Koreans Can't Stop Searching For {name} Right Now", f"Korean shopping searches {ch} this week. Naver data."
    if seg in ("brands", "brands-top"):
        return f"The K-Beauty Brand Koreans Are Searching Most: {name}", f"{ch} in Korean shopping searches this week. Naver data."
    if seg == "signals":
        return f"Seoul's Next K-Beauty Breakout? Watch {name}", f"Two straight weeks of rising Korean searches ({ch}). Naver data."
    return f"Koreans Suddenly Can't Stop Searching For {name}", f"Korean shopping searches {ch} this week. Naver data."


def photo_cover(story, photo, issue, run_date, pages):
    s = Slide(dark=True)
    im = Image.open(photo["path"]).convert("RGB")
    tw, th = W * SC, H * SC
    r = max(tw / im.width, th / im.height)
    im = im.resize((int(im.width * r + 1), int(im.height * r + 1)), Image.LANCZOS)
    left, top = (im.width - tw) // 2, max(0, (im.height - th) // 3)
    s.img.paste(im.crop((left, top, left + tw, top + th)))
    # bottom gradient for legibility
    grad = Image.new("L", (1, th))
    for y in range(th):
        t = max(0.0, (y / th - 0.38) / 0.62)
        grad.putpixel((0, y), int(255 * min(1, t * 1.15) ** 1.3))
    shade = Image.new("RGB", (tw, th), (8, 10, 16))
    s.img.paste(shade, (0, 0), grad.resize((tw, th)))
    top = Image.new("L", (1, 220 * SC))
    for y in range(220 * SC):
        top.putpixel((0, y), int(150 * (1 - y / (220 * SC)) ** 1.5))
    s.img.paste(shade, (0, 0), top.resize((tw, 220 * SC)))
    s.d = ImageDraw.Draw(s.img)
    title, dek = magazine_title(story)
    size = 78
    lines = s.wrap(title, "serif", size, W - 128)
    while len(lines) > 4 and size > 54:
        size -= 4
        lines = s.wrap(title, "serif", size, W - 128)
    dek_lines = s.wrap(dek, "semi", 24, W - 220)[:2]
    y = H - 120 - len(dek_lines) * 34 - 30 - len(lines) * size * 1.08
    s.text((64, y - 46), story.get("segment_label", "K-INSIDER LAB").upper(), "bold", 20, ACCENT)
    for line in lines:
        s.text((64, y), line, "serif", size, "white")
        y += size * 1.08
    y += 26
    for line in dek_lines:
        s.text((64, y), line, "semi", 24, "#d5dae4")
        y += 34
    s.d.rounded_rectangle(((W - 150) * SC, (y - 52) * SC, (W - 64) * SC, (y - 16) * SC), radius=18 * SC, outline="white", width=3 * SC)
    s.text((W - 107, y - 34), "→", "bold", 24, "white", anchor="mm")
    # brand mark + credit
    s.rect((64, 56, 104, 96), fill=ACCENT, radius=8)
    s.text((84, 76), "K", "black", 24, "white", anchor="mm")
    s.text((116, 76), "K-INSIDER LAB", "bold", 20, "white", anchor="lm")
    s.text((W - 64, 76), f"No. {issue:03d}  ·  {build.nice_date(run_date).upper()}", "semi", 18, "#e8ebf1", anchor="rm")
    s.text((64, H - 52), f"Photo: {photo['user']} / Pixabay", "med", 15, "#9aa3b5")
    s.text((W - 64, H - 52), f"1 / {pages}", "semi", 16, "#9aa3b5", anchor="ra")
    return s


def cover_slide(story, issue, run_date, pages):
    s = Slide(dark=True)
    chrome(s, issue, run_date, 1, pages)
    s.text((64, 168), story["kicker"], "bold", 22, ACCENT)
    size = 70
    lines = s.wrap(story["headline"], "xbold", size, W - 128)
    while len(lines) > 4 and size > 50:
        size -= 4
        lines = s.wrap(story["headline"], "xbold", size, W - 128)
    y = 214
    for line in lines:
        s.text((64, y), line, "xbold", size, "white")
        y += size * 1.12
    hero = story["items"][0]
    y = y + 48
    x = s.pill(64, y, hero["status"][0], hero["status"][1])
    s.text((x + 18, y + 20), hero["name"], "semi", 22, "#c9cfdb", anchor="lm")
    chart(s, (64, y + 110, W - 64, H - 200), hero["series"], True, marker_idx=hero.get("marker_idx"),
          marker_label=hero.get("marker_label"), end_label=hero["change_text"], color=ACCENT,
          dates=story["dates"])
    s.text((W - 64, H - 132), "Swipe for the details  →", "bold", 22, "white", anchor="rm")
    return s


def profile_slide(story, item, idx, total, issue, run_date, page, pages):
    s = Slide(dark=False)
    chrome(s, issue, run_date, page, pages)
    s.text((64, 160), f"{idx:02d}", "black", 44, ACCENT)
    s.text((64 + s.width(f"{idx:02d} ", "black", 44), 172), f"/ {total:02d}   {story['segment_label']}",
           "bold", 20, MUTED)
    size = s.fit(item["name"], "black", 92, W - 128, 48)
    s.text((64, 228), item["name"], "black", size, TEXT)
    y = 228 + size * 1.18
    if item["kw"] != item["name"]:
        s.text((64, y), "Searched in Korea as", "med", 21, MUTED)
        s.text((64 + s.width("Searched in Korea as  ", "med", 21), y - 4), item["kw"], "kr", 24, TEXT)
        y += 52
    else:
        y += 8
    x = s.pill(64, y, item["status"][0], item["status"][1])
    s.text((x + 16, y + 20), item["type"], "semi", 20, MUTED, anchor="lm")
    y += 76
    s.text((64, y), item["change_text"], "black", 104, item["change_color"])
    s.text((64 + s.width(item["change_text"] + "  ", "black", 104), y + 30), item["change_caption"][0], "semi", 22, MUTED)
    s.text((64 + s.width(item["change_text"] + "  ", "black", 104), y + 62), item["change_caption"][1], "semi", 22, MUTED)
    y += 150
    chart_bottom = y + 300
    chart(s, (64, y + 30, W - 64, chart_bottom), item["series"], False, marker_idx=item.get("marker_idx"),
          marker_label=item.get("marker_label"), color=item["change_color"] if item["change_color"] != STEADY else ACCENT,
          baseline=item.get("baseline"), baseline_label="4-week average", dates=story["dates"])
    y = chart_bottom + 62
    stats = item.get("stats") or []
    if stats:
        col = (W - 128) / len(stats)
        s.line([(64, y), (W - 64, y)], LINE, 1.5)
        for n, (val, lab) in enumerate(stats):
            x = 64 + col * n
            s.text((x, y + 20), val, "xbold", 40, TEXT)
            s.text((x, y + 72), lab, "med", 17, MUTED)
        y += 120
        s.line([(64, y), (W - 64, y)], LINE, 1.5)
        y += 34
    s.text((64, y), "WHAT IT IS", "bold", 18, ACCENT)
    s.paragraph((64, y + 34), item["note"], "med", 28, TEXT, W - 128, max_lines=3)
    return s


def ranking_slide(story, issue, run_date, page, pages):
    s = Slide(dark=False)
    chrome(s, issue, run_date, page, pages)
    s.text((64, 160), story["table_kicker"], "bold", 22, ACCENT)
    s.paragraph((64, 200), story["table_title"], "xbold", 52, TEXT, W - 128)
    rows = story["table"]
    top = 360
    row_h = min(96, (H - 200 - top) // max(len(rows), 1))
    vmax = max(abs(r["value"]) for r in rows if r.get("value") is not None) or 1
    y = top
    for r in rows:
        if r.get("section"):
            s.text((64, y + row_h / 2), r["section"], "bold", 18, MUTED, anchor="lm")
            y += row_h * 0.7
            continue
        s.line([(64, y), (W - 64, y)], LINE, 1.5)
        s.text((64, y + row_h / 2), r["rank"], "bold", 24, FAINT, anchor="lm")
        name_size = s.fit(r["name"], "bold", 30, 420, 20)
        s.text((116, y + row_h / 2 - 12), r["name"], "bold", name_size, TEXT, anchor="lm")
        s.text((116, y + row_h / 2 + 22), r["sub"], "med", 17, MUTED, anchor="lm")
        bx0, bx1 = 560, W - 200
        bw = (bx1 - bx0) * min(abs(r["value"]) / vmax, 1)
        s.rect((bx0, y + row_h / 2 - 11, bx0 + max(bw, 4), y + row_h / 2 + 11), fill=r["color"], radius=5)
        s.text((W - 64, y + row_h / 2), r["value_text"], "black", 34, r["color"], anchor="rm")
        y += row_h
    s.line([(64, y), (W - 64, y)], LINE, 1.5)
    s.paragraph((64, y + 30), story["table_note"], "med", 19, MUTED, W - 128)
    return s


def close_slide(story, counts, issue, run_date, pages):
    s = Slide(dark=True)
    chrome(s, issue, run_date, pages, pages)
    s.text((64, 168), "K-INSIDER LAB", "bold", 22, ACCENT)
    y = s.paragraph((64, 214), "See what Korea buys before it reaches your market.", "xbold", 66, "white", W - 128, 1.12)
    facts = [
        (f"{counts.get('beauty', 0) + counts.get('food', 0)}", "K-beauty & K-food products and ingredients, tracked daily"),
        (f"{counts.get('brands', 0)}", "K-beauty brands ranked by Korean search demand"),
        ("12", "export markets in official Korea Customs data"),
        ("100%", "of breakout calls kept public — hits and misses"),
    ]
    y += 50
    for big, label in facts:
        s.text((64, y), big, "black", 64, ACCENT)
        s.paragraph((300, y + 10), label, "med", 26, "#d7dce6", W - 364, 1.2)
        y += 118
    s.rect((64, H - 330, W - 64, H - 160), fill=INK2, radius=18)
    s.text((100, H - 290), "Free weekly brief + daily data", "bold", 30, "white")
    s.text((100, H - 240), "kinsider-lab.com", "black", 40, ACCENT)
    s.text((W - 100, H - 236), f"Follow {HANDLE}", "semi", 21, "#9aa3b5", anchor="ra")
    return s


# ---------------------------------------------------------------- stories

def item_view(seg, it, note_map, active_kws, change=None, caption=("last 7 days vs.", "prior 4 weeks")):
    ch = it["momentum"] if change is None else change
    color = UP if ch >= 0.05 else (DOWN if ch <= -0.05 else STEADY)
    return {
        "name": it["en"], "kw": it["kw"], "type": it["type"],
        "note": note_map.get((seg["id"], it["kw"]), f"Korean {seg['title']} {it['type'].lower()}."),
        "series": it["series"], "baseline": it.get("baseline"),
        "status": status_for(it, active_kws), "change": ch, "change_text": build.pct(ch),
        "change_color": color, "change_caption": caption,
        "stats": [(f"{it['level']:.0f}", "Search index, last 7 days"),
                  (f"{it['baseline']:.0f}" if it.get("baseline") is not None else "–", "Prior 4-week average"),
                  (f"{max(rolling(it['series'])):.0f}", "8-week high (7-day avg)")],
    }


def momentum_story(snapshot, sid, kicker, label, headline_fn, tags):
    seg = seg_by_id(snapshot, sid)
    if not seg:
        return None
    rising, cooling, _ = build.ranked(seg)
    if len(rising) < 3:
        return None
    run = dt.date.fromisoformat(snapshot["run_date"])
    active = {x["kw"] for x in active_breakouts(run) if x["segment"] == sid}
    nm = notes()
    items = [item_view(seg, it, nm, active) for it in rising[:3]]
    table = [{"rank": str(n), "name": it["en"], "sub": f"{it['type']} · index {it['level']:.0f}",
              "value": it["momentum"], "value_text": build.pct(it["momentum"]), "color": UP}
             for n, it in enumerate(rising[:6], 1)]
    if cooling:
        table.append({"section": "COOLING MOST"})
        table += [{"rank": "↓", "name": it["en"], "sub": f"{it['type']} · index {it['level']:.0f}",
                   "value": it["momentum"], "value_text": build.pct(it["momentum"]), "color": DOWN}
                  for it in cooling[:2]]
    anchor = seg["anchor"]["en"]
    return {
        "segment": sid, "segment_label": label, "kicker": kicker,
        "headline": headline_fn(items[0]), "items": items, "dates": seg["dates"],
        "table_kicker": label, "table_title": "What's rising and cooling in Korea this week",
        "table": table,
        "table_note": f"Change: last 7 days vs. the prior 28 days. Index: {anchor}'s 8-week average = 100. "
                      f"Terms below index 10 are not ranked.",
        "tags": tags,
    }


def amount(ch):
    return f"{abs(ch) * 100:.0f}%"


def verb(ch):
    return "jumped" if ch >= 0.30 else ("rose" if ch >= 0.10 else "edged up")


def beauty_story(snapshot):
    return momentum_story(
        snapshot, "beauty", "KOREA DEMAND SIGNAL · K-BEAUTY", "K-BEAUTY",
        lambda h: f"Korean shoppers' searches for {h['name']} {verb(h['change'])} {amount(h['change'])} this week.",
        "#kbeauty #koreanskincare #kbeautytrends #koreanbeauty #beautybuyer #cosmeticsindustry #skincareingredients")


def brands_story(snapshot):
    return momentum_story(
        snapshot, "brands", "KOREA DEMAND SIGNAL · K-BEAUTY BRANDS", "K-BEAUTY BRANDS",
        lambda h: f"{h['name']} is the fastest-rising K-beauty brand in Korea this week, up {amount(h['change'])}.",
        "#kbeauty #kbeautybrands #koreanskincare #beautybuyer #cosmeticsindustry #brandstrategy")


def food_story(snapshot):
    return momentum_story(
        snapshot, "food", "KOREA DEMAND SIGNAL · K-FOOD", "K-FOOD",
        lambda h: f"{h['name']} is Korea's fastest-rising food search this week, up {amount(h['change'])}.",
        "#kfood #koreanfood #foodtrends #foodimport #foodbuyer #fmcg")


def signal_items(snapshot, signals, mode):
    """Join ledger entries with today's series. mode: 'breakout' or 'track'."""
    nm = notes()
    out = []
    run = dt.date.fromisoformat(snapshot["run_date"])
    active = {x["kw"] for x in active_breakouts(run)}
    for x in signals:
        seg = seg_by_id(snapshot, x["segment"])
        it = next((i for i in seg["items"] if i["kw"] == x["kw"]), None) if seg else None
        if not it:
            continue
        dates = seg["dates"]
        marker = dates.index(x["called"]) if x["called"] in dates else None
        if mode == "breakout":
            ch = it["level"] / x["early_baseline"] - 1 if x.get("early_baseline") else 0
            v = item_view(seg, it, nm, active, change=ch, caption=("last 7 days vs.", "3-week base"))
        else:
            key = "d28" if "d28" in x["checks"] else ("d14" if "d14" in x["checks"] else "d7")
            ch = x["checks"][key]["change"]
            v = item_view(seg, it, nm, active, change=ch, caption=(f"{key[1:]} days after", "our call"))
            v["status"] = ("HIT", UP) if ch > 0 else ("MISS", DOWN)
        v["marker_idx"] = marker
        v["marker_label"] = f"Called {build.nice_date(x['called'])}"
        v["segment_title"] = x["segment_title"]
        v["called"] = x["called"]
        out.append(v)
    return out


def breakout_story(snapshot):
    run = dt.date.fromisoformat(snapshot["run_date"])
    recent = [x for x in active_breakouts(run) if (run - dt.date.fromisoformat(x["called"])).days <= 14]
    items = signal_items(snapshot, sorted(recent, key=lambda x: x["called"], reverse=True), "breakout")
    if len(items) < 3:
        return None
    items.sort(key=lambda v: v["change"], reverse=True)
    table = [{"rank": str(n), "name": v["name"], "sub": f"{v['segment_title']} · called {build.nice_date(v['called'])}",
              "value": v["change"], "value_text": v["change_text"], "color": UP if v["change"] >= 0 else DOWN}
             for n, v in enumerate(items[:8], 1)]
    seg_dates = seg_by_id(snapshot, "beauty")["dates"] if seg_by_id(snapshot, "beauty") else items[0]["series"]
    return {
        "segment": "signals", "segment_label": "BREAKOUT SIGNALS", "kicker": "KOREA BREAKOUT SIGNALS",
        "headline": f"{len(items)} Korean shopping searches just held a two-week rise. {items[0]['name']} leads.",
        "items": items[:3], "dates": seg_dates,
        "table_kicker": "BREAKOUT SIGNALS · LAST 14 DAYS", "table_title": "Every live breakout call",
        "table": table,
        "table_note": "A call needs a rise that lasts two weeks, not a one-week spike. Every call is checked "
                      "after 7, 14 and 28 days and kept public: kinsider-lab.com/signals",
        "tags": "#kbeauty #kfood #trendforecasting #consumertrends #beautybuyer #marketintelligence",
    }


def track_story(snapshot):
    led = build.load_signals()
    done = [x for x in led["signals"] if x["checks"]]
    items = signal_items(snapshot, done, "track")
    if len(items) < 3:
        return None
    hits = sum(1 for v in items if v["change"] > 0)
    items.sort(key=lambda v: v["called"], reverse=True)
    table = [{"rank": "✓" if v["change"] > 0 else "✗", "name": v["name"],
              "sub": f"called {build.nice_date(v['called'])} · {v['change_caption'][0]}",
              "value": v["change"], "value_text": v["change_text"], "color": UP if v["change"] > 0 else DOWN}
             for v in items[:8]]
    seg_dates = seg_by_id(snapshot, "beauty")["dates"] if seg_by_id(snapshot, "beauty") else []
    return {
        "segment": "track", "segment_label": "TRACK RECORD", "kicker": "OUR CALLS, CHECKED",
        "headline": f"{hits} of {len(items)} breakout calls stayed above their base. Here is every one.",
        "items": items[:3], "dates": seg_dates,
        "table_kicker": "TRACK RECORD", "table_title": "Hits and misses, nothing removed",
        "table": table,
        "table_note": "Change vs. the 3-week base before the call, at the latest check (7, 14 or 28 days). "
                      "Full ledger: kinsider-lab.com/signals",
        "tags": "#kbeauty #kfood #trendforecasting #marketintelligence #consumertrends",
    }


def top_brands_story(snapshot):
    """'Koreans actually use': the brands with the most Korean demand, not just the fastest risers."""
    seg = seg_by_id(snapshot, "brands")
    if not seg:
        return None
    _, _, biggest = build.ranked(seg)
    biggest = [i for i in biggest if not i["is_anchor"] and i["momentum"] is not None][:8]
    if len(biggest) < 3:
        return None
    run = dt.date.fromisoformat(snapshot["run_date"])
    active = {x["kw"] for x in active_breakouts(run) if x["segment"] == "brands"}
    nm = notes()
    items = [item_view(seg, it, nm, active) for it in biggest[:3]]
    table = [{"rank": str(n), "name": it["en"], "sub": f"{it['type']} · {build.pct(it['momentum'])} this week",
              "value": it["level"], "value_text": f"{it['level']:.0f}", "color": ACCENT}
             for n, it in enumerate(biggest, 1)]
    return {
        "segment": "brands-top", "segment_label": "KOREANS ACTUALLY USE", "kicker": "KOREANS ACTUALLY USE · K-BEAUTY BRANDS",
        "headline": f"Not hype: the K-beauty brands Koreans search most right now. {items[0]['name']} leads.",
        "items": items, "dates": seg["dates"],
        "table_kicker": "KOREANS ACTUALLY USE", "table_title": "Korea's most-searched K-beauty brands this week",
        "table": table,
        "table_note": f"Search index, last 7 days ({seg['anchor']['en']}'s 8-week average = 100). "
                      "Demand from Korean shoppers, not ads or sponsored posts.",
        "tags": "#kbeauty #koreanskincare #kbeautybrands #whatkoreansuse #koreanbeauty #skincare",
    }


SERIES = {
    2: ("explained", "EXPLAINED", "K-BEAUTY & K-FOOD, EXPLAINED"),
    3: ("buysmart", "BUY SMART", "BUY K-BEAUTY & K-FOOD SMART"),
}


def editorial_story(snapshot, wd, offset=0):
    """Evergreen explainer from config/series.json, rotated weekly so nothing repeats for months."""
    key, label, kicker = SERIES[wd]
    bank = json.loads((Path(__file__).resolve().parent.parent / "config" / "series.json").read_text(encoding="utf-8"))[key]
    week = (dt.date.fromisoformat(snapshot["run_date"]) - LAUNCH).days // 7
    t = bank[(week + offset) % len(bank)]
    hero = None
    for seg in snapshot.get("segments", []):
        for it in seg.get("items", []):
            if t.get("kw") and it["kw"] == t["kw"] and it.get("series"):
                hero = {"series": it["series"], "dates": seg["dates"], "change": it["momentum"]}
    return {"editorial": True, "segment": key, "segment_label": label, "kicker": f"{kicker}",
            "headline": t["title"], "sub": t["sub"], "kr": t.get("kr", ""), "points": t["points"],
            "hero": hero, "items": [], "photo": t.get("photo"), "tags": t.get("tags", "") + " #kbeauty #kfood #korea"}


def choose(snapshot):
    """Mon trend, Tue Koreans-actually-use, Wed explained, Thu buy smart, Fri K-food, Sat track record, Sun price check."""
    wd = dt.date.fromisoformat(snapshot["run_date"]).weekday()  # 0 = Monday
    if wd == 6:
        return price_story(snapshot) or editorial_story(snapshot, 3, offset=26)
    if wd in SERIES:
        return editorial_story(snapshot, wd)
    plan = {0: [beauty_story], 1: [top_brands_story, brands_story], 4: [food_story],
            5: [track_story, breakout_story]}
    for fn in plan[wd] + [beauty_story]:
        story = fn(snapshot)
        if story:
            return story
    return None


ED_SRC = "K-INSIDER LAB research"
PRICE_SRC = "Prices: Naver Shopping, Korea (reference)"


def price_story(snapshot):
    path = ROOT / "data" / "prices.json"
    if not path.exists():
        return None
    pr = json.loads(path.read_text(encoding="utf-8"))
    if pr.get("date") != snapshot["run_date"] or len(pr.get("items", [])) < 3:
        return None
    return {"price": True, "segment": "price", "segment_label": "KOREA PRICE CHECK",
            "kicker": "KOREA PRICE CHECK · SUNDAY",
            "headline": f"What Koreans pay this week for {pr['items'][0]['brand']}, "
                        f"{pr['items'][1]['brand']} and {pr['items'][2]['brand']}.",
            "sub": "Rising brands in Korea, and the reference price Korean shoppers see online today.",
            "prices": pr["items"], "rate": pr["rate"], "rate_kind": pr["rate_kind"], "items": [],
            "tags": "#kbeauty #koreanskincare #kbeautyprices #oliveyoung #koreanbeauty"}


def price_cover(story, issue, run_date, pages):
    s = Slide(dark=True)
    chrome(s, issue, run_date, 1, pages, PRICE_SRC)
    s.text((64, 168), story["kicker"], "bold", 22, ACCENT)
    y = s.paragraph((64, 214), story["headline"], "xbold", 70, "white", W - 128, 1.12, max_lines=4)
    y = s.paragraph((64, y + 24), story["sub"], "med", 30, "#c9cfdb", W - 128, 1.3, max_lines=2)
    y += 50
    for p in story["prices"]:
        s.rect((64, y, W - 64, y + 150), fill=INK2, radius=18)
        s.text((100, y + 46), p["brand"], "xbold", 38, "white", anchor="lm")
        s.text((100, y + 104), f"{build.pct(p['momentum'])} Korean searches this week", "semi", 22, "#9aa3b5", anchor="lm")
        s.text((W - 100, y + 60), f"₩{p['price_krw']:,}", "black", 46, ACCENT, anchor="rm")
        s.text((W - 100, y + 110), f"≈ US${p['price_usd']:,.2f}", "semi", 24, "#c9cfdb", anchor="rm")
        y += 172
    s.text((W - 64, H - 132), "Swipe  →", "bold", 22, "white", anchor="rm")
    return s


def price_slide(story, n, p, issue, run_date, page, pages):
    s = Slide(dark=False)
    chrome(s, issue, run_date, page, pages, PRICE_SRC)
    s.text((64, 160), f"{n:02d}", "black", 44, ACCENT)
    s.text((64 + s.width(f"{n:02d} ", "black", 44), 172), f"/ 03   KOREA PRICE CHECK", "bold", 20, MUTED)
    size = s.fit(p["brand"], "black", 96, W - 128, 48)
    s.text((64, 228), p["brand"], "black", size, TEXT)
    s.text((64, 228 + size * 1.25), "Searched in Korea as", "med", 21, MUTED)
    s.text((64 + s.width("Searched in Korea as  ", "med", 21), 228 + size * 1.25 - 4), p["kw"], "kr", 24, TEXT)
    y = 228 + size * 1.25 + 80
    s.text((64, y), "MOST RELEVANT LISTING IN KOREA", "bold", 18, ACCENT)
    y = s.paragraph((64, y + 36), p["title"], "kr", 34, TEXT, W - 128, 1.35, max_lines=3)
    y += 40
    s.line([(64, y), (W - 64, y)], LINE, 1.5)
    s.text((64, y + 40), f"₩{p['price_krw']:,}", "black", 110, TEXT)
    s.text((64, y + 175), f"≈ US${p['price_usd']:,.2f}  ·  lowest listed price, {p['mall']}", "semi", 26, MUTED)
    y += 260
    s.line([(64, y), (W - 64, y)], LINE, 1.5)
    s.text((64, y + 40), "BUYING ABROAD?", "bold", 18, ACCENT)
    s.paragraph((64, y + 76), "Use this as a reference: prices abroad add shipping, duties and tax. Buy from the "
                "brand's official store or an authorised retailer, and compare the same size.",
                "med", 28, TEXT, W - 128, 1.38, max_lines=4)
    return s


def price_note(story, issue, run_date, page, pages):
    s = Slide(dark=False)
    chrome(s, issue, run_date, page, pages, PRICE_SRC)
    s.text((64, 160), "HOW TO READ THESE PRICES", "bold", 22, ACCENT)
    y = s.paragraph((64, 210), "Korean prices change daily, and many are sale prices.", "xbold", 56, TEXT, W - 128, 1.12)
    rk = "live" if story["rate_kind"] == "live" else "approximate"
    for t in [f"Prices are the lowest listed price on Naver Shopping in Korea on {build.nice_date(run_date)}, "
              "for the listing that best matches the brand. They are references, not offers.",
              f"US$ figures use a {rk} exchange rate of ₩{story['rate']:,.0f} per dollar.",
              "Many Korean shops do not ship abroad or need a Korean phone number to sign up.",
              "Abroad, compare the same product and size, and buy from official or authorised sellers."]:
        s.rect((64, y + 48, 74, y + 58), fill=ACCENT, radius=5)
        y = s.paragraph((100, y + 30), t, "med", 32, TEXT, W - 164, 1.38, max_lines=4) + 10
    return s


def editorial_cover(story, issue, run_date, pages):
    s = Slide(dark=True)
    chrome(s, issue, run_date, 1, pages, ED_SRC)
    s.text((64, 168), story["kicker"], "bold", 22, ACCENT)
    size = 76
    lines = s.wrap(story["headline"], "xbold", size, W - 128)
    while len(lines) > 4 and size > 52:
        size -= 4
        lines = s.wrap(story["headline"], "xbold", size, W - 128)
    y = 214
    for line in lines:
        s.text((64, y), line, "xbold", size, "white")
        y += size * 1.12
    y = s.paragraph((64, y + 30), story["sub"], "med", 30, "#c9cfdb", W - 128, 1.3, max_lines=3)
    hero = story.get("hero")
    if hero:
        s.text((64, y + 50), "Korean shopping-search demand, last 8 weeks", "semi", 21, "#9aa3b5")
        chart(s, (64, y + 100, W - 64, H - 200), hero["series"], True, end_label=build.pct(hero["change"]),
              color=ACCENT, dates=hero["dates"])
    elif story.get("kr"):
        s.rect((64, y + 60, W - 64, H - 220), fill=INK2, radius=24)
        s.text((W / 2, (y + 60 + H - 220) / 2 - 20), story["kr"], "kr", 120, "white", anchor="mm")
        s.text((W / 2, (y + 60 + H - 220) / 2 + 80), "how it's written in Korean", "semi", 22, "#9aa3b5", anchor="mm")
    s.text((W - 64, H - 132), "Swipe  →", "bold", 22, "white", anchor="rm")
    return s


def point_slide(story, n, point, issue, run_date, page, pages):
    s = Slide(dark=False)
    chrome(s, issue, run_date, page, pages, ED_SRC)
    s.text((64, 160), f"{n:02d}", "black", 44, ACCENT)
    s.text((64 + s.width(f"{n:02d} ", "black", 44), 172), f"/ {len(story['points']):02d}   {story['segment_label']}",
           "bold", 20, MUTED)
    s.text((W - 40, 120), f"{n}", "black", 420, "#ece9e3", anchor="ra")
    y = s.paragraph((64, 290), point[0], "black", 84, TEXT, W - 128, 1.08, max_lines=3)
    s.rect((64, y + 36, 184, y + 46), fill=ACCENT, radius=5)
    s.paragraph((64, y + 100), point[1], "semi", 44, "#2b3240", W - 128, 1.38, max_lines=7)
    if len(point) > 2 and point[2]:
        s.rect((64, H - 300, W - 64, H - 150), fill="#f4f5f7", radius=18)
        s.text((100, H - 262), "IN KOREAN", "bold", 18, ACCENT)
        s.text((100, H - 214), point[2], "kr", 40, TEXT)
    else:
        day = "Wednesday" if story["segment"] == "explained" else "Thursday"
        s.rect((64, H - 300, W - 64, H - 150), fill="#f4f5f7", radius=18)
        s.text((100, H - 262), "SAVE THIS POST", "bold", 18, ACCENT)
        s.text((100, H - 214), f"New {story['segment_label'].title()} every {day}", "xbold", 34, TEXT)
    return s


def editorial_caption(story, linkedin=False):
    lines = [story["headline"], "", story["sub"], ""]
    for n, p in enumerate(story["points"], 1):
        lines.append(f"{n}. {p[0]}")
    if linkedin:
        lines += ["", "Practical K-beauty and K-food knowledge for buyers, sellers and creators abroad, every week, "
                      "alongside daily Korean demand data: https://www.kinsider-lab.com",
                  "", "#KBeauty #KFood #Korea #ConsumerTrends"]
    else:
        lines += ["", "Save this for later. New K-beauty & K-food data every weekday; free weekly brief: link in bio "
                      "(kinsider-lab.com)", "", story["tags"]]
    return "\n".join(lines)


def caption(story, run_date):
    lines = [story["headline"], ""]
    for v in story["items"]:
        lines.append(f"→ {v['name']} {v['change_text']} ({v['status'][0].title()}). {v['note']}")
    lines += ["", "Swipe for the 8-week charts and the full ranking.", "",
              "K-INSIDER LAB tracks Korean shopping searches every day so buyers abroad can see "
              "K-beauty and K-food demand before it travels. Free weekly brief: link in bio (kinsider-lab.com)",
              "", f"Data: Naver shopping-search clicks in Korea, to {build.nice_date(run_date)}.", "", story["tags"]]
    return "\n".join(lines)


def linkedin_caption(story, run_date):
    """LinkedIn is the trust/B2B channel: lead with what it means for buyers, fewer hashtags."""
    lines = [story["headline"], "", "What buyers and brand teams should note:"]
    for v in story["items"]:
        lines.append(f"• {v['name']} {v['change_text']} ({v['status'][0].lower()}): {v['note']}")
    lines += ["",
              "Korean shoppers often move first: ingredients and formats that gain search demand in Korea tend to "
              "reach export shelves later. We measure that demand daily from Naver shopping searches, and every "
              "breakout call we make stays public with its result.",
              "", "Full data, 8-week charts and the free Monday brief: https://www.kinsider-lab.com",
              "", f"Data to {build.nice_date(run_date)}. Source: Naver DataLab Shopping Insight.",
              "", "#KBeauty #KFood #MarketIntelligence #ConsumerTrends"]
    return "\n".join(lines)


REEL_SECONDS = [4, 3, 3, 3, 3, 3]  # cover holds a beat longer; ~19 s total


def make_reel(out_dir, names):
    """9:16 Reel from the slides (slides centred on the brand background).

    Reels reach non-followers; carousels mostly reach followers, so the same
    research ships in both formats. Returns False (carousel still posts) when
    ffmpeg is missing or fails.
    """
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        return False
    inputs, chains = [], []
    for i, name in enumerate(names):
        inputs += ["-loop", "1", "-t", str(REEL_SECONDS[min(i, len(REEL_SECONDS) - 1)]), "-i", str(out_dir / name)]
        chains.append(f"[{i}:v]scale=1080:1350,pad=1080:1920:0:285:color=0xD9481C,setsar=1,fps=30[v{i}]")
    graph = ";".join(chains) + ";" + "".join(f"[v{i}]" for i in range(len(names))) + f"concat=n={len(names)}:v=1:a=0,format=yuv420p[out]"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs,
           "-f", "lavfi", "-t", str(sum(REEL_SECONDS[:len(names)])), "-i", "anullsrc=r=44100:cl=stereo",
           "-filter_complex", graph, "-map", "[out]", "-map", f"{len(names)}:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-shortest",
           "-movflags", "+faststart", str(out_dir / "reel.mp4")]
    try:
        subprocess.run(cmd, check=True, timeout=300)
        return True
    except Exception as exc:
        print(f"Reel skipped: {exc}")
        return False


def render(story, snapshot, out_dir):
    run = snapshot["run_date"]
    issue = (dt.date.fromisoformat(run) - LAUNCH).days + 1
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    from . import photos
    photo = photos.pick(story, out_dir / "photo.jpg", run)
    if story.get("price"):
        pages = 6
        slides = [price_cover(story, issue, run, pages)]
        slides += [price_slide(story, n, p, issue, run, n + 1, pages) for n, p in enumerate(story["prices"], 1)]
        slides.append(price_note(story, issue, run, 5, pages))
    elif story.get("editorial"):
        pages = 2 + len(story["points"])
        slides = [editorial_cover(story, issue, run, pages)]
        slides += [point_slide(story, n, p, issue, run, n + 1, pages) for n, p in enumerate(story["points"], 1)]
    else:
        pages = 2 + len(story["items"]) + 1
        slides = [cover_slide(story, issue, run, pages)]
        for n, item in enumerate(story["items"], 1):
            slides.append(profile_slide(story, item, n, len(story["items"]), issue, run, n + 1, pages))
        slides.append(ranking_slide(story, issue, run, pages - 1, pages))
    if photo:  # magazine-style photo cover; the inside slides carry the data
        slides[0] = photo_cover(story, photo, issue, run, pages)
    slides.append(close_slide(story, tracked_counts(snapshot), issue, run, pages))
    names = []
    for n, s in enumerate(slides, 1):
        name = f"{n:02d}.jpg"
        s.save(out_dir / name)
        names.append(name)
    if story.get("price"):
        story["points"] = [(f"{p['brand']}: ₩{p['price_krw']:,} (≈ US${p['price_usd']:,.2f})",) for p in story["prices"]]
    ed = story.get("editorial") or story.get("price")
    (out_dir / "caption.txt").write_text(editorial_caption(story) if ed else caption(story, run), encoding="utf-8")
    (out_dir / "caption-linkedin.txt").write_text(
        editorial_caption(story, True) if ed else linkedin_caption(story, run), encoding="utf-8")
    meta = {"date": run, "issue": issue, "story": story["segment"], "title": story["headline"], "slides": names}
    from . import reel
    if reel.make(story, out_dir / "reel.mp4") or make_reel(out_dir, names):
        meta["reel"] = "reel.mp4"
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


def prune(today):
    for p in OUT.iterdir() if OUT.exists() else []:
        stem = p.name.split(".")[0]
        try:
            day = dt.date.fromisoformat(stem)
        except ValueError:
            continue
        if (today - day).days > KEEP_DAYS:
            shutil.rmtree(p) if p.is_dir() else p.unlink()


def main():
    latest_path = ROOT / "data" / "latest.json"
    if not latest_path.exists():
        print("No data yet; no card.")
        return 0
    snapshot = json.loads(latest_path.read_text(encoding="utf-8"))
    if snapshot.get("status") != "ok":
        print("Data not configured; no card.")
        return 0
    story = choose(snapshot)
    if not story:
        print("No story qualifies today (fresh data with at least 3 ranked terms required).")
        return 0
    meta = render(story, snapshot, OUT / snapshot["run_date"])
    prune(dt.date.fromisoformat(snapshot["run_date"]))
    print(f"Carousel written: cards/{meta['date']}/ ({len(meta['slides'])} slides, {meta['story']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def todays_carousel(day):
    """(folder, meta, caption) for a date's carousel, or None. Used by the publishers."""
    folder = OUT / day
    meta_path = folder / "meta.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not all((folder / n).exists() for n in meta["slides"]):
        return None
    return folder, meta, (folder / "caption.txt").read_text(encoding="utf-8")


def deck_pdf(folder, meta, out_path):
    """Slides as one PDF: LinkedIn shows uploaded documents as a swipeable carousel."""
    pages = [Image.open(folder / n).convert("RGB") for n in meta["slides"]]
    pages[0].save(out_path, "PDF", save_all=True, append_images=pages[1:], resolution=150)
    return out_path
