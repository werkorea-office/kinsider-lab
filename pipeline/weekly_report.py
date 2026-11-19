"""Weekly operations report in Korean, opened as a GitHub issue (GitHub emails it to the owner).
Run: python -m pipeline.weekly_report  (needs GITHUB_TOKEN, GITHUB_REPOSITORY)
"""
import csv
import datetime as dt
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KST = dt.timezone(dt.timedelta(hours=9))


def gh(method, path, body=None):
    req = urllib.request.Request(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}{path}", method=method,
                                 data=None if body is None else json.dumps(body).encode())
    req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def delta(rows, key):
    vals = [num(r.get(key)) for r in rows if num(r.get(key)) is not None]
    if not vals:
        return "기록 없음"
    return f"{vals[-1]:,} (지난주 대비 {vals[-1] - vals[0]:+,})" if len(vals) > 1 else f"{vals[-1]:,}"


def main():
    today = dt.datetime.now(KST).date()
    since = today - dt.timedelta(days=7)
    rows = []
    p = ROOT / "data" / "assets.csv"
    if p.exists():
        rows = [r for r in csv.DictReader(p.open(encoding="utf-8")) if r["date"] >= since.isoformat()]
    visits = sum(num(r.get("visitors_today")) or 0 for r in rows)
    sig = json.loads((ROOT / "data" / "signals.json").read_text()) if (ROOT / "data" / "signals.json").exists() else {"signals": []}
    new_calls = [x for x in sig["signals"] if x["called"] >= since.isoformat()]
    runs = gh("GET", f"/actions/runs?created=>={since.isoformat()}&per_page=100").get("workflow_runs", [])
    failed = [r for r in runs if r.get("conclusion") == "failure"]
    li = json.loads((ROOT / "data" / "social" / "linkedin.json").read_text()) if (ROOT / "data" / "social" / "linkedin.json").exists() else {}
    li_age = (today - dt.date.fromisoformat(li["token_first_seen"])).days if li.get("token_first_seen") else None
    lines = [f"## K-INSIDER LAB 주간 운영 보고 ({since} ~ {today})", "",
             "| 항목 | 값 |", "|---|---|",
             f"| 사이트 방문자 (7일 합계) | {visits:,} |",
             f"| 이메일 구독자 (확인됨) | {delta(rows, 'subscribers_confirmed')} |",
             f"| 이메일 구독자 (확인 대기) | {delta(rows, 'subscribers_pending')} |",
             f"| 인스타그램 팔로워 | {delta(rows, 'ig_followers')} |",
             f"| 인스타그램 게시물 | {delta(rows, 'ig_posts')} |",
             f"| 링크드인 게시 누적 | {delta(rows, 'linkedin_posts')} |",
             f"| 이번 주 급상승 신호 | {len(new_calls)}건 {', '.join(x['en'] for x in new_calls[:8])} |",
             f"| 신호 누적 / 적중 | {delta(rows, 'breakout_calls')} / {delta(rows, 'breakout_hits')} |",
             f"| 자동 작업 실행 / 실패 | {len(runs)}회 / {len(failed)}회 |", ""]
    if failed:
        lines += ["### 실패한 작업 (확인 필요)"] + [f"- {r['name']} {r['created_at'][:10]}: {r['html_url']}" for r in failed[:10]] + [""]
    if li_age is not None and li_age >= 45:
        lines += [f"### 링크드인 토큰 {li_age}일 경과 — 60일 전에 재발급하세요 (OPERATIONS.md 5-1)", ""]
    if not failed and (li_age is None or li_age < 45):
        lines.append("이번 주는 대표님이 하실 일이 없습니다.")
    gh("POST", "/issues", {"title": f"주간 운영 보고 {today}", "body": "\n".join(lines), "labels": ["weekly-report"]})
    print("Weekly report issue created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
