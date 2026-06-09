from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.services.everytime_service import (
    login_everytime,
    fetch_reviews,
    get_session,
    delete_session,
)

router = APIRouter(prefix="/api/everytime", tags=["everytime"])


class LoginBody(BaseModel):
    id: str
    password: str


@router.post("/login")
async def login(body: LoginBody):
    """에브리타임 로그인 → 세션 토큰 반환"""
    if not body.id.strip() or not body.password:
        raise HTTPException(400, "아이디와 비밀번호를 입력해주세요.")
    token = await login_everytime(body.id.strip(), body.password)
    if not token:
        raise HTTPException(401, "로그인 실패 — 아이디·비밀번호를 확인해주세요.")
    return {"token": token}


@router.get("/check")
def check(token: str = Query(...)):
    """세션 유효 여부 확인"""
    s = get_session(token)
    if not s:
        raise HTTPException(401, "세션이 만료됐어요.")
    return {"valid": True, "user_id": s["user_id"]}


@router.get("/reviews")
async def reviews(
    token: str = Query(..., description="login 토큰"),
    restaurant: str = Query(..., description="식당 이름"),
):
    """식당 이름으로 에브리타임 후기 검색 + 요약"""
    if not restaurant.strip():
        raise HTTPException(400, "식당 이름이 비어있어요.")
    result = await fetch_reviews(token, restaurant.strip())
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.delete("/session")
def logout(token: str = Query(...)):
    """세션 삭제 (로그아웃)"""
    delete_session(token)
    return {"ok": True}
