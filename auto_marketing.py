import json
import os
import requests

def generate_marketing_post():
    # 1. 가공된 최신 트렌드 데이터 읽기
    try:
        with open("data/processed_latest.json", "r", encoding="utf-8") as f:
            trends = json.load(f)
    except FileNotFoundError:
        print("❌ 데이터 파일이 없습니다. 1단계를 먼저 실행하세요.")
        return None

    # 2. Reddit / LinkedIn에 올릴 정보성 영문 원고 생성
    top_items = trends[:3] # 상위 3개 급상승 제품 추출
    
    post_content = "🔥 [Weekly Insights] Top Surging K-Beauty Products in Korea\n\n"
    post_content += "Here are the top rising cosmetic trends in Korea this week based on live retail velocity data:\n\n"

    for item in top_items:
        post_content += f"📍 #{item['rank']} {item['brand_en']} - {item['product_en']} (Rank Jump: {item['velocity']})\n"
        post_content += f"   • Key Insight: {item['ai_summary']}\n\n"

    # 사이트 유입용 CTA (Call to Action)
    post_content += "--------------------------------------------------\n"
    post_content += "📊 Want to explore the full Live Rank Velocity Dataset (Top 50+)?\n"
    post_content += "Check out our open live dashboard: https://k-trend-pulse.pages.dev\n"

    return post_content

def send_to_webhook(content):
    """
    Make.com 또는 Zapier 웹훅으로 전송하여 Reddit, LinkedIn에 자동 포스팅합니다.
    """
    webhook_url = os.environ.get("MARKETING_WEBHOOK_URL")
    
    if not webhook_url:
        print("⚠️ 웹훅 URL이 설정되지 않았습니다. 콘솔에 생성된 원고를 출력합니다:\n")
        print(content)
        return

    payload = {"post_text": content}
    response = requests.post(webhook_url, json=payload)
    
    if response.status_code == 200:
        print("✅ [4단계 완료] 해외 커뮤니티 자동 포스팅 웹훅 전송 성공!")
    else:
        print(f"❌ 전송 실패: {response.status_code}")

if __name__ == "__main__":
    post_text = generate_marketing_post()
    if post_text:
        send_to_webhook(post_text)