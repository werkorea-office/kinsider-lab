"""Publishes today's card to Instagram (Instagram API with Instagram Login).

Run: python -m pipeline.social_instagram publish   # post today's card once
     python -m pipeline.social_instagram refresh   # extend the 60-day token

Rules: never posts twice for the same day (data/social/instagram.json is the
ledger), never posts if today's card does not exist (no stale numbers), and
waits until the card is actually reachable on the public site before asking
Instagram to fetch it.
"""
import base64
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "social" / "instagram.json"
SITE = "https://www.kinsider-lab.com"
API = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v23.0")
KST = dt.timezone(dt.timedelta(hours=9))


def call(method, url, params, timeout=60):
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:400]}")


def wait_until_public(url, minutes=15):
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=20) as r:
                if r.status == 200 and r.headers.get("Content-Type", "").startswith("image/"):
                    return True
        except Exception:
            pass
        time.sleep(30)
    return False


def load_ledger():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"posts": []}


def publish():
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not token:
        print("IG_ACCESS_TOKEN not set; skipping Instagram.")
        return 0
    today = dt.datetime.now(KST).date().isoformat()
    png = ROOT / "cards" / f"{today}.png"
    txt = ROOT / "cards" / f"{today}.txt"
    if not png.exists():
        print(f"No card for {today}; nothing to post.")
        return 0
    ledger = load_ledger()
    if any(p["date"] == today for p in ledger["posts"]):
        print(f"Already posted {today}; skipping.")
        return 0
    image_url = f"{SITE}/cards/{today}.png"
    if not wait_until_public(image_url):
        print(f"Card not reachable at {image_url}; not posting.")
        return 1
    caption = txt.read_text(encoding="utf-8")
    container = call("POST", f"{API}/me/media", {"image_url": image_url, "caption": caption,
                                                   "access_token": token})
    cid = container["id"]
    for _ in range(20):  # container must finish processing before publish
        status = call("GET", f"{API}/{cid}", {"fields": "status_code", "access_token": token})
        if status.get("status_code") == "FINISHED":
            break
        if status.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram could not process the image: {status}")
        time.sleep(6)
    result = call("POST", f"{API}/me/media_publish", {"creation_id": cid, "access_token": token})
    ledger["posts"].append({"date": today, "media_id": result.get("id"), "image": image_url})
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=1), encoding="utf-8")
    print(f"Posted {today} to Instagram: {result.get('id')}")
    return 0


def save_secret(name, value):
    """Store a refreshed token back into GitHub Actions secrets (needs GH_SECRETS_TOKEN)."""
    gh_token = os.environ.get("GH_SECRETS_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not gh_token or not repo:
        return False
    from nacl import encoding, public  # installed in the workflow

    def gh(method, path, body=None):
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}{path}", method=method,
                                     data=None if body is None else json.dumps(body).encode())
        req.add_header("Authorization", f"Bearer {gh_token}")
        req.add_header("Accept", "application/vnd.github+json")
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}

    key = gh("GET", "/actions/secrets/public-key")
    box = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder()))
    sealed = base64.b64encode(box.encrypt(value.encode())).decode()
    gh("PUT", f"/actions/secrets/{name}", {"encrypted_value": sealed, "key_id": key["key_id"]})
    return True


def refresh():
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not token:
        print("IG_ACCESS_TOKEN not set; nothing to refresh.")
        return 0
    res = call("GET", "https://graph.instagram.com/refresh_access_token",
               {"grant_type": "ig_refresh_token", "access_token": token})
    new = res["access_token"]
    days = int(res.get("expires_in", 0)) // 86400
    if new == token:
        print(f"Token extended in place; valid ~{days} days.")
        return 0
    if save_secret("IG_ACCESS_TOKEN", new):
        print(f"Token refreshed and saved; valid ~{days} days.")
        return 0
    print("Token refreshed but could not be saved (GH_SECRETS_TOKEN missing). Old token keeps working "
          "until it expires; add GH_SECRETS_TOKEN to automate this.")
    return 1


def check():
    """Verifies GH_SECRETS_TOKEN can reach this repo's secrets API without changing anything."""
    gh_token = os.environ.get("GH_SECRETS_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not gh_token:
        print("GH_SECRETS_TOKEN not set.")
        return 1
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/secrets/public-key")
    req.add_header("Authorization", f"Bearer {gh_token}")
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            key = json.loads(r.read())
        print(f"GH_SECRETS_TOKEN OK: can manage secrets of {repo} (key {key['key_id']}).")
        return 0
    except urllib.error.HTTPError as e:
        print(f"GH_SECRETS_TOKEN check failed: HTTP {e.code}")
        return 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "publish"
    sys.exit({"publish": publish, "refresh": refresh, "check": check}[cmd]())
