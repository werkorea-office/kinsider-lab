"""Daily social card generator. Run: python -m pipeline.cards

Produces cards/<run_date>.png (1080x1080) and cards/<run_date>.txt (caption)
from data/latest.json, using the same ranking rules as the website. If the
latest data is not fresh, no card is produced: social posts never repeat stale
numbers as if they were new.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import build

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
S = 1080
INK, MUTED, LINE, BG = "#121826", "#6b7385", "#e4e6eb", "#fbfaf7"
ACCENT, UP, DOWN = "#d9481c", "#127a4f", "#b42318"


def font(size, bold=False):
    return ImageFont.truetype(str(FONTS / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")), size)


def fit(draw, text, size, bold, max_w):
    while size > 18 and draw.textlength(text, font=font(size, bold)) > max_w:
        size -= 2
    return font(size, bold)


def render(snapshot, seg, out_png):
    rising, cooling, _ = build.ranked(seg)
    rows = rising[:5]
    img = Image.new("RGB", (S, S), BG)
    d = ImageDraw.Draw(img)
    # header band
    d.rectangle([0, 0, S, 150], fill=INK)
    d.rounded_rectangle([60, 47, 116, 103], radius=12, fill=ACCENT)
    d.text((88, 75), "K", font=font(38, True), fill="white", anchor="mm")
    d.text((136, 75), "K-INSIDER", font=font(30, True), fill="white", anchor="lm")
    w = d.textlength("K-INSIDER ", font=font(30, True))
    d.text((136 + w, 75), "LAB", font=font(30, True), fill=ACCENT, anchor="lm")
    d.text((S - 60, 75), build.nice_date(snapshot["run_date"]), font=font(26), fill="#c9cfdb", anchor="rm")
    # title
    d.text((60, 205), f"RISING IN KOREA · {seg['title'].upper()}", font=font(26, True), fill=ACCENT)
    d.text((60, 245), "Shopping-search momentum,", font=font(52, True), fill=INK)
    d.text((60, 307), "last 7 days vs. prior 4 weeks", font=font(52, True), fill=INK)
    # rows
    y = 410
    for n, it in enumerate(rows, 1):
        d.line([60, y, S - 60, y], fill=LINE, width=2)
        d.text((60, y + 58), str(n), font=font(40, True), fill=MUTED, anchor="lm")
        name_font = fit(d, it["en"], 44, True, 640)
        d.text((125, y + 42), it["en"], font=name_font, fill=INK, anchor="lm")
        d.text((125, y + 88), f"{it['type']} · index {it['level']:.0f}", font=font(24), fill=MUTED, anchor="lm")
        color = UP if it["momentum"] >= 0.05 else (DOWN if it["momentum"] <= -0.05 else MUTED)
        d.text((S - 60, y + 58), build.pct(it["momentum"]), font=font(52, True), fill=color, anchor="rm")
        y += 116
    d.line([60, y, S - 60, y], fill=LINE, width=2)
    if cooling and len(rows) < 5:
        c = cooling[0]
        d.text((60, y + 50), "COOLING MOST", font=font(24, True), fill=MUTED, anchor="lm")
        d.text((60, y + 95), c["en"], font=fit(d, c["en"], 40, True, 700), fill=INK, anchor="lm")
        d.text((S - 60, y + 95), build.pct(c["momentum"]), font=font(46, True), fill=DOWN, anchor="rm")
    # footer
    d.text((60, S - 70), "kinsider-lab.com", font=font(30, True), fill=INK, anchor="lm")
    d.text((S - 60, S - 70), "Source: Naver DataLab Shopping Insight", font=font(22), fill=MUTED, anchor="rm")
    img.save(out_png, optimize=True)


def caption(snapshot, seg):
    rising, cooling, _ = build.ranked(seg)
    lines = [f"Rising in Korean online shopping this week ({build.nice_date(snapshot['run_date'])}):", ""]
    for it in rising[:5]:
        lines.append(f"• {it['en']} {build.pct(it['momentum'])}")
    if cooling:
        lines += ["", f"Cooling: {cooling[0]['en']} {build.pct(cooling[0]['momentum'])}"]
    lines += ["", "Daily K-beauty & K-food demand data, free: link in bio (kinsider-lab.com)",
              "Data: Naver DataLab shopping-search clicks, 7 days vs prior 28 days.", "",
              "#kbeauty #koreanskincare #kbeautytrends #koreanbeauty #beautybuyer #cosmeticsindustry #kfood"]
    return "\n".join(lines)


def main():
    latest_path = ROOT / "data" / "latest.json"
    if not latest_path.exists():
        print("No data yet; no card.")
        return 0
    snapshot = json.loads(latest_path.read_text(encoding="utf-8"))
    if snapshot.get("status") != "ok":
        print("Data not configured; no card.")
        return 0
    seg = next((s for s in snapshot["segments"] if s["id"] == "beauty"), None)
    if not seg or seg.get("fresh") is False:
        print("Beauty data not fresh today; no card (stale numbers are never re-posted).")
        return 0
    rising, _, _ = build.ranked(seg)
    if len(rising) < 3:
        print("Fewer than 3 qualified risers; no card today.")
        return 0
    out = ROOT / "cards"
    out.mkdir(exist_ok=True)
    run = snapshot["run_date"]
    render(snapshot, seg, out / f"{run}.png")
    (out / f"{run}.txt").write_text(caption(snapshot, seg), encoding="utf-8")
    print(f"Card written: cards/{run}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
