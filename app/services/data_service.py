import json
import os
import re
from app.core.config import DATA_DIR
from app.core.utils import get_main_category
from app.crawlers import naver, kakao

FOOD_JSON = os.path.join(DATA_DIR, "restaurants.json")
CAFE_JSON = os.path.join(DATA_DIR, "cafe.json")
SURVEY_JSON = os.path.join(DATA_DIR, "survey.json")


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


def _preserve_survey_entries(merged: list[dict], existing: list[dict]) -> list[dict]:
    """크롤링 갱신 시 설문으로 추가한 식당(출처=설문)이 크롤링 결과에 없으면 기존 항목을 유지한다.
    (수동으로 채운 필드도 함께 보존됨. 크롤링에 같은 식당이 잡히면 크롤링 데이터 우선.)"""
    have = {_normalize_name(i["이름"]) for i in merged}
    for item in existing:
        if item.get("출처") == "설문" and _normalize_name(item["이름"]) not in have:
            merged.append(item)
    return merged


async def refresh_food() -> list[dict]:
    naver_data, kakao_data = await naver.get_food(), await kakao.get_food()
    merged = _merge_dedupe(naver_data, kakao_data)
    merged = _preserve_survey_entries(merged, _load(FOOD_JSON))
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


# ── 추천 점수 ─────────────────────────────────────────────
# 최종점수(n) = 0.60 × 기본점수 B + 0.25 × 설문가산점 S + 0.15 × 수용적합도 C(n)
#   B: 거리/가격/별점/리뷰신뢰도 가중합 (상황별 가중치)
#   S: 설문 등재 식당 가산점 = 예비율 × min(언급수/3, 1), 미등재 0
#   C: 수용인원 ≥ 인원수 → 1.0 / 미만 → 0.0 / 설문 정보 없음 → 0.3 (후순위)
# 설문 식당을 무조건 앞세우지 않고 가산점으로만 반영해 비설문 식당과 섞이게 함.

WEIGHTS_DEFAULT = {"거리": 0.35, "가격": 0.25, "별점": 0.25, "신뢰도": 0.15}
# 3인(선배1:후배2) 약속: 가성비 우선 → 가격 비중 강화
WEIGHTS_VALUE = {"거리": 0.20, "가격": 0.40, "별점": 0.25, "신뢰도": 0.15}


def _normalize_name(name: str) -> str:
    """식당명 매칭 키: 공백·괄호 제거, 지점명 접미사 제거 (scripts/build_survey.py와 동일)"""
    s = re.sub(r"\(.*?\)", "", name or "")
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"(부산대본점|부산대점|본점|전문점)$", "", s)
    return s


def _load_survey() -> dict:
    """설문 집계(survey.json)를 정규화된 식당명 키로 로드"""
    return _load_dict(SURVEY_JSON)


def get_survey() -> dict:
    """프론트(추천 화면)에서 사용할 설문 집계 데이터"""
    return _load_survey()


def _load_dict(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _base_score(item: dict, weights: dict) -> float:
    """기본점수 B: 거리/가격/별점/리뷰신뢰도 (각 0~1)"""
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

    return (
        dist_score * weights["거리"]
        + price_score * weights["가격"]
        + rating_score * weights["별점"]
        + trust * weights["신뢰도"]
    )


def _survey_score(entry: dict | None) -> float:
    """설문 가산점 S = 예비율 × min(언급수/3, 1). 미등재 시 0."""
    if not entry:
        return 0.0
    return entry["예비율"] * min(entry["언급수"] / 3, 1.0)


def _capacity_fit(entry: dict | None, people: int | None) -> float:
    """수용 적합도 C(n). 설문 정보 없으면 0.3(후순위)."""
    if not entry:
        return 0.3
    if people is None:
        return 1.0
    return 1.0 if entry["수용인원"] >= people else 0.0


def _score(item: dict, survey: dict, people: int | None = None, value_priority: bool = False) -> float:
    """최종점수 = 0.60×B + 0.25×S + 0.15×C"""
    weights = WEIGHTS_VALUE if value_priority else WEIGHTS_DEFAULT
    entry = survey.get(_normalize_name(item.get("이름", "")))
    b = _base_score(item, weights)
    s = _survey_score(entry)
    c = _capacity_fit(entry, people)
    return round(b * 0.60 + s * 0.25 + c * 0.15, 4)


def get_recommend(people: int | None = None, seniors: int | None = None, juniors: int | None = None) -> dict:
    """추천 지수 상위 10개 중 가중 랜덤 추천.

    people/seniors/juniors: 약속 인원수와 선후배 구성.
    선배1:후배2 3인 약속이면 가성비(가격) 가중치를 우선 적용한다.
    """
    import random
    food_items = _load(FOOD_JSON)
    cafe_items = _load(CAFE_JSON)
    survey = _load_survey()

    value_priority = people == 3 and seniors == 1 and juniors == 2

    for item in food_items:
        item["추천점수"] = _score(item, survey, people=people, value_priority=value_priority)
    for item in cafe_items:
        item["추천점수"] = _score(item, survey, people=people, value_priority=value_priority)

    food_pool = sorted(food_items, key=lambda x: x["추천점수"], reverse=True)[:10]
    cafe_pool = sorted(cafe_items, key=lambda x: x["추천점수"], reverse=True)[:10]

    return {
        "밥집": random.choice(food_pool) if food_pool else None,
        "카페": random.choice(cafe_pool) if cafe_pool else None,
    }
