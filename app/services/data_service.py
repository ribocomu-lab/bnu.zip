import json
import os
from app.core.config import DATA_DIR
from app.core.utils import get_main_category
from app.crawlers import naver, kakao

FOOD_JSON = os.path.join(DATA_DIR, "restaurants.json")
CAFE_JSON = os.path.join(DATA_DIR, "cafe.json")


def _load(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(path: str, data: list[dict]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _merge_dedupe(naver_items: list[dict], kakao_items: list[dict]) -> list[dict]:
    """이름 기준 중복 제거 후 합치기. 카카오(거리 정보 있음)를 우선 앞에."""
    seen = set()
    result = []
    for item in kakao_items + naver_items:
        if item["이름"] not in seen:
            seen.add(item["이름"])
            item["대분류"] = get_main_category(item["카테고리"])
            result.append(item)
    return result


async def refresh_food() -> list[dict]:
    naver_data, kakao_data = await naver.get_food(), await kakao.get_food()
    merged = _merge_dedupe(naver_data, kakao_data)
    _save(FOOD_JSON, merged)
    return merged


async def refresh_cafe() -> list[dict]:
    naver_data, kakao_data = await naver.get_cafe(), await kakao.get_cafe()
    merged = _merge_dedupe(naver_data, kakao_data)
    _save(CAFE_JSON, merged)
    return merged


def get_food(sort: str = "거리순", category: str | None = None) -> list[dict]:
    items = _load(FOOD_JSON)
    if category:
        items = [i for i in items if i.get("대분류") == category]
    return _sort(items, sort)


def get_cafe(sort: str = "거리순") -> list[dict]:
    items = _load(CAFE_JSON)
    return _sort(items, sort)


def _sort(items: list[dict], sort: str) -> list[dict]:
    if sort == "거리순":
        return sorted(items, key=lambda x: int(x["거리(m)"]) if x["거리(m)"] != "-" else 9999)
    if sort == "카테고리별":
        return sorted(items, key=lambda x: x.get("대분류", ""))
    return items


def _score(item: dict) -> float:
    """추천 지수: (거리×0.35) + (가격×0.25) + (별점×0.25) + (리뷰신뢰도×0.15)"""
    dist = item.get("거리(m)", "-")
    try:
        dist_score = max(0.0, 1 - int(dist) / 1000)  # 1km 기준
    except (ValueError, TypeError):
        dist_score = 0.5

    try:
        price = item.get("가격")
        price_score = max(0.0, 1 - int(price) / 10000) if price else 0.5
    except (ValueError, TypeError):
        price_score = 0.5

    rating = item.get("별점")
    # 현실적 범위 2.5~5.0 → 0~1 로 정규화
    rating_score = max(0.0, (float(rating) - 2.5) / 2.5) if rating is not None else 0.5

    reviews = item.get("리뷰수")
    trust = min(int(reviews) / 100, 1.0) if reviews is not None else 0.3

    return round((dist_score * 0.35) + (price_score * 0.25) + (rating_score * 0.25) + (trust * 0.15), 4)


def get_recommend() -> dict:
    """추천 지수 상위 10개 중 가중 랜덤 추천"""
    import random
    food_items = _load(FOOD_JSON)
    cafe_items = _load(CAFE_JSON)

    for item in food_items:
        item["추천점수"] = _score(item)
    for item in cafe_items:
        item["추천점수"] = _score(item)

    food_pool = sorted(food_items, key=lambda x: x["추천점수"], reverse=True)[:10]
    cafe_pool = sorted(cafe_items, key=lambda x: x["추천점수"], reverse=True)[:10]

    return {
        "밥집": random.choice(food_pool) if food_pool else None,
        "카페": random.choice(cafe_pool) if cafe_pool else None,
    }
