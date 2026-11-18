"""Publishes today's carousel to LinkedIn (PDF document, falling back to multi-image) (member profile via Share on LinkedIn).

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


def upload(token, author, kind, data, content_type):
    _, _, init = rest_call("POST", f"https://api.linkedin.com/rest/{kind}s?action=initializeUpload", token,
                           {"initializeUploadRequest": {"owner": author}})
    req("PUT", init["value"]["uploadUrl"], token, raw=data, content_type=content_type)
    return init["value"][kind]


def document_content(token, author, folder, meta, deck_pdf):
    pdf = deck_pdf(folder, meta, folder.parent / f".{meta['date']}-deck.pdf")
    try:
        urn = upload(token, author, "document", pdf.read_bytes(), "application/pdf")
    finally:
        pdf.unlink(missing_ok=True)
    title = f"K-INSIDER LAB No. {meta['issue']:03d}: {meta['title']}"[:200]
    return {"media": {"id": urn, "title": title}}


def multi_image_content(token, author, folder, meta):
    images = [{"id": upload(token, author, "image", (folder / n).read_bytes(), "image/jpeg"),
               "altText": f"K-INSIDER LAB slide {i}"} for i, n in enumerate(meta["slides"], 1)]
    return {"multiImage": {"images": images}}


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
    from .cards import deck_pdf, todays_carousel
    found = todays_carousel(today.isoformat())
    status = 0
    if not found:
        print(f"No carousel for {today}; nothing to post.")
    elif any(p["date"] == today.isoformat() for p in ledger["posts"]):
        print(f"Already posted {today}; skipping.")
    else:
        folder, meta, caption = found
        _, _, me = req("GET", "https://api.linkedin.com/v2/userinfo", token)
        author = f"urn:li:person:{me['sub']}"
        caption = caption.replace("link in bio (kinsider-lab.com)", "https://www.kinsider-lab.com")
        caption = caption.replace("Swipe for the", "Swipe through the")
        try:
            content, kind = document_content(token, author, folder, meta, deck_pdf), "document"
        except RuntimeError as e:  # documents need an extra permission on some app tiers
            print(f"Document upload unavailable ({str(e)[:160]}); posting slides as images.")
            content, kind = multi_image_content(token, author, folder, meta), "images"
        post = {
            "author": author,
            "commentary": caption,
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                             "thirdPartyDistributionChannels": []},
            "content": content,
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        _, headers, _ = rest_call("POST", "https://api.linkedin.com/rest/posts", token, post)
        post_id = headers.get("x-restli-id") or headers.get("X-RestLi-Id")
        ledger["posts"].append({"date": today.isoformat(), "post": post_id, "format": kind,
                                "story": meta.get("story")})
        print(f"Posted {today} to LinkedIn as {kind}: {post_id}")
    save_ledger(ledger)
    if age >= TOKEN_DAYS - 7:
        print(f"LinkedIn token is {age} days old and expires around day {TOKEN_DAYS}. "
              "Generate a new one in the LinkedIn developer token tool and update LINKEDIN_ACCESS_TOKEN.")
        status = 1  # fail the job so GitHub emails the owner in time
    return status


def dryrun():
    """Uploads today's deck as a LinkedIn document without creating a post."""
    from .cards import deck_pdf, todays_carousel
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "").strip()
    found = todays_carousel(dt.datetime.now(KST).date().isoformat())
    if not token or not found:
        print("Dry run needs LINKEDIN_ACCESS_TOKEN and today's carousel.")
        return 1
    folder, meta, _ = found
    _, _, me = req("GET", "https://api.linkedin.com/v2/userinfo", token)
    author = f"urn:li:person:{me['sub']}"
    try:
        content = document_content(token, author, folder, meta, deck_pdf)
        print(f"LinkedIn dry run OK: document upload accepted ({content['media']['id']}); will post as PDF carousel.")
    except RuntimeError as e:
        print(f"Document upload refused ({str(e)[:200]}); checking image fallback.")
        upload(token, author, "image", (folder / meta["slides"][0]).read_bytes(), "image/jpeg")
        print("LinkedIn dry run OK: will post as multi-image carousel.")
    return 0


if __name__ == "__main__":
    sys.exit({"publish": publish, "dryrun": dryrun}[sys.argv[1] if len(sys.argv) > 1 else "publish"]())
