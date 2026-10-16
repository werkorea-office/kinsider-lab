import os
import json
from datetime import datetime

# ==========================================
# 1. 국내 커머스 가상 수집 데이터 (스크래핑 예시)
# ==========================================
def get_raw_korean_trends():
    """
    올리브영/쿠팡 등에서 수집된 국내 실시간 뷰티 랭킹 원본 데이터입니다.
    """
    return [
        {
            "current_rank": 1,
            "prev_rank": 45,
            "brand_kr": "조선미녀",
            "product_kr": "맑은쌀 선크림",
            "category": "Sun Care",
            "notes": "틱톡 숏폼 바이럴 및 북미 직구 수요 급증"
        },
        {
            "current_rank": 2,
            "prev_rank": 12,
            "brand_kr": "VT코스메틱",
            "product_kr": "리들샷 100 에센스",
            "category": "Serum / Essence",
            "notes": "미세침 성분 피부 결 개선 후기 폭발"
        },
        {
            "current_rank": 3,
            "prev_rank": 80,
            "brand_kr": "아누아",
            "product_kr": "어성초 77 수딩 토너",
            "category": "Toner",
            "notes": "여드름 진정 케어 트렌드로 순위 수직 상승"
        }
    ]

# ==========================================
# 2. AI 가공 및 Rank Velocity(상승 폭) 계산
# ==========================================
def process_data_with_ai(raw_data):
    processed_list = []
    
    for item in raw_data:
        # 순위 상승 폭 계산 (양수일수록 폭발적 상승)
        velocity = item["prev_rank"] - item["current_rank"]
        
        # 가공된 데이터 구조 (해외 B2B 제공용)
        processed_item = {
            "rank": item["current_rank"],
            "velocity": f"+{velocity}" if velocity > 0 else str(velocity),
            "brand_en": translate_brand(item["brand_kr"]),
            "product_en": translate_product(item["product_kr"]),
            "category": item["category"],
            "ai_summary": generate_ai_summary(item["brand_kr"], item["product_kr"], item["notes"])
        }
        processed_list.append(processed_item)
        
    return processed_list

# 영문 번역 및 AI 인사이트 생성 가상 함수 (AI API 연동부)
def translate_brand(kr_brand):
    mapping = {
        "조선미녀": "Beauty of Joseon",
        "VT코스메틱": "VT Cosmetics",
        "아누아": "Anua"
    }
    return mapping.get(kr_brand, kr_brand)

def translate_product(kr_product):
    mapping = {
        "맑은쌀 선크림": "Relief Sun: Rice + Probiotics",
        "리들샷 100 에센스": "Reedle Shot 100 Essence",
        "어성초 77 수딩 토너": "Heartleaf 77% Soothing Toner"
    }
    return mapping.get(kr_product, kr_product)

def generate_ai_summary(brand, product, notes):
    # 실제 환경에서는 Gemini API가 영문 인사이트 3줄 요약을 자동 생성합니다.
    return f"Surging demand in Korea due to {notes}. High potential for global re-sellers."

# ==========================================
# 3. 가공 완료된 JSON 저장
# ==========================================
if __name__ == "__main__":
    raw_trends = get_raw_korean_trends()
    final_data = process_data_with_ai(raw_trends)
    
    # 결과를 JSON 파일로 저장 (웹사이트와 바로 연동됨)
    os.makedirs("data", exist_ok=True)
    with open("data/processed_latest.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
        
    print("✅ [1단계 완료] 데이터 수집 및 영문 AI 가공이 완료되었습니다! (data/processed_latest.json 저장됨)")
    import json
import os
from datetime import datetime

def save_trend_data(trend_data):
    os.makedirs('data', exist_ok=True)
    today_str = datetime.now().strftime('%Y-%m-%d')
    file_path = f'data/trends_{today_str}.json'
    
    payload = {
        "date": today_str,
        "timestamp": datetime.now().isoformat(),
        "trends": trend_data
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Saved daily trend data to {file_path}")

    history_file = 'data/history.json'
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []
            
    history = [item for item in history if item.get('date') != today_str]
    history.append(payload)
    
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"Updated {history_file}")
