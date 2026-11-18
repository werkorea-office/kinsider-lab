"""Daily social card generator. Run: python -m pipeline.cards

Produces cards/<run_date>.png (1080x1080) and cards/<run_date>.txt (caption).
The card type follows a weekly schedule (KST weekday of the run):
  Mon  K-beauty brands rising          Wed  breakout signals (falls back to beauty)
  Fri  K-food rising                   Sat  track record (falls back to beauty)
  other days  K-beauty categories & ingredients rising
Rules: only fresh data is used, the same ranking rules as the website apply,
and a card with fewer than 3 qualified rows is never published.
"""
import datetime as dt
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import build

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
S = 1080
INK, MUTED, LINE, BG = "#121826", "#6b7385", "#e4e6eb", "#fbfaf7"
ACCENT, UP, DOWN = "#d9481c", "#127a4f", "#b42318"
TAGS = "#kbeauty #koreanskincare #kbeautytrends #koreanbeauty #beautybuyer #cosmeticsindustry"


def font(size, bold=False):
    return ImageFont.truetype(str(FONTS / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")), size)


def fit(draw, text, size, bold, max_w):
    while size > 18 and draw.textlength(text, font=font(size, bold)) > max_w:
        size -= 2
    return font(size, bold)


def color_for(change):
    return UP if change >= 0.05 else (DOWN if change <= -0.05 else MUTED)


def render(run_date, label, title_lines, rows, out_png, extra=None):
    """rows: list of (name, subline, value_text, color)."""
    img = Image.new("RGB", (S, S), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, S, 150], fill=INK)
    d.rounded_rectangle([60, 47, 116, 103], radius=12, fill=ACCENT)
    d.text((88, 75), "K", font=font(38, True), fill="white", anchor="mm")
    d.text((136, 75), "K-INSIDER", font=font(30, True), fill="white", anchor="lm")
    w = d.textlength("K-INSIDER ", font=font(30, True))
    d.text((136 + w, 75), "LAB", font=font(30, True), fill=ACCENT, anchor="lm")
    d.text((S - 60, 75), build.nice_date(run_date), font=font(26), fill="#c9cfdb", anchor="rm")
    d.text((60, 205), label, font=font(26, True), fill=ACCENT)
    y = 245
    for line in title_lines:
        d.text((60, y), line, font=fit(d, line, 52, True, S - 120), fill=INK)
        y += 62
    y = max(y + 41, 410)
    for n, (name, sub, value, color) in enumerate(rows, 1):
        d.line([60, y, S - 60, y], fill=LINE, width=2)
        d.text((60, y + 58), str(n), font=font(40, True), fill=MUTED, anchor="lm")
        d.text((125, y + 42), name, font=fit(d, name, 44, True, 600), fill=INK, anchor="lm")
        d.text((125, y + 88), sub, font=fit(d, sub, 24, False, 600), fill=MUTED, anchor="lm")
        d.text((S - 60, y + 58), value, font=fit(d, value, 52, True, 260), fill=color, anchor="rm")
        y += 116
    d.line([60, y, S - 60, y], fill=LINE, width=2)
    if extra and len(rows) < 5:
        title, name, value, color = extra
        d.text((60, y + 50), title, font=font(24, True), fill=MUTED, anchor="lm")
        d.text((60, y + 95), name, font=fit(d, name, 40, True, 700), fill=INK, anchor="lm")
        d.text((S - 60, y + 95), value, font=font(46, True), fill=color, anchor="rm")
    d.text((60, S - 70), "kinsider-lab.com", font=font(30, True), fill=INK, anchor="lm")
    d.text((S - 60, S - 70), "Source: Naver DataLab Shopping Insight", font=font(22), fill=MUTED, anchor="rm")
    img.save(out_png, optimize=True)


def seg_by_id(snapshot, sid):
    seg = next((s for s in snapshot["segments"] if s["id"] == sid), None)
    return seg if seg and seg.get("status") == "ok" and seg.get("fresh") is not False else None


def rising_card(snapshot, sid, label, title_lines, intro, hashtags):
    seg = seg_by_id(snapshot, sid)
    if not seg:
        return None
    rising, cooling, _ = build.ranked(seg)
    if len(rising) < 3:
        return None
    rows = [(i["en"], f"{i['type']} · index {i['level']:.0f}", build.pct(i["momentum"]), color_for(i["momentum"]))
            for i in rising[:5]]
    extra = ("COOLING MOST", cooling[0]["en"], build.pct(cooling[0]["momentum"]), DOWN) if cooling else None
    lines = [intro, ""] + [f"• {i['en']} {build.pct(i['momentum'])}" for i in rising[:5]]
    if cooling:
        lines += ["", f"Cooling: {cooling[0]['en']} {build.pct(cooling[0]['momentum'])}"]
    caption = lines + ["", "Daily K-beauty & K-food demand data, free: link in bio (kinsider-lab.com)",
                       "Data: Naver DataLab shopping-search clicks, last 7 days vs prior 28 days.", "", hashtags]
    return label, title_lines, rows, extra, "\n".join(caption)


def breakout_card(snapshot):
    led = build.load_signals()
    run = dt.date.fromisoformat(snapshot["run_date"])
    active = [x for x in led["signals"] if (run - dt.date.fromisoformat(x["called"])).days <= 14]
    active.sort(key=lambda x: x["called"], reverse=True)
    if len(active) < 3:
        return None
    rows = []
    for x in active[:5]:
        ch = x["latest"]["level"] / x["early_baseline"] - 1 if x.get("early_baseline") else 0
        rows.append((x["en"], f"{x['segment_title']} · called {build.nice_date(x['called'])}", build.pct(ch), color_for(ch)))
    caption = ["Breakout signals from Korean online shopping: rises that held for two weeks.", ""]
    caption += [f"• {x['en']} ({x['segment_title']}), called {build.nice_date(x['called'])}" for x in active[:5]]
    caption += ["", "Every call is tracked publicly after 7, 14 and 28 days, hits and misses: "
                    "link in bio (kinsider-lab.com/signals)", "", TAGS]
    return ("BREAKOUT SIGNALS · KOREA", ["Two-week rises in Korean", "shopping searches"], rows, None, "\n".join(caption))


def track_card(snapshot):
    led = build.load_signals()
    done = [x for x in led["signals"] if x["checks"]]
    if len(done) < 3:
        return None
    done.sort(key=lambda x: max(x["checks"]), reverse=True)
    rows = []
    for x in done[:5]:
        key = "d28" if "d28" in x["checks"] else ("d14" if "d14" in x["checks"] else "d7")
        ch = x["checks"][key]["change"]
        rows.append((x["en"], f"called {build.nice_date(x['called'])} · +{key[1:]} days", build.pct(ch), color_for(ch)))
    caption = ["Track record: how our breakout calls did afterwards (hits and misses, nothing removed).", ""]
    caption += [f"• {r[0]}: {r[2]} ({r[1]})" for r in rows]
    caption += ["", "Full public ledger: link in bio (kinsider-lab.com/signals)", "", TAGS]
    return ("TRACK RECORD", ["What happened after", "our breakout calls"], rows, None, "\n".join(caption))


def beauty_card(snapshot):
    return rising_card(snapshot, "beauty", "RISING IN KOREA · K-BEAUTY",
                       ["Shopping-search momentum,", "last 7 days vs. prior 4 weeks"],
                       f"Rising in Korean online shopping this week ({build.nice_date(snapshot['run_date'])}):", TAGS)


def choose(snapshot):
    wd = dt.date.fromisoformat(snapshot["run_date"]).weekday()  # 0 = Monday
    plan = {
        0: lambda: rising_card(snapshot, "brands", "K-BEAUTY BRANDS · KOREA",
                               ["Brands gaining ground", "in Korean shopping searches"],
                               "K-beauty brands gaining the most search demand in Korea this week:", TAGS),
        2: lambda: breakout_card(snapshot),
        4: lambda: rising_card(snapshot, "food", "RISING IN KOREA · K-FOOD",
                               ["K-food shopping momentum,", "last 7 days vs. prior 4 weeks"],
                               "K-food rising in Korean online shopping this week:",
                               "#kfood #koreanfood #koreansnacks #ramyeon #foodimport #foodbuyer"),
        5: lambda: track_card(snapshot),
    }
    chosen = plan[wd]() if wd in plan else None
    return chosen or beauty_card(snapshot)


def main():
    latest_path = ROOT / "data" / "latest.json"
    if not latest_path.exists():
        print("No data yet; no card.")
        return 0
    snapshot = json.loads(latest_path.read_text(encoding="utf-8"))
    if snapshot.get("status") != "ok":
        print("Data not configured; no card.")
        return 0
    chosen = choose(snapshot)
    if not chosen:
        print("No card qualifies today (fresh data with at least 3 rows required).")
        return 0
    label, title_lines, rows, extra, caption = chosen
    out = ROOT / "cards"
    out.mkdir(exist_ok=True)
    run = snapshot["run_date"]
    render(run, label, title_lines, rows, out / f"{run}.png", extra)
    (out / f"{run}.txt").write_text(caption, encoding="utf-8")
    print(f"Card written: cards/{run}.png ({label})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
