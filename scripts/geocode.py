"""주소 → 위경도 변환 후 JSON에 저장 (Nominatim, 1req/sec)"""
import json, time, urllib.request, urllib.parse, sys, os

sys.stdout.reconfigure(encoding="utf-8")

PNU_LAT, PNU_LNG = 35.2323, 129.0876


def geocode(address: str):
    params = urllib.parse.urlencode({"q": address, "format": "json", "limit": 1})
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "pnueat/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read())
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"  오류: {e}")
    return None, None


def process(fname: str):
    with open(fname, encoding="utf-8") as f:
        items = json.load(f)

    updated = 0
    for i, item in enumerate(items):
        if item.get("lat") and item.get("lng"):
            continue
        addr = item.get("주소", "")
        lat, lng = geocode(addr)
        item["lat"] = lat if lat else PNU_LAT
        item["lng"] = lng if lng else PNU_LNG
        updated += 1
        print(f"[{i+1}/{len(items)}] {item['이름']} → {item['lat']:.4f}, {item['lng']:.4f}")
        time.sleep(1.1)

    with open(fname, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"{fname}: {updated}개 업데이트 완료")


base = os.path.join(os.path.dirname(__file__), "..", "data")
process(os.path.join(base, "restaurants.json"))
process(os.path.join(base, "cafe.json"))
print("완료!")
