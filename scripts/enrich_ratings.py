"""Google Places API로 식당 별점/리뷰수 보강

사용법:
  .env에 GOOGLE_MAPS_API_KEY=<키> 추가 후
  python scripts/enrich_ratings.py
"""
import json, time, os, sys, urllib.request, urllib.parse
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
FIND_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"


def fetch_rating(name: str, address: str):
    params = urllib.parse.urlencode({
        "input": f"{name} {address}",
        "inputtype": "textquery",
        "fields": "rating,user_ratings_total",
        "language": "ko",
        "key": API_KEY,
    })
    try:
        with urllib.request.urlopen(f"{FIND_URL}?{params}", timeout=10) as res:
            data = json.loads(res.read())
        candidates = data.get("candidates", [])
        if candidates:
            c = candidates[0]
            return c.get("rating"), c.get("user_ratings_total")
    except Exception as e:
        print(f"  오류: {e}")
    return None, None


def enrich(fname: str):
    with open(fname, encoding="utf-8") as f:
        items = json.load(f)

    updated = 0
    for i, item in enumerate(items):
        if "별점" in item:
            continue
        rating, review_count = fetch_rating(item["이름"], item.get("주소", "부산 금정구"))
        item["별점"] = rating
        item["리뷰수"] = review_count
        if rating is not None:
            updated += 1
            print(f"[{i+1}/{len(items)}] {item['이름']} → ★{rating} ({review_count}개)")
        else:
            print(f"[{i+1}/{len(items)}] {item['이름']} → 검색 실패")
        time.sleep(0.05)

    with open(fname, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"\n{fname}: {updated}/{len(items)}개 별점 확보\n")


if not API_KEY:
    print("오류: GOOGLE_MAPS_API_KEY 환경변수가 없습니다.")
    print(".env 파일에 GOOGLE_MAPS_API_KEY=<키> 를 추가하세요.")
    sys.exit(1)

base = os.path.join(os.path.dirname(__file__), "..", "data")
enrich(os.path.join(base, "restaurants.json"))
enrich(os.path.join(base, "cafe.json"))
print("완료!")
