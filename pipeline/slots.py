"""Posting slots and the relay's 'what is next' decision.

eu   = 17:00 KST (08:00 UTC): Europe 9 AM, South-East Asia afternoon. Instagram only, guide post.
main = 23:00 KST (14:00 UTC): US East 9 AM. Instagram + LinkedIn, data post.
A slot is 'done' when its ledger key is recorded; a slot more than 3 h past is given up.
"""
import datetime as dt
import json
import sys

KST = dt.timezone(dt.timedelta(hours=9))
SLOTS = [("eu", 8), ("main", 14)]          # UTC hour
GRACE = 3 * 3600


def key(slot, when_utc):
    d = when_utc.astimezone(KST).date().isoformat()
    return d if slot == "main" else f"{d}-eu"


def channels(slot):
    return ["instagram", "linkedin"] if slot == "main" else ["instagram"]


def done(slot, k, ledgers):
    return all(any(p.get("date") == k for p in ledgers.get(c, {}).get("posts", [])) for c in channels(slot))


def next_slot(now, ledgers):
    day = now.date()
    for add in range(0, 3):
        for slot, hour in SLOTS:
            t = dt.datetime.combine(day + dt.timedelta(days=add), dt.time(hour), dt.timezone.utc)
            if (now - t).total_seconds() > GRACE:
                continue
            k = key(slot, t)
            if not done(slot, k, ledgers):
                return {"slot": slot, "key": k, "wait": max(0, int((t - now).total_seconds()))}
    return None


if __name__ == "__main__":
    # usage: python -m pipeline.slots next instagram.json linkedin.json
    led = {}
    for name, path in (("instagram", sys.argv[2]), ("linkedin", sys.argv[3])):
        try:
            led[name] = json.load(open(path, encoding="utf-8"))
        except Exception:
            led[name] = {"posts": []}
    print(json.dumps(next_slot(dt.datetime.now(dt.timezone.utc), led)))
