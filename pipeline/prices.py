"""Sunday 'Korea Price Check': what Korean shoppers pay right now.

For the week's three fastest-rising K-beauty brands, takes the most relevant
Naver Shopping listing and its lowest price in Korea (Naver Search API, developer
keys). Output: data/prices.json, read by cards.py on Sundays. No keys, a failed
call or too few results -> no file for today, and the Sunday card falls back to
an evergreen Buy Smart topic. Prices are reference points, dated, never 'cheapest'.
"""
import datetime as dt
import html
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

from . import build

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "prices.json"
KST = dt.timezone(dt.timedelta(hours=9))
FALLBACK_RATE = 1400.0  # KRW per USD, used only if the rate lookup fails (labelled on the card)


def get_json(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def usd_rate(fetch=get_json):
    try:
        rate = float(fetch("https://open.er-api.com/v6/latest/USD")["rates"]["KRW"])
        return rate, "live"
    except Exception:
        return FALLBACK_RATE, "approx."


def renderable(ch):
    """The card font carries the KS X 1001 Hangul set (= what EUC-KR can encode); drop anything else."""
    try:
        ch.encode("euc-kr")
        return True
    except UnicodeEncodeError:
        return False


def clean(title):
    t = html.unescape(re.sub(r"<[^>]+>", "", title))
    return re.sub(r"\s+", " ", "".join(c for c in t if renderable(c))).strip()


def best_listing(kw, cid, secret, fetch=get_json):
    q = urllib.parse.urlencode({"query": kw, "display": 20, "sort": "sim"})
    data = fetch(f"https://openapi.naver.com/v1/search/shop.json?{q}",
                 {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret})
    for it in data.get("items", []):
        price = int(it.get("lprice") or 0)
        title = clean(it.get("title", ""))
        # Skip bundles/sets so the price is for one product.
        if kw.replace(" ", "") not in title.replace(" ", ""):
            continue  # must be the brand's own listing
        if price >= 3000 and not re.search(r"세트|기획|\d+\s*개|\d+\s*팩|1\+1|증정", title):
            return {"title": title[:60], "price_krw": price, "mall": m if (m := it.get("mallName") or "").isascii() and m else "Naver Shopping",
                    "category": " / ".join(x for x in (it.get("category2"), it.get("category3")) if x)}
    return None


def main(now=None, fetch=get_json):
    now = now or dt.datetime.now(KST)
    if now.weekday() != 6:
        return 0
    cid, secret = os.environ.get("NAVER_CLIENT_ID", ""), os.environ.get("NAVER_CLIENT_SECRET", "")
    latest = ROOT / "data" / "latest.json"
    if not (cid and secret and latest.exists()):
        print("Price check skipped: no Naver developer keys or no data.")
        return 0
    snap = json.loads(latest.read_text(encoding="utf-8"))
    seg = next((s for s in snap.get("segments", []) if s["id"] == "brands"), None)
    if not seg:
        return 0
    rising, _, biggest = build.ranked(seg)
    picks, seen = [], set()
    for it in rising + biggest:
        if it.get("is_anchor") or it["kw"] in seen:
            continue
        seen.add(it["kw"])
        try:
            listing = best_listing(it["kw"], cid, secret, fetch)
        except Exception as exc:
            print(f"Price lookup failed ({exc}); no price check today.")
            return 0
        if listing:
            picks.append({"brand": it["en"], "kw": it["kw"], "momentum": it["momentum"], **listing})
        if len(picks) == 3:
            break
    if len(picks) < 3:
        print("Too few clean listings; no price check today.")
        return 0
    rate, rate_kind = usd_rate(fetch)
    for p in picks:
        p["price_usd"] = round(p["price_krw"] / rate, 2)
    OUT.write_text(json.dumps({"date": snap["run_date"], "rate": round(rate, 1), "rate_kind": rate_kind,
                               "items": picks}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Price check written for {snap['run_date']}: {', '.join(p['brand'] for p in picks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
