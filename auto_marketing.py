import os
import requests

# GitHub Secrets에서 가져오기
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("✅ 텔레그램 메시지 전송 성공!")
        return True
    else:
        print(f"❌ 전송 실패: {response.text}")
        return False

if __name__ == "__main__":
    # 마케팅 리포트 샘플 메세지
    report_text = (
        "<b>🔥 [K-Insider Trend Pulse] 일간 K-Beauty 트렌드 요약</b>\n\n"
        "1️⃣ <b>글로우 스킨/세럼:</b> 아마존 US 상위 순위 급상승\n"
        "2️⃣ <b>선케어/스틱:</b> 유럽 및 북미 지역 검색량 전주 대비 +18% 증가\n"
        "3️⃣ <b>추천 마케팅 문구:</b> <i>\"Discover the secret to natural Korean glass skin with top-trending K-beauty essentials.\"</i>\n\n"
        "👉 <b>자세한 분석 보러가기:</b> <a href='https://kinsider-lab.com'>kinsider-lab.com</a>"
    )
    send_telegram_message(report_text)
