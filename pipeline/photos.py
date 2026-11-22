"""Cover photos from Pixabay (free for commercial use; images are downloaded and stored,
never hotlinked, as Pixabay's API terms ask). One or two requests a day, cached per query.
No key, no network or no match -> None, and the card keeps its data-only cover."""
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "photos.json"
GENERIC = {"beauty": "skincare cosmetics", "brands": "cosmetics skincare products", "brands-top": "cosmetics skincare products",
           "signals": "skincare serum", "food": "korean food", "explained": "skincare", "buysmart": "cosmetics shopping",
           "price": "cosmetics products", "track": "skincare products", "guides": "seoul"}


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "kinsider-lab/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def queries(story):
    q = []
    if story.get("photo"):
        q.append(story["photo"])
    items = story.get("items") or []
    if items and items[0].get("name"):
        q.append(items[0]["name"])
    q.append(GENERIC.get(story.get("segment"), "skincare"))
    return q


def pick(story, out_path, run_date, fetch=_get):
    key = os.environ.get("PIXABAY_KEY", "")
    if not key:
        return None
    try:
        ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {"used": []}
    except Exception:
        ledger = {"used": []}
    used = {u["id"] for u in ledger["used"][-60:]}
    for q in queries(story):
        try:
            params = urllib.parse.urlencode({"key": key, "q": q[:100], "image_type": "photo", "orientation": "vertical",
                                             "safesearch": "true", "order": "popular", "per_page": 30, "min_width": 1080})
            hits = json.loads(fetch(f"https://pixabay.com/api/?{params}"))["hits"]
        except Exception as exc:
            print(f"Pixabay search failed for {q!r}: {exc}")
            continue
        hits = [h for h in hits if h["id"] not in used and h.get("largeImageURL")]
        if len(hits) < 3 and q != queries(story)[-1]:
            continue  # too narrow a match is often off-topic; fall back to the broader query
        if not hits:
            continue
        h = hits[sum(map(ord, run_date)) % min(len(hits), 10)]
        try:
            Path(out_path).write_bytes(fetch(h["largeImageURL"], 60))
        except Exception as exc:
            print(f"Pixabay download failed: {exc}")
            continue
        ledger["used"] = (ledger["used"] + [{"id": h["id"], "date": run_date, "q": q, "user": h.get("user", "")}])[-200:]
        LEDGER.write_text(json.dumps(ledger, indent=1), encoding="utf-8")
        return {"path": str(out_path), "user": h.get("user", ""), "page": h.get("pageURL", "")}
    return None
