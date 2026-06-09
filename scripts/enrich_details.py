"""Google Places API로 전화번호·운영시간 보강 (2단계)

1단계: findplacefromtext → place_id 획득
2단계: place/details → 전화번호, 운영시간

사용법:
  python scripts/enrich_details.py
"""
import json, time, os, sys, urllib.request, urllib.parse
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
FIND_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def get_place_id(name: str, address: str):
    params = urllib.parse.urlencode({
        "input": f"{name} {address}",
        "inputtype": "textquery",
        "fields": "place_id",
        "language": "ko",
        "key": API_KEY,
    })
    try:
        with urllib.request.urlopen(f"{FIND_URL}?{params}", timeout=10) as r:
            data = json.loads(r.read())
        c = data.get("candidates", [])
        return c[0]["place_id"] if c else None
    except Exception as e:
        print(f"  find오류: {e}")
    return None


def get_details(place_id: str):
    params = urllib.parse.urlencode({
        "place_id": place_id,
        "fields": "formatted_phone_number,opening_hours",
        "language": "ko",
        "key": API_KEY,
    })
    try:
        with urllib.request.urlopen(f"{DETAILS_URL}?{params}", timeout=10) as r:
            data = json.loads(r.read())
        result = data.get("result", {})
        phone = result.get("formatted_phone_number")
        hours = result.get("opening_hours", {}).get("weekday_text", [])
        return phone, hours
    except Exception as e:
        print(f"  detail오류: {e}")
    return None, []


def enrich(fname: str):
    with open(fname, encoding="utf-8") as f:
        items = json.load(f)

    # 이미 처리된 항목 스킵 (재실행 시)
    targets = [i for i in items if "전화번호" not in i]
    print(f"{fname}: {len(targets)}/{len(items)}개 처리 필요")

    updated = 0
    for idx, item in enumerate(targets):
        pid = get_place_id(item["이름"], item.get("주소", "부산 금정구"))
        if not pid:
            item["전화번호"] = None
            item["운영시간"] = []
            print(f"[{idx+1}/{len(targets)}] {item['이름'][:14]:14s} → place_id 없음")
            time.sleep(0.05)
            continue

        phone, hours = get_details(pid)
        item["전화번호"] = phone
        item["운영시간"] = hours
        if phone or hours:
            updated += 1
            print(f"[{idx+1}/{len(targets)}] {item['이름'][:14]:14s} → {phone or '-'}  시간:{len(hours)}개")
        else:
            print(f"[{idx+1}/{len(targets)}] {item['이름'][:14]:14s} → 정보 없음")
        time.sleep(0.1)

    with open(fname, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"\n{fname}: {updated}/{len(targets)}개 확보\n")


if not API_KEY:
    print("오류: GOOGLE_MAPS_API_KEY 없음")
    sys.exit(1)

# 이전 실행에서 빈 값으로 채워진 항목 초기화
def reset_empty(fname):
    with open(fname, encoding="utf-8") as f:
        items = json.load(f)
    for item in items:
        if "전화번호" in item and item["전화번호"] is None and item.get("운영시간") == []:
            del item["전화번호"]
            del item["운영시간"]
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

base = os.path.join(os.path.dirname(__file__), "..", "data")
food_path = os.path.join(base, "restaurants.json")
cafe_path = os.path.join(base, "cafe.json")

reset_empty(food_path)
reset_empty(cafe_path)

enrich(food_path)
enrich(cafe_path)
print("완료!")
