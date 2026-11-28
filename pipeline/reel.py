"""Reel 2.0: a native 9:16, ~9-second motion video built for the first second.

Lessons from the first reel (19 s slideshow of the carousel): 90% skipped, 2 s average watch,
most drop-off inside 1 s. So: a full-screen number or claim at frame 1, large type, something
moving every ~1.5 s, short, a clear follow prompt at the end, and a soft generated soundtrack
(no licensed music; nothing to clear).

Scenes (seconds): hook 0-2.2 | chart draws or points pop 2.2-5.6 | top three / prices 5.6-8.2 |
follow card 8.2-9.6. Frames are drawn with Pillow and piped straight into ffmpeg.
"""
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H, FPS = 1080, 1920, 30
DUR = 9.6
INK, INK2, ACCENT, WHITE, MUTED, UP = (15, 20, 32), (27, 34, 50), (224, 82, 31), (255, 255, 255), (154, 163, 181), (46, 204, 133)
_fc = {}


def font(kind, size):
    from .cards import FONTS, FONT_FILES
    key = (kind, size)
    if key not in _fc:
        _fc[key] = ImageFont.truetype(str(FONTS / FONT_FILES[kind]), size)
    return _fc[key]


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def wrap(d, text, f, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=f) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit(d, text, kind, size, width, min_size=60):
    while size > min_size and d.textlength(text, font=font(kind, size)) > width:
        size -= 6
    return size


def plan(story):
    """Turn any story into the four reel scenes."""
    if story.get("price"):
        ps = story["prices"]
        return {"kicker": "KOREA PRICE CHECK", "big": f"₩{ps[0]['price_krw']:,}",
                "hook": f"What Koreans pay for {ps[0]['brand']}", "series": None,
                "points": [], "rows": [(p["brand"], f"₩{p['price_krw']:,}", f"≈ US${p['price_usd']:,.0f}") for p in ps]}
    if story.get("word"):
        import re
        sents = [story["headline"]] + [x.strip() for x in re.split(r"(?<=[.!?])\s+", story["body"]) if x.strip()][:2]
        return {"kicker": "KOREAN WORD OF THE DAY", "big": None, "kr": story["kr"], "hook": story["topic"],
                "series": None, "points": sents, "rows": []}
    if story.get("editorial"):
        return {"kicker": story["segment_label"], "big": None, "hook": story["headline"], "series": None,
                "points": [p[0] for p in story["points"]], "rows": []}
    # Lead with the biggest number in the story: '+353%' stops thumbs, '+18%' does not.
    it = max(story["items"], key=lambda i: i.get("momentum") or 0)
    rows = [(i["name"], i["change_text"], i.get("type", "")) for i in story["items"][:3]]
    return {"kicker": story["kicker"].split("·")[0].strip() or "KOREA DEMAND SIGNAL",
            "big": it["change_text"], "hook": f"Korean searches for {it['name']} this week",
            "series": it.get("series"), "points": [], "rows": rows}


def background(photo_path):
    """Darkened, cropped cover photo for the hook and follow scenes (None if no photo)."""
    try:
        im = Image.open(photo_path).convert("RGB")
    except Exception:
        return None
    r = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * r + 1), int(im.height * r + 1)), Image.LANCZOS)
    left, top = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((left, top, left + W, top + H))
    return Image.blend(im, Image.new("RGB", (W, H), INK), 0.62)


def draw_frame(p, t):
    bg = p.get("bg")
    photo_scene = bg is not None and (t < 2.2 or t >= (8.2 if p["rows"] else 5.6) or (not p["series"] and not p["rows"]))
    img = bg.copy() if photo_scene else Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    # brand bar
    d.rounded_rectangle((72, 110, 132, 170), 12, fill=ACCENT)
    d.text((102, 140), "K", font=font("black", 40), fill=WHITE, anchor="mm")
    d.text((152, 140), "K-INSIDER", font=font("bold", 34), fill=WHITE, anchor="lm")
    d.text((152 + d.textlength("K-INSIDER ", font=font("bold", 34)), 140), "LAB", font=font("bold", 34), fill=ACCENT, anchor="lm")
    # progress bar keeps the eye moving
    d.rectangle((0, H - 10, int(W * t / DUR), H), fill=ACCENT)

    if t < 2.2:                                   # 1) hook, readable at frame 1
        a = ease(t / 0.35)
        d.text((72, 470), p["kicker"], font=font("bold", 40), fill=ACCENT)
        if p.get("kr"):
            ksz = fit(d, p["kr"], "kr", 220, W - 144, 90)
            d.text((W // 2, 720 + int((1 - a) * 60)), p["kr"], font=font("kr", ksz), fill=WHITE, anchor="mm")
            d.text((W // 2, 900), "What does it mean in Korea?", font=font("semi", 44), fill=MUTED, anchor="mm")
            for i, line in enumerate(wrap(d, f"From: {p['hook']}", font("bold", 40), W - 200)[:2]):
                d.text((W // 2, 1000 + i * 52), line, font=font("bold", 40), fill=ACCENT, anchor="mm")
            return img
        if p["big"]:
            size = fit(d, p["big"], "black", 300, W - 144, 120)
            y = 640 + int((1 - a) * 60)
            d.text((W // 2, y + size // 2), p["big"], font=font("black", size), fill=ACCENT if "₩" in p["big"] else UP, anchor="mm")
            y += size + 80
        else:
            y = 600
        f = font("xbold", 84 if p["big"] else 96)
        for line in wrap(d, p["hook"], f, W - 144)[:5]:
            d.text((72, y), line, font=f, fill=WHITE)
            y += int(f.size * 1.15)
        return img

    end2 = 5.6 if p["rows"] else 8.2
    if t < end2:                                  # 2) motion: chart draws, or points pop in
        k = (t - 2.2) / (end2 - 2.2)
        if p["series"]:
            raw = p["series"][-62:]
            s = [sum(raw[max(0, i - 6):i + 1]) / len(raw[max(0, i - 6):i + 1]) for i in range(len(raw))][6:]
            lo, hi = min(s), max(s)
            x0, x1, y0, y1 = 72, W - 72, 860, 1480
            pts = [(x0 + (x1 - x0) * i / (len(s) - 1), y1 - (y1 - y0) * (v - lo) / ((hi - lo) or 1)) for i, v in enumerate(s)]
            n = max(2, int(len(pts) * ease(k * 1.25)))
            yy = 380
            for line in wrap(d, p["hook"], font("xbold", 68), W - 144)[:3]:
                d.text((72, yy), line, font=font("xbold", 68), fill=WHITE)
                yy += 80
            d.text((72, yy + 10), "Korean shopping-search demand, 7-day average", font=font("semi", 36), fill=MUTED)
            d.polygon(pts[:n] + [(pts[n - 1][0], y1), (x0, y1)], fill=(64, 30, 24))
            d.line(pts[:n], fill=ACCENT, width=10, joint="curve")
            cx, cy = pts[n - 1]
            r = 18 + 6 * math.sin(t * 10)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ACCENT)
            if n == len(pts):
                d.text((x1, y0 - 30), p["big"], font=font("black", 110), fill=UP, anchor="rb")
        else:
            d.text((72, 380), p["kicker"], font=font("bold", 40), fill=ACCENT)
            y = 470
            for line in wrap(d, p["hook"], font("xbold", 70), W - 144)[:3]:
                d.text((72, y), line, font=font("xbold", 70), fill=WHITE)
                y += 82
            y += 60
            for i, pt in enumerate(p["points"][:4]):
                a = ease((k * 4.4) - i)
                if a <= 0:
                    break
                yy = y + i * 230 + int((1 - a) * 40)
                d.rounded_rectangle((72, yy, W - 72, yy + 200), 28, fill=INK2)
                d.text((120, yy + 100), f"{i + 1:02d}", font=font("black", 64), fill=ACCENT, anchor="lm")
                lines = wrap(d, pt, font("xbold", 48), W - 360)[:2]
                for j, line in enumerate(lines):
                    d.text((260, yy + 100 + (j - (len(lines) - 1) / 2) * 58), line, font=font("xbold", 48), fill=WHITE, anchor="lm")
        return img

    if t < 8.2 and p["rows"]:                     # 3) top three
        k = (t - 5.6) / 2.6
        d.text((72, 420), "THIS WEEK IN KOREA", font=font("bold", 40), fill=ACCENT)
        y = 520
        for i, (name, value, sub) in enumerate(p["rows"]):
            a = ease(k * 3.2 - i * 0.7)
            if a <= 0:
                break
            yy = y + i * 330 + int((1 - a) * 50)
            d.rounded_rectangle((72, yy, W - 72, yy + 290), 32, fill=INK2)
            d.text((120, yy + 70), f"#{i + 1}", font=font("black", 56), fill=ACCENT)
            nsz = fit(d, name, "xbold", 72, 560, 40)
            d.text((120, yy + 150), name, font=font("xbold", nsz), fill=WHITE)
            d.text((W - 120, yy + 145), value, font=font("black", 80), fill=UP if value.startswith("+") else ACCENT, anchor="rm")
            if sub:
                d.text((W - 120, yy + 225), sub, font=font("semi", 34), fill=MUTED, anchor="rm")
        return img

    # 4) follow card
    k = ease((t - (8.2 if p["rows"] else 5.6)) / 0.4)
    d.text((W // 2, 760 - int((1 - k) * 40)), "Korea's shopping", font=font("black", 96), fill=WHITE, anchor="mm")
    d.text((W // 2, 880 - int((1 - k) * 40)), "data, every day.", font=font("black", 96), fill=WHITE, anchor="mm")
    d.rounded_rectangle((150, 1040, W - 150, 1180), 70, fill=ACCENT)
    d.text((W // 2, 1110), "Follow @kinsiderlab_official", font=font("bold", 46), fill=WHITE, anchor="mm")
    d.text((W // 2, 1280), "Free weekly brief: kinsider-lab.com", font=font("semi", 40), fill=MUTED, anchor="mm")
    return img


def soundtrack(path):
    """Soft generated pad + gentle pulse (no licensed audio). Returns ffmpeg input args."""
    expr = ("0.05*sin(2*PI*220*t)+0.04*sin(2*PI*277.18*t)+0.04*sin(2*PI*329.63*t)"
            "+0.06*sin(2*PI*110*t)*exp(-6*mod(t,0.5))")
    return ["-f", "lavfi", "-t", str(DUR), "-i", f"aevalsrc='{expr}':s=44100"]


def make(story, out_path):
    if not shutil.which("ffmpeg"):
        return False
    p = plan(story)
    p["bg"] = background(Path(out_path).parent / "photo.jpg")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", *soundtrack(out_path),
           "-af", f"afade=t=in:d=0.6,afade=t=out:st={DUR - 1.2}:d=1.2,volume=0.8",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out_path)]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for i in range(int(DUR * FPS)):
            proc.stdin.write(draw_frame(p, i / FPS).tobytes())
        proc.stdin.close()
        return proc.wait(timeout=300) == 0
    except Exception as exc:
        print(f"Reel 2.0 failed: {exc}")
        return False
