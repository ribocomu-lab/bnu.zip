from fastapi import APIRouter, Query
from app.services import data_service
from app.core.config import GOOGLE_MAPS_API_KEY, KAKAO_JS_KEY

router = APIRouter(prefix="/api")


@router.get("/food")
async def food(
    sort: str = Query("거리순", description="거리순 | 카테고리별"),
    category: str | None = Query(None, description="한식, 치킨, 카페 등 대분류"),
):
    return data_service.get_food(sort=sort, category=category)


@router.get("/cafe")
async def cafe(
    sort: str = Query("거리순", description="거리순 | 카테고리별"),
):
    return data_service.get_cafe(sort=sort)


@router.get("/recommend")
async def recommend():
    return data_service.get_recommend()


@router.get("/config")
def config():
    return {"google_maps_key": GOOGLE_MAPS_API_KEY, "kakao_key": KAKAO_JS_KEY}


# 데이터 수집 트리거 (배포 후 한 번만 호출하면 JSON에 캐시됨)
@router.post("/refresh")
async def refresh():
    food = await data_service.refresh_food()
    cafe = await data_service.refresh_cafe()
    return {"food_count": len(food), "cafe_count": len(cafe)}
