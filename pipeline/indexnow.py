"""Tells Bing, Naver, Yandex and other IndexNow engines which pages changed today.
Run after the daily build: python -m pipeline.indexnow"""
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY = "413050ca8f87b56adea2c7aa7dd9938d"
HOST = "www.kinsider-lab.com"


def main():
    urls = re.findall(r"<loc>([^<]+)</loc>", (ROOT / "sitemap.xml").read_text(encoding="utf-8"))[:10000]
    body = json.dumps({"host": HOST, "key": KEY, "keyLocation": f"https://{HOST}/{KEY}.txt", "urlList": urls}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow: {len(urls)} URLs submitted (HTTP {r.status})")
    except Exception as err:  # search-engine pings must never fail the daily run
        print(f"IndexNow unavailable: {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
