"""Breakout signals and their public track record.

A term is called a Breakout when, on fresh data:
  * its demand index (last 7 days) is at least `min_level`,
  * the last 7 days are at least `week_rise` above the 3 weeks before the prior week,
  * the prior week was already at least `prior_week_rise` above that same base,
  * and the last 7 days are not below the prior week (still rising or holding).
So a single noisy day can't trigger it: the rise must last two weeks.

Every call is written once into data/signals.json and never edited or removed.
After 7, 14 and 28 days the demand index is compared with the level at the call,
and the result is recorded whether the call worked or not.
"""
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "signals.json"


def load():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"rule": None, "signals": []}


def is_breakout(item, rule):
    if item.get("is_anchor"):
        return False
    lvl, prev, base = item["level"], item.get("prev_week"), item.get("early_baseline")
    if prev is None or base is None or base <= 0:
        return False
    return (lvl >= rule["min_level"]
            and lvl >= base * (1 + rule["week_rise"])
            and prev >= base * (1 + rule["prior_week_rise"])
            and lvl >= prev)


def update(snapshot, rule, ledger=None):
    """Adds new calls from a fresh snapshot and records checkpoint results. Returns the ledger."""
    ledger = ledger or load()
    ledger["rule"] = rule
    run = dt.date.fromisoformat(snapshot["run_date"])
    current = {}
    for seg in snapshot.get("segments", []):
        if seg.get("status") != "ok" or seg.get("fresh") is False:
            continue
        for it in seg["items"]:
            current[(seg["id"], it["kw"])] = (seg, it)

    # checkpoints for existing calls
    for sig in ledger["signals"]:
        key = (sig["segment"], sig["kw"])
        if key not in current:
            continue
        _, it = current[key]
        age = (run - dt.date.fromisoformat(sig["called"])).days
        sig["latest"] = {"date": snapshot["run_date"], "level": it["level"]}
        for cp in rule["checkpoints"]:
            name = f"d{cp}"
            if age >= cp and name not in sig["checks"]:
                sig["checks"][name] = {
                    "date": snapshot["run_date"], "level": it["level"],
                    "change": round(it["level"] / sig["level_at_call"] - 1, 4),
                }

    # new calls
    last_call = {}
    for sig in ledger["signals"]:
        key = (sig["segment"], sig["kw"])
        last_call[key] = max(last_call.get(key, ""), sig["called"])
    for key, (seg, it) in current.items():
        if not is_breakout(it, rule):
            continue
        prev = last_call.get(key)
        if prev and (run - dt.date.fromisoformat(prev)).days < rule["cooldown_days"]:
            continue
        ledger["signals"].append({
            "id": f"{seg['id']}:{it['kw']}:{snapshot['run_date']}",
            "segment": seg["id"], "segment_title": seg["title"],
            "kw": it["kw"], "en": it["en"], "type": it.get("type", ""),
            "called": snapshot["run_date"], "data_end": seg["data_end"],
            "level_at_call": it["level"], "momentum_at_call": it["momentum"],
            "prev_week": it["prev_week"], "early_baseline": it["early_baseline"],
            "checks": {}, "latest": {"date": snapshot["run_date"], "level": it["level"]},
        })
    return ledger


def save(ledger):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")


def new_on(ledger, date):
    return [s for s in ledger["signals"] if s["called"] == date]


def with_results(ledger):
    return [s for s in ledger["signals"] if s["checks"]]
