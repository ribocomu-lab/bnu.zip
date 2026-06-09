"""카카오 place_url에서 가게 대표 사진 URL 보강

사용법:
  cd backend
  python scripts/enrich_photos.py
"""
import json, time, os, sys, urllib.request, urllib.parse, re
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

KAKAO_API_KEY = os.getenv("KAKAO_API_KEY", "")
KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

KAKAO_HEADERS = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

GENERIC_IMAGES = {"kakaomap.com/static", "daumcdn.net/thumb/default", "no_img"}


def get_place_url(name: str) -> str | None:
    params = urllib.parse.urlencode({"query": name, "size": 1})
    req = urllib.request.Request(f"{KEYWORD_URL}?{params}", headers=KAKAO_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        docs = data.get("documents", [])
        if docs:
            return docs[0].get("place_url")
    except Exception as e:
        print(f"  카카오 검색 오류({name[:10]}): {e}")
    return None


def get_og_image(place_url: str) -> str | None:
    req = urllib.request.Request(place_url, headers=BROWSER_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")

        # og:image 추출 (두 가지 태그 순서 처리)
        patterns = [
            r'property=["\']og:image["\'][^>]+content=["\']([^"\'> ]+)',
            r'content=["\']([^"\'> ]+)["\'][^>]+property=["\']og:image',
        ]
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                img = m.group(1).strip()
                # 프로토콜 없는 URL 보정
                if img.startswith("//"):
                    img = "https:" + img
                # 일반 placeholder 이미지 제외
                if any(g in img for g in GENERIC_IMAGES):
                    return None
                if img.startswith("http"):
                    return img
    except Exception as e:
        print(f"  페이지 fetch 오류: {e}")
    return None


def enrich(fpath: str):
    with open(fpath, encoding="utf-8") as f:
        items = json.load(f)

    targets = [i for i in items if not i.get("사진")]
    print(f"\n{os.path.basename(fpath)}: {len(targets)}/{len(items)}개 처리 필요")

    updated = 0
    for idx, item in enumerate(targets):
        place_url = get_place_url(item["이름"])
        if not place_url:
            item["사진"] = None
            print(f"[{idx+1}/{len(targets)}] {item['이름'][:18]:18s} - place 없음")
            time.sleep(0.1)
            continue

        img = get_og_image(place_url)
        item["사진"] = img
        if img:
            updated += 1
            print(f"[{idx+1}/{len(targets)}] {item['이름'][:18]:18s} ✓")
        else:
            print(f"[{idx+1}/{len(targets)}] {item['이름'][:18]:18s} - 사진 없음")
        time.sleep(0.2)

    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"  → {updated}/{len(targets)}개 사진 확보")


if not KAKAO_API_KEY:
    print("오류: KAKAO_API_KEY 없음")
    sys.exit(1)

base = os.path.join(os.path.dirname(__file__), "..", "data")
enrich(os.path.join(base, "restaurants.json"))
enrich(os.path.join(base, "cafe.json"))
print("\n완료!")
