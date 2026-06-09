import httpx
from app.core.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
from app.core.utils import strip_tags, haversine, calc_walk_time

URL = "https://openapi.naver.com/v1/search/local.json"

FOOD_QUERIES = [
    "부산대 맛집", "부산대 한식", "부산대 일식", "부산대 중식", "부산대 양식",
    "부산대 치킨", "부산대 피자", "부산대 분식", "부산대 고기", "부산대 족발",
    "부산대 찜탕", "부산대 돈가스", "부산대 아시안", "부산대 패스트푸드",
    "장전동 맛집", "장전동 한식", "장전동 고기", "장전동 치킨", "장전동 분식",
    "부산대역 맛집", "부산대역 한식", "부산대역 일식",
]
CAFE_QUERIES = ["부산대 카페", "부산대 커피", "부산대 디저트", "부산대 베이커리", "부산대 브런치",
                "장전동 카페", "부산대역 카페"]

FOOD_EXCLUDE = ["베이커리", "카페", "술집", "호프", "야식"]
CAFE_EXCLUDE = ["키즈", "보드", "스파게티", "파스타", "여가", "실내놀이",
                "타로", "PC", "오락", "네일", "마사지", "헬스", "필라테스", "노래"]


async def _search(queries: list[str], exclude: list[str]) -> list[dict]:
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    seen = set()
    results = []

    async with httpx.AsyncClient() as client:
        for query in queries:
            params = {"query": query, "display": 5, "sort": "comment"}
            res = await client.get(URL, headers=headers, params=params)
            for item in res.json().get("items", []):
                name = strip_tags(item["title"])
                if name in seen:
                    continue
                if any(ex in item.get("category", "") for ex in exclude):
                    continue
                seen.add(name)
                cat = item.get("category", "")

                # mapx/mapy로 거리 계산 (네이버 좌표 × 1e-7 = 도)
                try:
                    lat = int(item["mapy"]) / 1e7
                    lng = int(item["mapx"]) / 1e7
                    dist = haversine(lat, lng)
                    dist_str = str(dist)
                    walk_time = calc_walk_time(dist)
                except Exception:
                    dist_str = "-"
                    walk_time = "-"

                entry = {
                    "이름": name,
                    "주소": item.get("roadAddress", item.get("address", "")),
                    "카테고리": cat.split(">")[1].strip() if ">" in cat else cat,
                    "거리(m)": dist_str,
                    "도보시간": walk_time,
                    "출처": "네이버",
                }
                try:
                    entry["lat"] = int(item["mapy"]) / 1e7
                    entry["lng"] = int(item["mapx"]) / 1e7
                except (KeyError, ValueError, TypeError):
                    pass
                results.append(entry)
    return results


async def get_food() -> list[dict]:
    return await _search(FOOD_QUERIES, FOOD_EXCLUDE)


async def get_cafe() -> list[dict]:
    return await _search(CAFE_QUERIES, CAFE_EXCLUDE)
