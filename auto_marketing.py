import os
import sys
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    print(f"📌 Checking Secrets -> Token: {bool(TELEGRAM_BOT_TOKEN)}, Chat ID: {TELEGRAM_CHAT_ID}")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN.strip()}/sendMessage"
    payload = {
        "chat_id": str(TELEGRAM_CHAT_ID).strip(),
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"📡 Status Code: {response.status_code}")
        print(f"📡 Response Body: {response.text}")
        
        response.raise_for_status()
        print("✅ 텔레그램 메시지 전송 성공!")
        return True
    except Exception as e:
        print(f"❌ 전송 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    report_text = "<b>🔥 [K-Insider Trend Pulse] 테스트 메시지입니다.</b>"
    send_telegram_message(report_text)
