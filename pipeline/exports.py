"""Korea Customs export statistics (관세청 품목별 국가별 수출입실적).

Run: python -m pipeline.exports            (refreshes at most once a week)
     python -m pipeline.exports --force

For each tracked HS code and destination country it stores monthly export
values (USD) for the last 24 months in data/exports.json, so the site can show
the latest month and the change versus the same month a year earlier.
Customs revises the previous month around the 15th, so figures are re-pulled
weekly and always shown with their month.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "exports.json"
URL = "http://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
KST = dt.timezone(dt.timedelta(hours=9))

PRODUCTS = [
    {"hs": "3304", "en": "Skin care & make-up", "segment": "beauty"},
    {"hs": "3305", "en": "Hair care", "segment": "beauty"},
    {"hs": "1902", "en": "Noodles incl. instant ramyeon", "segment": "food"},
    {"hs": "2103", "en": "Sauces & condiments (incl. gochujang)", "segment": "food"},
]
COUNTRIES = [
    ("US", "United States"), ("CN", "China"), ("JP", "Japan"), ("HK", "Hong Kong"), ("VN", "Vietnam"),
    ("TW", "Taiwan"), ("TH", "Thailand"), ("AE", "United Arab Emirates"), ("GB", "United Kingdom"),
    ("RU", "Russia"), ("PL", "Poland"), ("AU", "Australia"),
]


def service_key():
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if "%" in key:  # the portal shows an already URL-encoded variant; normalise to the decoded key
        key = urllib.parse.unquote(key)
    return key


def months_back(end, n):
    y, m = end.year, end.month
    out = []
    for _ in range(n):
        out.append(f"{y:04d}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def fetch(key, hs, cnty, start, end, attempts=3):
    q = urllib.parse.urlencode({"serviceKey": key, "strtYymm": start, "endYymm": end, "hsSgn": hs, "cntyCd": cnty})
    last = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(URL + "?" + q, timeout=40) as r:
                return parse_full(r.read())
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"{hs}/{cnty}: {last}")


def parse(raw):
    """Returns {YYYYMM: export_usd}. Raises ValueError on API errors."""
    return {m: usd for m, (usd, _) in parse_full(raw).items()}


def parse_full(raw):
    """Returns {YYYYMM: (export_usd, export_kg)}. Raises ValueError on API errors."""
    root = ET.fromstring(raw)
    code = root.findtext(".//resultCode")
    if code not in (None, "00", "0", "000"):
        raise ValueError(f"API error {code}: {root.findtext('.//resultMsg')}")
    out = {}
    for item in root.iter("item"):
        fields = {child.tag: (child.text or "").strip() for child in item}
        period = fields.get("year") or fields.get("yymm") or fields.get("period") or ""
        digits = "".join(ch for ch in period if ch.isdigit())
        if len(digits) != 6:  # skip totals ("총계") and malformed rows
            continue
        val = fields.get("expDlr") or fields.get("expUsdAmt") or "0"
        wgt = fields.get("expWgt") or fields.get("expWght") or "0"
        try:
            usd, kg = float(val.replace(",", "")), float(wgt.replace(",", "") or 0)
        except ValueError:
            continue
        prev = out.get(digits, (0.0, 0.0))
        out[digits] = (prev[0] + usd, prev[1] + kg)
    return out


def main(force=False):
    key = service_key()
    if not key:
        print("DATA_GO_KR_KEY not set; skipping export statistics.")
        return 0
    if OUT.exists() and not force:
        prev = json.loads(OUT.read_text(encoding="utf-8"))
        age = (dt.datetime.now(KST).date() - dt.date.fromisoformat(prev["fetched"])).days
        if age < 7:
            print(f"Export statistics fetched {age} day(s) ago; next refresh after 7 days.")
            return 0
    today = dt.datetime.now(KST).date()
    last_month = (today.replace(day=1) - dt.timedelta(days=1))
    months = months_back(last_month, 24)
    data, weights, errors = {}, {}, []
    for p in PRODUCTS:
        for code, name in COUNTRIES:
            series = {}
            try:
                series.update(fetch(key, p["hs"], code, months[0], months[11]))
                series.update(fetch(key, p["hs"], code, months[12], months[23]))
            except Exception as e:
                errors.append(str(e))
                continue
            data.setdefault(p["hs"], {})[code] = {m: round(series.get(m, (0.0, 0.0))[0]) for m in months}
            weights.setdefault(p["hs"], {})[code] = {m: round(series.get(m, (0.0, 0.0))[1]) for m in months}
    if not data:
        print("All export requests failed; keeping previous file.")
        for e in errors[:5]:
            print("  -", e)
        return 1
    # latest month with real figures (customs publishes with a lag of a few weeks)
    latest = None
    for m in reversed(months):
        if sum(v.get(m, 0) for c in data.values() for v in c.values()) > 0:
            latest = m
            break
    snapshot = {"fetched": today.isoformat(), "latest_month": latest, "months": months,
                "products": PRODUCTS, "countries": [{"code": c, "name": n} for c, n in COUNTRIES],
                "values": data, "weights_kg": weights, "errors": errors,
                "source": "Korea Customs Service, export statistics by item and country (data.go.kr)"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, indent=1), encoding="utf-8")
    print(f"Export statistics saved; latest month {latest}; errors {len(errors)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(force="--force" in sys.argv))
