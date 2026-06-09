"""네이버 지도 별점·리뷰수·Google Places 사진 보강

흐름:
  1. 네이버 모바일 검색 스크래핑 → place_id 추출
  2. 네이버 모바일 플레이스 페이지 → 별점, 리뷰수 파싱
  3. Google Places API → 업체 사진 최대 5장 (CDN URL 추출)

실패 시 별점/리뷰수는 Google Places API로 폴백.

사용법:
  cd backend
  python scripts/enrich_naver.py
"""
import json, time, os, sys, re, urllib.request, urllib.parse
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

NAVER_ID     = os.getenv("NAVER_CLIENT_ID", "")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
GOOGLE_KEY   = os.getenv("GOOGLE_MAPS_API_KEY", "")

LOCAL_URL         = "https://openapi.naver.com/v1/search/local.json"
GOOGLE_URL        = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
GOOGLE_DETAIL_URL = "https://maps.googleapis.com/maps/api/place/details/json"
GOOGLE_PHOTO_URL  = "https://maps.googleapis.com/maps/api/place/photo"

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)


# ── 네이버 place_id 취득 ────────────────────────────────────────────────────

def get_naver_place_id(name: str, address: str) -> str | None:
    # Method 1: Naver Local Search API — some items have /place/(\d+) in link
    params = urllib.parse.urlencode({"query": f"{name} {address}", "display": 3})
    req = urllib.request.Request(
        f"{LOCAL_URL}?{params}",
        headers={
            "X-Naver-Client-Id": NAVER_ID,
            "X-Naver-Client-Secret": NAVER_SECRET,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        for item in data.get("items", []):
            link = item.get("link", "")
            m = re.search(r"/place/(\d+)", link)
            if m:
                return m.group(1)
    except Exception as e:
        print(f"    naver search 오류: {e}")

    # Method 2: Scrape Naver mobile search page
    return _scrape_naver_place_id(name, address)


def _scrape_naver_place_id(name: str, address: str) -> str | None:
    query = urllib.parse.quote(f"{name} {address}")
    url = f"https://m.search.naver.com/search.naver?where=m_local&query={query}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": MOBILE_UA, "Accept-Language": "ko-KR,ko;q=0.9"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")
        for pat in [
            r"place\.naver\.com/restaurant/(\d+)",
            r"place\.naver\.com/[a-z]+/(\d+)",
            r"/entry/place/(\d+)",
        ]:
            m = re.search(pat, html)
            if m:
                return m.group(1)
    except Exception as e:
        print(f"    naver scrape 오류: {e}")
    return None


# ── 네이버 모바일 페이지 → 별점·리뷰수 ────────────────────────────────────

def get_naver_rating(place_id: str):
    url = f"https://m.place.naver.com/restaurant/{place_id}/home"
    req = urllib.request.Request(url, headers={"User-Agent": MOBILE_UA})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")

        rm = (
            re.search(r'"starScore"\s*:\s*"?([\d.]+)"?', html)
            or re.search(r'"avgRating"\s*:\s*"?([\d.]+)"?', html)
            or re.search(r'"reviewScore"\s*:\s*"?([\d.]+)"?', html)
        )
        vm = (
            re.search(r'"visitorReviewCount"\s*:\s*(\d+)', html)
            or re.search(r'"reviewCount"\s*:\s*(\d+)', html)
        )
        if rm:
            return float(rm.group(1)), int(vm.group(1)) if vm else 0
    except Exception as e:
        print(f"    naver rating 오류: {e}")
    return None, None


# ── Google Places 사진 (CDN URL 추출) ─────────────────────────────────────

def get_google_place_id(name: str, address: str) -> str | None:
    params = urllib.parse.urlencode({
        "input": f"{name} {address}",
        "inputtype": "textquery",
        "fields": "place_id",
        "language": "ko",
        "key": GOOGLE_KEY,
    })
    try:
        with urllib.request.urlopen(f"{GOOGLE_URL}?{params}", timeout=10) as r:
            data = json.loads(r.read())
        c = data.get("candidates", [])
        if c:
            return c[0].get("place_id")
    except Exception as e:
        print(f"    google place_id 오류: {e}")
    return None


def get_google_photos(google_place_id: str, max_count: int = 5) -> list[str]:
    params = urllib.parse.urlencode({
        "place_id": google_place_id,
        "fields": "photos",
        "language": "ko",
        "key": GOOGLE_KEY,
    })
    photos = []
    try:
        with urllib.request.urlopen(f"{GOOGLE_DETAIL_URL}?{params}", timeout=10) as r:
            data = json.loads(r.read())
        refs = [p.get("photo_reference") for p in data.get("result", {}).get("photos", [])[:max_count]]
        for ref in refs:
            if not ref:
                continue
            api_url = (
                f"{GOOGLE_PHOTO_URL}?maxwidth=800"
                f"&photo_reference={ref}&key={GOOGLE_KEY}"
            )
            try:
                # Follow redirect → get actual CDN URL (no API key in stored URL)
                opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
                with opener.open(api_url, timeout=10) as pr:
                    cdn_url = pr.url
                photos.append(cdn_url)
                time.sleep(0.08)
            except Exception:
                photos.append(api_url)
    except Exception as e:
        print(f"    google photos 오류: {e}")
    return photos


# ── Google 폴백: 별점·리뷰수 ───────────────────────────────────────────────

def get_google_rating(name: str, address: str):
    params = urllib.parse.urlencode({
        "input": f"{name} {address}",
        "inputtype": "textquery",
        "fields": "rating,user_ratings_total",
        "language": "ko",
        "key": GOOGLE_KEY,
    })
    try:
        with urllib.request.urlopen(f"{GOOGLE_URL}?{params}", timeout=10) as r:
            data = json.loads(r.read())
        c = data.get("candidates", [])
        if c:
            return c[0].get("rating"), c[0].get("user_ratings_total")
    except Exception as e:
        print(f"    google rating 오류: {e}")
    return None, None


# ── 메인 ───────────────────────────────────────────────────────────────────

def enrich(fpath: str):
    with open(fpath, encoding="utf-8") as f:
        items = json.load(f)

    # 처리 대상: 별점 없거나 사진목록 없는 항목
    targets = [i for i in items if i.get("별점") is None or not i.get("사진목록")]
    print(f"\n{os.path.basename(fpath)}: {len(targets)}/{len(items)}개 처리 필요\n")

    naver_ok = google_ok = photo_ok = 0

    for idx, item in enumerate(targets):
        name    = item["이름"]
        address = item.get("주소", "부산 금정구")
        prefix  = f"[{idx+1}/{len(targets)}] {name[:16]:16s}"

        needs_rating = item.get("별점") is None
        needs_photos = not item.get("사진목록")

        rating, reviews = item.get("별점"), item.get("리뷰수")
        src = "-"

        if needs_rating:
            # 1) 네이버 place_id (모바일 검색 스크래핑)
            pid = get_naver_place_id(name, address)
            time.sleep(0.2)

            if pid:
                rating, reviews = get_naver_rating(pid)
                time.sleep(0.15)

            if rating is None and GOOGLE_KEY:
                rating, reviews = get_google_rating(name, address)
                if rating is not None:
                    google_ok += 1
                    src = "G"
                else:
                    src = "✗"
            elif rating is not None:
                naver_ok += 1
                src = "N"

        # 2) 사진 — Google Places
        photos = item.get("사진목록") or []
        if needs_photos and GOOGLE_KEY:
            g_pid = get_google_place_id(name, address)
            time.sleep(0.1)
            if g_pid:
                photos = get_google_photos(g_pid)
                time.sleep(0.15)
            if photos:
                photo_ok += 1

        item["별점"]    = rating
        item["리뷰수"]  = reviews
        item["사진목록"] = photos
        if photos and not item.get("사진"):
            item["사진"] = photos[0]

        print(
            f"{prefix} 별점:{str(rating or '-'):>5}({src})  "
            f"리뷰:{str(reviews or 0):>5}  사진:{len(photos)}장"
        )

        if (idx + 1) % 10 == 0:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)

    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"\n완료 — 네이버:{naver_ok}  구글폴백:{google_ok}  사진:{photo_ok}/{len(targets)}\n")


if not NAVER_ID or not NAVER_SECRET:
    print("오류: NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 없음")
    sys.exit(1)

base = os.path.join(os.path.dirname(__file__), "..", "data")
enrich(os.path.join(base, "restaurants.json"))
enrich(os.path.join(base, "cafe.json"))
print("전체 완료!")
