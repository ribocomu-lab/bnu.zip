"""Kakao(전화번호) + Naver 스크래핑(운영시간) 보강

Google Places에서 못 찾은 항목을 추가로 채움.

사용법:
  cd backend
  python scripts/enrich_contacts.py
"""
import json, time, os, sys, re, urllib.request, urllib.parse
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

NAVER_ID     = os.getenv("NAVER_CLIENT_ID", "")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
KAKAO_KEY    = os.getenv("KAKAO_API_KEY", "")

KAKAO_KW_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
NAVER_LOCAL  = "https://openapi.naver.com/v1/search/local.json"
MOBILE_UA    = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)
DAYS_KO = {
    "월": "월요일", "화": "화요일", "수": "수요일", "목": "목요일",
    "금": "금요일", "토": "토요일", "일": "일요일",
}
DAY_ORDER = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


# ── 카카오 전화번호 ────────────────────────────────────────────────────────────

def kakao_phone(name: str, address: str) -> str | None:
    # 짧은 쿼리 먼저, 긴 주소 폴백
    for query in [f"{name} 부산대", f"{name} {address}"]:
        params = urllib.parse.urlencode({"query": query, "size": 1})
        req = urllib.request.Request(
            f"{KAKAO_KW_URL}?{params}",
            headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            docs = data.get("documents", [])
            if docs and docs[0].get("phone"):
                return docs[0]["phone"]
        except Exception as e:
            print(f"    kakao 오류: {e}")
        time.sleep(0.05)
    return None


# ── 네이버 place_id 스크래핑 ──────────────────────────────────────────────────

def naver_place_id(name: str, address: str) -> str | None:
    # 1) Local Search API link 필드 확인
    params = urllib.parse.urlencode({"query": f"{name} 부산대", "display": 3})
    req = urllib.request.Request(
        f"{NAVER_LOCAL}?{params}",
        headers={"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        for item in data.get("items", []):
            m = re.search(r"/place/(\d+)", item.get("link", ""))
            if m:
                return m.group(1)
    except Exception:
        pass

    # 2) 모바일 검색 스크래핑
    query = urllib.parse.quote(f"{name} 부산대")
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
    except Exception:
        pass
    return None


# ── 네이버 운영시간 ───────────────────────────────────────────────────────────

def naver_hours(pid: str) -> list[str] | None:
    url = f"https://m.place.naver.com/restaurant/{pid}/home"
    req = urllib.request.Request(url, headers={"User-Agent": MOBILE_UA})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")

        entries = re.findall(
            r'"day":"([^"]+)"[^}]{0,300}?"start":"(\d{1,2}:\d{2})","end":"(\d{1,2}:\d{2})"',
            html,
        )
        if not entries:
            return None

        seen = {}
        for day_raw, start, end in entries:
            day = re.sub(r"\([^)]+\)", "", day_raw).strip()
            day_full = DAYS_KO.get(day, day)
            if day_full not in seen:
                seen[day_full] = f"{start} ~ {end}"

        ordered = [f"{d}: {seen[d]}" for d in DAY_ORDER if d in seen]
        return ordered if ordered else None
    except Exception as e:
        print(f"    naver hours 오류: {e}")
    return None


# ── 메인 ─────────────────────────────────────────────────────────────────────

def enrich(fpath: str):
    with open(fpath, encoding="utf-8") as f:
        items = json.load(f)

    # 전화번호 없거나 운영시간 없는 항목만
    targets = [i for i in items if not i.get("전화번호") or not i.get("운영시간")]
    print(f"\n{os.path.basename(fpath)}: {len(targets)}/{len(items)}개 처리 필요\n")

    phone_ok = hours_ok = 0

    for idx, item in enumerate(targets):
        name    = item["이름"]
        address = item.get("주소", "부산 금정구")
        prefix  = f"[{idx+1}/{len(targets)}] {name[:16]:16s}"

        need_phone = not item.get("전화번호")
        need_hours = not item.get("운영시간")

        phone = item.get("전화번호")
        hours = item.get("운영시간")

        # 전화번호 — 카카오
        if need_phone:
            phone = kakao_phone(name, address)
            time.sleep(0.05)

        # 운영시간 — 네이버 place 스크래핑
        if need_hours:
            pid = naver_place_id(name, address)
            time.sleep(0.15)
            if pid:
                hours = naver_hours(pid)
                time.sleep(0.15)

        if phone:
            item["전화번호"] = phone
            if need_phone:
                phone_ok += 1
        if hours:
            item["운영시간"] = hours
            if need_hours:
                hours_ok += 1

        p_mark = "✓" if phone else "✗"
        h_mark = "✓" if hours else "✗"
        print(f"{prefix} 전화:{p_mark} {str(phone or '')[:16]:16s}  시간:{h_mark} {len(hours) if hours else 0}일")

        if (idx + 1) % 20 == 0:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)

    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"\n완료 — 전화번호+{phone_ok}  운영시간+{hours_ok}/{len(targets)}\n")


base = os.path.join(os.path.dirname(__file__), "..", "data")
enrich(os.path.join(base, "restaurants.json"))
enrich(os.path.join(base, "cafe.json"))
print("전체 완료!")
