import json
import os
import random
import time
import requests

# [설정] 환경변수가 있으면 우선 사용, 없으면 직접 입력한 토큰 사용
THREADS_USER_ID = "me"
ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "THAAXHdHWZB48pBYlp6SmcxWEpkcklrLUJfQ0lXcDd3XzNwM2FCaEZAlTm1Yc1kwUWl3MFlYVGtXUkRRNmNYU0ozM3FHYjBvUnZAOTFFNSzJTakx0aFBqNlFyLUhpV2E5Y2xzaGNqZAjEwQzd4WjdJSVhUeXUzcTlCUWRFWE00bWNmUmZAVaEpkbEI0S2s1MlVILVkZD")

CACHE_FILE = "today_deals_cache.json"
INDEX_TRACKER_FILE = "threads_rotation_idx.txt"
KAKAO_LINK = "https://open.kakao.com/o/g80iZNLi"
WEB_LINK = "https://gptmaker95.github.io/toss-deal"

# 주목도를 높이는 후킹 문구 10선
HOOK_TITLES = [
    "🚨 이거 제값 주고 샀으면 땅을 치고 후회할 뻔했습니다",
    "⏰ 오늘 자정 지나면 원복되는 가격이라 급하게 공유해요",
    "🔍 쿠팡보다 싼 거 맞는지 최저가 직접 뜯어보고 골랐습니다",
    "⚡ 알고리즘 뚫고 찾은 오늘자 토스 가격 오류급 특가",
    "🛒 요즘 물가 미쳤는데… 이건 장바구니 무조건 담아야 이득입니다",
    "💡 자취생·주부님들 주목! 마트 갈 필요 없는 역대급 할인 모음",
    "🤔 솔직히 이 가격이면 남는 게 있나 싶은 오늘자 라인업",
    "📌 모르면 정가 다 내고 사는 토스 숨은 알짜 핫딜 3선",
    "🔥 재고 빠지기 전에 빠르게 털어야 하는 실시간 특가",
    "⏳ 단 몇 시간만 열리는 가격! 품절 뜨기 전에 확인하세요"
]

def get_next_rotation_items(deals, batch_size=3):
    """품절되지 않은 특가 중 다음 3개를 순환 선택"""
    active_deals = [d for d in deals if not d.get("isSoldOut")]
    if not active_deals:
        print("[스레드] 현재 살아있는 하루특가 상품이 없습니다.")
        return []

    current_idx = 0
    if os.path.exists(INDEX_TRACKER_FILE):
        try:
            with open(INDEX_TRACKER_FILE, "r", encoding="utf-8") as f:
                current_idx = int(f.read().strip())
        except Exception:
            current_idx = 0

    if current_idx >= len(active_deals):
        current_idx = 0

    selected = active_deals[current_idx : current_idx + batch_size]

    next_idx = current_idx + batch_size
    if next_idx >= len(active_deals):
        next_idx = 0

    with open(INDEX_TRACKER_FILE, "w", encoding="utf-8") as f:
        f.write(str(next_idx))

    return selected

def build_thread_message(items):
    """스레드에 올릴 본문 텍스트 생성"""
    hook_header = random.choice(HOOK_TITLES)
    lines = [hook_header, ""]
    
    for it in items:
        # 쉼표 자르기를 제거해 규격/수량을 보존하고, 38자 초과 시에만 말줄임표 처리
        raw_name = it.get('displayName', '').strip()
        name = raw_name if len(raw_name) <= 38 else raw_name[:35] + "..."
        
        discount = it.get('discountRate', 0)
        price = f"{it.get('displayPrice', 0):,}원"
        rating = f" ★{it['rating']}" if it.get('rating') else ""
        
        lines.append(f"▫️ {name}")
        lines.append(f"   👉 {discount}% 할인 | {price}{rating}")
        lines.append("")

    lines.extend([
        "🔥 실시간 랭킹 & 전체 특가 보러가기:",
        f"👉 {WEB_LINK}",
        "",
        "💬 실시간 핫딜 알림 오픈채팅방:",
        f"👉 {KAKAO_LINK}",
        "",
        "쿠팡보다 저렴한 상품으로 모아놨어! 오픈톡방 구경하고 가 ㅎㅎ"
    ])
    return "\n".join(lines)

def post_to_threads():
    if not os.path.exists(CACHE_FILE):
        print(f"[오류] {CACHE_FILE} 파일이 없습니다. analyze_and_build.py를 먼저 1회 실행하세요.")
        return

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        deals = json.load(f)

    selected_items = get_next_rotation_items(deals, batch_size=3)
    if not selected_items:
        return

    message = build_thread_message(selected_items)
    image_url = selected_items[0].get("thumbnailUrl")

    base_url = "https://graph.threads.net/v1.0"
    
    print(f"[1] 스레드 컨테이너 생성 요청 중... (첫 상품: {selected_items[0]['displayName'][:15]}...)")
    create_url = f"{base_url}/{THREADS_USER_ID}/threads"
    
    if image_url and image_url.startswith("http"):
        payload = {
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": message,
            "access_token": ACCESS_TOKEN
        }
    else:
        payload = {
            "media_type": "TEXT",
            "text": message,
            "access_token": ACCESS_TOKEN
        }

    res = requests.post(create_url, data=payload)
    res_data = res.json()

    if "id" not in res_data:
        print("[스레드 오류] 컨테이너 생성 실패:", res_data)
        return

    creation_id = res_data["id"]
    print(f" -> 컨테이너 생성 완료 (ID: {creation_id}), 메타 서버 처리 대기 중...")
    
    time.sleep(5)

    print("[2] 피드 최종 발행 중...")
    publish_url = f"{base_url}/{THREADS_USER_ID}/threads_publish"
    pub_res = requests.post(publish_url, data={"creation_id": creation_id, "access_token": ACCESS_TOKEN})
    pub_data = pub_res.json()

    if "id" in pub_data:
        print(f"🎉 성공! 스레드 포스팅 완료 (게시물 ID: {pub_data['id']})")
    else:
        print("[스레드 오류] 최종 발행 실패:", pub_data)

if __name__ == "__main__":
    post_to_threads()