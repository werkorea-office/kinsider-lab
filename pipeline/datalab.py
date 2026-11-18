"""Naver DataLab Shopping Insight client.

Supports both access routes Naver offers:
  * NAVER API HUB (NCP)  -> env NAVER_HUB_KEY_ID + NAVER_HUB_KEY
  * Naver Developers     -> env NAVER_CLIENT_ID + NAVER_CLIENT_SECRET
Only the standard library is used so the GitHub Actions run has nothing to install.
"""
import json
import os
import time
import urllib.error
import urllib.request

HUB_URL = "https://naverapihub.apigw.ntruss.com/shopping/v1/category/keywords"
DEV_URL = "https://openapi.naver.com/v1/datalab/shopping/category/keywords"


class DataLabError(RuntimeError):
    pass


def credentials_from_env():
    """Return (url, headers) or None when no credentials are configured."""
    hub_id, hub_key = os.environ.get("NAVER_HUB_KEY_ID"), os.environ.get("NAVER_HUB_KEY")
    if hub_id and hub_key:
        return HUB_URL, {
            "X-NCP-APIGW-API-KEY-ID": hub_id.strip(),
            "X-NCP-APIGW-API-KEY": hub_key.strip(),
        }
    dev_id, dev_secret = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    if dev_id and dev_secret:
        return DEV_URL, {
            "X-Naver-Client-Id": dev_id.strip(),
            "X-Naver-Client-Secret": dev_secret.strip(),
        }
    return None


def fetch_keywords(url, headers, category_code, keywords, start, end, attempts=3):
    """keywords: list of Korean query strings (max 5). Returns {kw: {date: ratio}}."""
    if not 1 <= len(keywords) <= 5:
        raise ValueError("DataLab accepts 1-5 keywords per request")
    body = {
        "startDate": start,
        "endDate": end,
        "timeUnit": "date",
        "category": category_code,
        "keyword": [{"name": kw, "param": [kw]} for kw in keywords],
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    last_err = None
    for i in range(attempts):
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return parse_response(payload, keywords)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            last_err = DataLabError(f"HTTP {e.code}: {detail}")
            if e.code in (400, 401, 403):  # configuration problems: retrying won't help
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = DataLabError(str(e))
        time.sleep(2 * (i + 1))
    raise last_err


def parse_response(payload, keywords):
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != len(keywords):
        raise DataLabError("Unexpected response shape")
    out = {}
    for item in results:
        name = item.get("title")
        if name not in keywords:
            raise DataLabError(f"Unexpected keyword in response: {name!r}")
        series = {}
        for point in item.get("data", []):
            series[point["period"]] = float(point["ratio"])
        out[name] = series
    return out
