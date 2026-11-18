"""Daily collector. Run: python -m pipeline.collect

Rules this script never breaks:
  * Nothing is invented. If a source fails, the last verified data is kept and
    clearly marked with its real date; no placeholder numbers are written.
  * Every published number can be traced to a stored daily snapshot.
"""
import csv
import datetime as dt
import json
import os
import sys
from pathlib import Path

from . import datalab, signals
from .metrics import date_range, keyword_metrics, normalize_batch

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "watchlist.json"
DATA = ROOT / "data"
DAILY = DATA / "daily"
LATEST = DATA / "latest.json"
HISTORY = DATA / "history.csv"
KST = dt.timezone(dt.timedelta(hours=9))
MIN_COVERAGE = 0.8  # share of watchlist keywords that must succeed to publish a segment


def load_config():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    for key in ("lookback_days", "recent_days", "baseline_days", "min_level", "segments"):
        if key not in cfg:
            raise SystemExit(f"watchlist.json missing '{key}'")
    if cfg["recent_days"] + cfg["baseline_days"] > cfg["lookback_days"]:
        raise SystemExit("lookback_days must cover recent_days + baseline_days")
    for seg in cfg["segments"]:
        kws = [k["kw"] for k in seg["keywords"]]
        if len(kws) != len(set(kws)):
            raise SystemExit(f"Duplicate keyword in segment {seg['id']}")
        if seg["anchor"]["kw"] in kws:
            raise SystemExit(f"Anchor repeated as keyword in segment {seg['id']}")
        for k in seg["keywords"] + [seg["anchor"]]:
            if not k.get("kw") or not k.get("en"):
                raise SystemExit(f"Keyword needs 'kw' and 'en' in segment {seg['id']}")
    return cfg


def collect_segment(seg, cfg, creds, start, end, fetch=datalab.fetch_keywords):
    url, headers = creds
    dates = date_range(start, end)
    anchor = seg["anchor"]["kw"]
    others = [k["kw"] for k in seg["keywords"]]
    indexed, errors = {}, []
    for i in range(0, len(others), 4):
        group = others[i:i + 4]
        try:
            raw = fetch(url, headers, seg["category_code"], [anchor] + group, start, end)
            norm = normalize_batch(raw, anchor, dates)
        except Exception as e:  # one bad batch must not sink the others
            errors.append(f"{', '.join(group)}: {e}")
            continue
        indexed.setdefault(anchor, norm[anchor])
        for kw in group:
            indexed[kw] = norm[kw]
    succeeded = sum(1 for kw in others if kw in indexed)
    if not others or succeeded / len(others) < MIN_COVERAGE:
        raise RuntimeError(f"coverage {succeeded}/{len(others)} below threshold; " + " | ".join(errors))

    labels = {k["kw"]: k for k in seg["keywords"] + [seg["anchor"]]}
    items = []
    for kw, series in indexed.items():
        m = keyword_metrics(series, cfg["recent_days"], cfg["baseline_days"], cfg["min_level"])
        meta = labels[kw]
        items.append({"kw": kw, "en": meta["en"], "type": meta.get("type", ""),
                      "is_anchor": kw == anchor, **m})
    return {
        "id": seg["id"], "title": seg["title"],
        "category_code": seg["category_code"], "category_name_kr": seg["category_name_kr"],
        "anchor": {"kw": anchor, "en": seg["anchor"]["en"]},
        "data_start": start, "data_end": end, "dates": dates,
        "items": items, "warnings": errors, "status": "ok",
    }


def load_previous():
    if LATEST.exists():
        try:
            return json.loads(LATEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def upsert_history(run_date, segments):
    rows = []
    if HISTORY.exists():
        with HISTORY.open(encoding="utf-8", newline="") as f:
            rows = [r for r in csv.DictReader(f) if r["run_date"] != run_date]
    for seg in segments:
        if seg.get("status") != "ok" or seg.get("fresh") is False:
            continue
        for it in seg["items"]:
            rows.append({"run_date": run_date, "data_end": seg["data_end"], "segment": seg["id"],
                         "keyword_kr": it["kw"], "keyword_en": it["en"], "level": it["level"],
                         "momentum": "" if it["momentum"] is None else it["momentum"]})
    rows.sort(key=lambda r: (r["run_date"], r["segment"], r["keyword_kr"]))
    with HISTORY.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["run_date", "data_end", "segment", "keyword_kr",
                                          "keyword_en", "level", "momentum"])
        w.writeheader()
        w.writerows(rows)


def main(now=None, fetch=datalab.fetch_keywords, creds=None):
    cfg = load_config()
    now = now or dt.datetime.now(KST)
    run_date = now.date().isoformat()
    end = (now.date() - dt.timedelta(days=1)).isoformat()
    start = (now.date() - dt.timedelta(days=cfg["lookback_days"])).isoformat()
    creds = creds or datalab.credentials_from_env()
    previous = load_previous() or {}
    prev_segments = {s["id"]: s for s in previous.get("segments", [])}

    if creds is None:
        print("No Naver DataLab credentials configured; site will show the setup notice.")
        if not previous:
            snapshot = {"run_date": run_date, "status": "not_configured", "segments": []}
            DATA.mkdir(exist_ok=True)
            LATEST.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0

    segments, failures = [], []
    for seg in cfg["segments"]:
        try:
            result = collect_segment(seg, cfg, creds, start, end, fetch=fetch)
            result["fresh"] = True
            segments.append(result)
        except Exception as e:
            failures.append(f"{seg['id']}: {e}")
            old = prev_segments.get(seg["id"])
            if old and old.get("status") == "ok":
                old = dict(old)
                old["fresh"] = False  # shown with its real (older) date, never relabelled as today
                segments.append(old)

    if not any(s.get("fresh") for s in segments):
        print("All segments failed; keeping previous published data untouched.")
        for f in failures:
            print("  -", f)
        return 1  # fail the workflow so the owner is notified by GitHub

    snapshot = {"run_date": run_date, "status": "ok", "segments": segments, "failures": failures}
    DAILY.mkdir(parents=True, exist_ok=True)
    text = json.dumps(snapshot, ensure_ascii=False, indent=1)
    (DAILY / f"{run_date}.json").write_text(text, encoding="utf-8")
    LATEST.write_text(text, encoding="utf-8")
    upsert_history(run_date, segments)
    if cfg.get("breakout"):
        ledger = signals.update(snapshot, cfg["breakout"])
        signals.save(ledger)
        print(f"Breakout calls today: {len(signals.new_on(ledger, run_date))}")
    print(f"Published snapshot {run_date}; failures: {failures or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
