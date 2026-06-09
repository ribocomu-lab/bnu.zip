"""Google Places API로 좌표 없는 식당 위치 보정

사용법:
  python scripts/enrich_coords.py
"""
import json, time, os, sys, urllib.request, urllib.parse
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
FIND_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
PNU_LAT, PNU_LNG = 35.2323, 129.0876


def fetch_coords(name: str, address: str):
    params = urllib.parse.urlencode({
        "input": f"{name} {address}",
        "inputtype": "textquery",
        "fields": "geometry",
        "language": "ko",
        "key": API_KEY,
    })
    try:
        with urllib.request.urlopen(f"{FIND_URL}?{params}", timeout=10) as r:
            data = json.loads(r.read())
        candidates = data.get("candidates", [])
        if candidates:
            loc = candidates[0].get("geometry", {}).get("location", {})
            return loc.get("lat"), loc.get("lng")
    except Exception as e:
        print(f"  오류: {e}")
    return None, None


def is_default(item):
    lat, lng = item.get("lat"), item.get("lng")
    if not lat or not lng:
        return True
    return abs(lat - PNU_LAT) < 0.0002 and abs(lng - PNU_LNG) < 0.0002


def enrich(fname: str):
    with open(fname, encoding="utf-8") as f:
        items = json.load(f)

    targets = [i for i in items if is_default(i)]
    print(f"{fname}: {len(targets)}/{len(items)}개 좌표 보정 필요")

    updated = 0
    for i, item in enumerate(targets):
        lat, lng = fetch_coords(item["이름"], item.get("주소", "부산 금정구"))
        if lat and lng:
            item["lat"] = lat
            item["lng"] = lng
            updated += 1
            print(f"[{i+1}/{len(targets)}] {item['이름'][:16]:16s} → {lat:.4f}, {lng:.4f}")
        else:
            print(f"[{i+1}/{len(targets)}] {item['이름'][:16]:16s} → 실패")
        time.sleep(0.05)

    with open(fname, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"\n{fname}: {updated}/{len(targets)}개 좌표 확보\n")


if not API_KEY:
    print("오류: GOOGLE_MAPS_API_KEY 환경변수가 없습니다.")
    sys.exit(1)

base = os.path.join(os.path.dirname(__file__), "..", "data")
enrich(os.path.join(base, "restaurants.json"))
enrich(os.path.join(base, "cafe.json"))
print("완료!")
