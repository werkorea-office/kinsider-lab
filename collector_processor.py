import os
import json
from datetime import datetime

# ==========================================
# 1. 국내 커머스 가상 수집 데이터 (Top 10 항목)
# ==========================================
def get_raw_korean_trends():
    """
    올리브영/쿠팡 등에서 수집된 국내 실시간 뷰티 랭킹 원본 데이터 (Top 10)
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
        },
        {
            "current_rank": 4,
            "prev_rank": 35,
            "brand_kr": "메디힐",
            "product_kr": "흔적 패드 (마데카소사이드)",
            "category": "Toner Pad",
            "notes": "데일리 피부 장벽 케어 및 진정 니즈 증가"
        },
        {
            "current_rank": 5,
            "prev_rank": 50,
            "brand_kr": "바이오던스",
            "product_kr": "콜라겐 리얼 딥 마스크",
            "category": "Sheet Mask",
            "notes": "수면 마스크 형태의 하이드로겔 패치 인기"
        },
        {
            "current_rank": 6,
            "prev_rank": 62,
            "brand_kr": "라운드랩",
            "product_kr": "자작나무 수분 선크림",
            "category": "Sun Care",
            "notes": "백탁 없는 촉촉한 유기자차 제형 보편화"
        },
        {
            "current_rank": 7,
            "prev_rank": 40,
            "brand_kr": "코스알엑스",
            "product_kr": "어드밴스드 스네일 96 엠피신 팩",
            "category": "Essence",
            "notes": "해외 스테디셀러의 국내 역수입 바이럴"
        },
        {
            "current_rank": 8,
            "prev_rank": 75,
            "brand_kr": "성분에디터",
            "product_kr": "그린토마토 모공 타이트닝 앰플",
            "category": "Ampoule",
            "notes": "모공 축소 타겟팅 숏폼 광고 효능 입증"
        },
        {
            "current_rank": 9,
            "prev_rank": 30,
            "brand_kr": "토리든",
            "product_kr": "다이브인 저분자 히알루론산 세럼",
            "category": "Serum",
            "notes": "속건조 해결 수분 세럼 부문 지속 상위권"
        },
        {
            "current_rank": 10,
            "prev_rank": 88,
            "brand_kr": "넘버즈인",
            "product_kr": "3번 결광가득 세럼",
            "category": "Serum",
            "notes": "발효 성분 바탕 피부 결 개선 후기 지속"
        }
    ]

# ==========================================
# 2. AI 가공 및 Rank Velocity(상승 폭) 계산
# ==========================================
def process_data_with_ai(raw_data):
    processed_list = []
    
    # Top 10 까지만 처리하도록 제한
    for item in raw_data[:10]:
        velocity = item["prev_rank"] - item["current_rank"]
        
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

# 영문 번역 및 AI 인사이트 매핑 함수
def translate_brand(kr_brand):
    mapping = {
        "조선미녀": "Beauty of Joseon",
        "VT코스메틱": "VT Cosmetics",
        "아누아": "Anua",
        "메디힐": "Mediheal",
        "바이오던스": "Biodance",
        "라운드랩": "Round Lab",
        "코스알엑스": "COSRX",
        "성분에디터": "Sungboon Editor",
        "토리든": "Torriden",
        "넘버즈인": "numbuzin"
    }
    return mapping.get(kr_brand, kr_brand)

def translate_product(kr_product):
    mapping = {
        "맑은쌀 선크림": "Relief Sun: Rice + Probiotics",
        "리들샷 100 에센스": "Reedle Shot 100 Essence",
        "어성초 77 수딩 토너": "Heartleaf 77% Soothing Toner",
        "흔적 패드 (마데카소사이드)": "Madecassoside Blemish Pad",
        "콜라겐 리얼 딥 마스크": "Bio-Collagen Real Deep Mask",
        "자작나무 수분 선크림": "Birch Juice Moisturizing Sunscreen",
        "어드밴스드 스네일 96 엠피신 팩": "Advanced Snail 96 Mucin Power Essence",
        "그린토마토 모공 타이트닝 앰플": "Green Tomato Pore Lifting Ampoule",
        "다이브인 저분자 히알루론산 세럼": "Dive-In Low Molecule Hyaluronic Acid Serum",
        "3번 결광가득 세럼": "No.3 Skin Softening Serum"
    }
    return mapping.get(kr_product, kr_product)

def generate_ai_summary(brand, product, notes):
    return f"Surging demand in Korea due to {notes}. High potential for global re-sellers."

# ==========================================
# 3. 데이터 저장 함수
# ==========================================
def save_trend_data(trend_data):
    os.makedirs('data', exist_ok=True)
    today_str = datetime.now().strftime('%Y-%m-%d')
    file_path = f'data/trends_{today_str}.json'
    
    payload = {
        "date": today_str,
        "timestamp": datetime.now().isoformat(),
        "trends": trend_data
    }
    
    # 1. 일별 파일 저장
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Saved daily trend data to {file_path}")

    # 2. 누적 history.json 저장
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

# ==========================================
# 4. 메인 실행부
# ==========================================
if __name__ == "__main__":
    raw_trends = get_raw_korean_trends()
    final_data = process_data_with_ai(raw_trends)
    
    # 1) processed_latest.json 저장 (단일 파이프라인용)
    os.makedirs("data", exist_ok=True)
    with open("data/processed_latest.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
        
    # 2) 일별/누적 데이터 저장 (히스토리용)
    save_trend_data(final_data)
    
    print("✅ [1단계 완료] Top 10 데이터 수집, 영문 AI 가공 및 JSON 저장이 완료되었습니다!")
