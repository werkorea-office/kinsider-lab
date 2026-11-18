"""Publishes today's card to LinkedIn (member profile via Share on LinkedIn).

Run: python -m pipeline.social_linkedin publish

Same rules as Instagram: one post per day (ledger in data/social/linkedin.json),
no card -> no post, and the image is uploaded through LinkedIn's Images API.
LinkedIn member tokens last 60 days and cannot be refreshed for this app tier,
so the ledger records when the token started working and the workflow fails
loudly (email to the owner) 7 days before it expires.
"""
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "social" / "linkedin.json"
KST = dt.timezone(dt.timedelta(hours=9))
TOKEN_DAYS = 60


def req(method, url, token, body=None, raw=None, content_type="application/json", extra=None):
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        r.add_header("Content-Type", content_type)
    for k, v in (extra or {}).items():
        r.add_header(k, v)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            payload = resp.read()
            return resp.status, dict(resp.headers), (json.loads(payload) if payload.strip().startswith(b"{") else {})
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {url}: {e.read().decode('utf-8', 'replace')[:400]}")


_VERSION = None


def candidate_versions():
    """Newest first: last month back to ~11 months ago (LinkedIn keeps about a year active)."""
    if os.environ.get("LINKEDIN_VERSION"):
        return [os.environ["LINKEDIN_VERSION"]]
    d = dt.date.today().replace(day=1)
    out = []
    for _ in range(12):
        d = (d - dt.timedelta(days=1)).replace(day=1)
        out.append(d.strftime("%Y%m"))
    return out


def rest_call(method, url, token, body=None):
    """REST call that finds an active LinkedIn-Version automatically and remembers it."""
    global _VERSION
    versions = [_VERSION] if _VERSION else candidate_versions()
    last = None
    for v in versions:
        try:
            result = req(method, url, token, body, extra={"LinkedIn-Version": v,
                                                          "X-Restli-Protocol-Version": "2.0.0"})
            _VERSION = v
            return result
        except RuntimeError as e:
            last = e
            if "NONEXISTENT_VERSION" not in str(e) and "not active" not in str(e):
                raise
    raise last


def load_ledger():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"posts": [], "token_first_seen": None}


def save_ledger(ledger):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=1), encoding="utf-8")


def publish():
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "").strip()
    if not token:
        print("LINKEDIN_ACCESS_TOKEN not set; skipping LinkedIn.")
        return 0
    ledger = load_ledger()
    fingerprint = token[-12:]
    if ledger.get("token_fingerprint") != fingerprint:
        ledger["token_fingerprint"] = fingerprint
        ledger["token_first_seen"] = dt.datetime.now(KST).date().isoformat()
    today = dt.datetime.now(KST).date()
    age = (today - dt.date.fromisoformat(ledger["token_first_seen"])).days
    png = ROOT / "cards" / f"{today.isoformat()}.png"
    txt = ROOT / "cards" / f"{today.isoformat()}.txt"
    status = 0
    if not png.exists():
        print(f"No card for {today}; nothing to post.")
    elif any(p["date"] == today.isoformat() for p in ledger["posts"]):
        print(f"Already posted {today}; skipping.")
    else:
        _, _, me = req("GET", "https://api.linkedin.com/v2/userinfo", token)
        author = f"urn:li:person:{me['sub']}"
        _, _, init = rest_call("POST", "https://api.linkedin.com/rest/images?action=initializeUpload", token,
                               {"initializeUploadRequest": {"owner": author}})
        upload_url = init["value"]["uploadUrl"]
        image_urn = init["value"]["image"]
        req("PUT", upload_url, token, raw=png.read_bytes(), content_type="image/png")
        caption = txt.read_text(encoding="utf-8").replace("link in bio (kinsider-lab.com)",
                                                          "https://www.kinsider-lab.com")
        post = {
            "author": author,
            "commentary": caption,
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                             "thirdPartyDistributionChannels": []},
            "content": {"media": {"id": image_urn, "altText": "Korea shopping-search momentum chart"}},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        _, headers, _ = rest_call("POST", "https://api.linkedin.com/rest/posts", token, post)
        post_id = headers.get("x-restli-id") or headers.get("X-RestLi-Id")
        ledger["posts"].append({"date": today.isoformat(), "post": post_id})
        print(f"Posted {today} to LinkedIn: {post_id}")
    save_ledger(ledger)
    if age >= TOKEN_DAYS - 7:
        print(f"LinkedIn token is {age} days old and expires around day {TOKEN_DAYS}. "
              "Generate a new one in the LinkedIn developer token tool and update LINKEDIN_ACCESS_TOKEN.")
        status = 1  # fail the job so GitHub emails the owner in time
    return status


if __name__ == "__main__":
    sys.exit(publish())
