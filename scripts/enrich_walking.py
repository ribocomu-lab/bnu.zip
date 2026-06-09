"""Google Distance Matrix API로 실제 도보거리/시간 업데이트

사용법:
  python scripts/enrich_walking.py
"""
import json, time, os, sys, urllib.request, urllib.parse
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
PNU_LAT, PNU_LNG = 35.2323, 129.0876
MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


def get_walk(lat, lng):
    params = urllib.parse.urlencode({
        "origins": f"{PNU_LAT},{PNU_LNG}",
        "destinations": f"{lat},{lng}",
        "mode": "walking",
        "language": "ko",
        "key": API_KEY,
    })
    try:
        with urllib.request.urlopen(f"{MATRIX_URL}?{params}", timeout=10) as r:
            data = json.loads(r.read())
        elem = data["rows"][0]["elements"][0]
        if elem["status"] == "OK":
            return elem["distance"]["value"], elem["duration"]["text"]
    except Exception as e:
        print(f"  오류: {e}")
    return None, None


def fmt_walk(seconds: int) -> str:
    m = round(seconds / 60)
    if m < 1:
        return "1분 이내"
    return f"약 {m}분"


def enrich(fname: str):
    with open(fname, encoding="utf-8") as f:
        items = json.load(f)

    updated = 0
    for i, item in enumerate(items):
        if item.get("_walk_updated"):
            continue
        lat, lng = item.get("lat"), item.get("lng")
        if not lat or not lng:
            continue

        dist_m, walk_text = get_walk(lat, lng)
        if dist_m is not None:
            item["거리(m)"] = str(dist_m)
            item["도보시간"] = walk_text
            item["_walk_updated"] = True
            updated += 1
            print(f"[{i+1}/{len(items)}] {item['이름'][:16]:16s} → {dist_m}m {walk_text}")
        else:
            print(f"[{i+1}/{len(items)}] {item['이름'][:16]:16s} → 실패")
        time.sleep(0.05)

    with open(fname, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"\n{fname}: {updated}/{len(items)}개 업데이트 완료\n")


if not API_KEY:
    print("오류: GOOGLE_MAPS_API_KEY 환경변수가 없습니다.")
    sys.exit(1)

base = os.path.join(os.path.dirname(__file__), "..", "data")
enrich(os.path.join(base, "restaurants.json"))
enrich(os.path.join(base, "cafe.json"))
print("완료! 서버 재시작 후 반영됩니다.")
