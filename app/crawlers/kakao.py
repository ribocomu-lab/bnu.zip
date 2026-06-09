import httpx
from app.core.config import KAKAO_API_KEY, PNU_LAT, PNU_LNG
from app.core.utils import calc_walk_time

CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category.json"
KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

FOOD_EXCLUDE = ["샐러드", "간식", "베이커리", "제과", "도시락", "술집", "호프", "야식"]
CAFE_EXCLUDE = ["키즈", "보드", "스파게티", "파스타", "여가", "실내놀이",
                "방탈출", "노래", "당구", "스크린", "타로", "PC방", "오락",
                "네일", "마사지", "헬스", "필라테스", "코인노래"]

FOOD_KEYWORDS = [
    "부산대 한식", "부산대 일식", "부산대 중식", "부산대 양식", "부산대 치킨",
    "부산대 피자", "부산대 분식", "부산대 고기", "부산대 족발", "부산대 찜탕",
    "부산대 돈가스", "장전동 맛집", "부산대역 맛집", "금정구 맛집",
]


async def _category_search(category_code: str, exclude: list[str], radius: int = 1000) -> list[dict]:
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    seen = set()
    results = []

    async with httpx.AsyncClient() as client:
        for page in range(1, 10):
            params = {
                "category_group_code": category_code,
                "x": PNU_LNG, "y": PNU_LAT,
                "radius": radius, "sort": "distance",
                "size": 15, "page": page,
            }
            res = await client.get(CATEGORY_URL, headers=headers, params=params)
            data = res.json()
            for doc in data.get("documents", []):
                name = doc["place_name"]
                cat = doc.get("category_name", "")
                if name in seen or any(ex in cat for ex in exclude):
                    continue
                seen.add(name)
                dist = doc.get("distance", "-")
                results.append(_make_item(doc, dist))
            if data.get("meta", {}).get("is_end", True):
                break
    return results, seen


async def _keyword_search(keywords: list[str], exclude: list[str], seen: set, radius: int = 1000) -> list[dict]:
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    results = []

    async with httpx.AsyncClient() as client:
        for keyword in keywords:
            for page in range(1, 4):
                params = {
                    "query": keyword,
                    "x": PNU_LNG, "y": PNU_LAT,
                    "radius": radius, "sort": "distance",
                    "size": 15, "page": page,
                }
                res = await client.get(KEYWORD_URL, headers=headers, params=params)
                data = res.json()
                for doc in data.get("documents", []):
                    name = doc["place_name"]
                    cat = doc.get("category_name", "")
                    if name in seen or any(ex in cat for ex in exclude):
                        continue
                    if "CE7" in cat or "카페" in cat or "커피" in cat:
                        continue
                    seen.add(name)
                    dist = doc.get("distance", "-")
                    results.append(_make_item(doc, dist))
                if data.get("meta", {}).get("is_end", True):
                    break
    return results


def _make_item(doc: dict, dist) -> dict:
    cat = doc.get("category_name", "")
    item = {
        "이름": doc["place_name"],
        "주소": doc.get("road_address_name", doc.get("address_name", "")),
        "카테고리": cat.split(">")[1].strip() if ">" in cat else cat,
        "거리(m)": dist,
        "도보시간": calc_walk_time(dist),
        "출처": "카카오",
    }
    try:
        item["lat"] = float(doc["y"])
        item["lng"] = float(doc["x"])
    except (KeyError, ValueError, TypeError):
        pass
    return item


async def get_food() -> list[dict]:
    category_results, seen = await _category_search("FD6", FOOD_EXCLUDE)
    keyword_results = await _keyword_search(FOOD_KEYWORDS, FOOD_EXCLUDE, seen)
    return category_results + keyword_results


async def get_cafe() -> list[dict]:
    results, _ = await _category_search("CE7", CAFE_EXCLUDE)
    return results
