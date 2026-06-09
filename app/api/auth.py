from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import jwt, JWTError
import httpx, json, os, urllib.parse
from fastapi.responses import RedirectResponse
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from app.core.config import GOOGLE_CLIENT_ID, KAKAO_API_KEY, KAKAO_CLIENT_SECRET, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_DAYS
from app.services import user_service

KAKAO_REDIRECT_URI = os.getenv(
    "KAKAO_REDIRECT_URI",
    "http://127.0.0.1:8000/api/auth/kakao/callback"
)
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://127.0.0.1:8000/api/auth/google/callback"
)

router = APIRouter(prefix="/api/auth")
bearer = HTTPBearer(auto_error=False)


class GoogleTokenRequest(BaseModel):
    token: str


class KakaoTokenRequest(BaseModel):
    access_token: str


class BookmarkRequest(BaseModel):
    bookmarks: list[str]


class VisitedRequest(BaseModel):
    visited: list[str]


def create_jwt(email: str) -> str:
    expire = datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS)
    return jwt.encode({"sub": email, "exp": expire}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if not credentials:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="유효하지 않은 토큰")
        user = user_service.get_user(email)
        if not user:
            raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰")


@router.post("/google")
def google_login(body: GoogleTokenRequest):
    try:
        info = id_token.verify_oauth2_token(
            body.token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"구글 토큰 검증 실패: {e}")

    email = info["email"]
    name = info.get("name", "")
    picture = info.get("picture", "")

    user = user_service.upsert_user(email, name, picture)
    token = create_jwt(email)
    return {"token": token, "user": user}


@router.get("/me")
def me(user=Depends(get_current_user)):
    return user


@router.get("/bookmarks")
def get_bookmarks(user=Depends(get_current_user)):
    return user_service.get_bookmarks(user["email"])


@router.post("/bookmarks")
def save_bookmarks(body: BookmarkRequest, user=Depends(get_current_user)):
    return user_service.set_bookmarks(user["email"], body.bookmarks)


@router.get("/visited")
def get_visited_list(user=Depends(get_current_user)):
    return user_service.get_visited(user["email"])


@router.post("/visited")
def save_visited(body: VisitedRequest, user=Depends(get_current_user)):
    return user_service.set_visited(user["email"], body.visited)


@router.get("/google/url")
def google_auth_url():
    params = urllib.parse.urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
    })
    return {"url": f"https://accounts.google.com/o/oauth2/v2/auth?{params}"}


@router.get("/google/callback")
async def google_callback(code: str):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post("https://oauth2.googleapis.com/token", data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            })
            token_data = res.json()
            if "id_token" not in token_data:
                print(f"[GOOGLE ERROR] {token_data}")
                return RedirectResponse("/login?google_error=1")
            id_tok = token_data["id_token"]
    except Exception as e:
        print(f"[GOOGLE REQUEST ERROR] {e}")
        return RedirectResponse("/login?google_error=1")

    try:
        info = id_token.verify_oauth2_token(id_tok, google_requests.Request(), GOOGLE_CLIENT_ID)
    except Exception as e:
        print(f"[GOOGLE TOKEN ERROR] {e}")
        return RedirectResponse("/login?google_error=1")

    email = info["email"]
    name = info.get("name", "")
    picture = info.get("picture", "")
    user = user_service.upsert_user(email, name, picture)
    jwt_token = create_jwt(email)
    user_encoded = urllib.parse.quote(json.dumps(user, ensure_ascii=False))
    return RedirectResponse(f"/?_kt={jwt_token}&_ku={user_encoded}")


@router.get("/kakao/url")
def kakao_auth_url():
    url = (
        "https://kauth.kakao.com/oauth/authorize"
        f"?client_id={KAKAO_API_KEY}"
        f"&redirect_uri={urllib.parse.quote(KAKAO_REDIRECT_URI)}"
        "&response_type=code"
    )
    return {"url": url}


@router.get("/kakao/callback")
async def kakao_callback(code: str):
    # 1. 인가코드 → 액세스 토큰
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "grant_type": "authorization_code",
                "client_id": KAKAO_API_KEY,
                "redirect_uri": KAKAO_REDIRECT_URI,
                "code": code,
            }
            if KAKAO_CLIENT_SECRET:
                payload["client_secret"] = KAKAO_CLIENT_SECRET
            res = await client.post("https://kauth.kakao.com/oauth/token", data=payload)
            token_data = res.json()
            if "access_token" not in token_data:
                print(f"[KAKAO ERROR] token_data: {token_data}")
                return RedirectResponse("/login?kakao_error=1")
            access_token = token_data["access_token"]
    except httpx.RequestError as e:
        print(f"[KAKAO REQUEST ERROR] {e}")
        return RedirectResponse("/login?kakao_error=1")

    # 2. 액세스 토큰 → 사용자 정보
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get("https://kapi.kakao.com/v2/user/me",
                headers={"Authorization": f"Bearer {access_token}"})
            info = res.json()
    except httpx.RequestError:
        return RedirectResponse("/login?kakao_error=1")

    kakao_account = info.get("kakao_account", {})
    profile = kakao_account.get("profile", {})
    email = kakao_account.get("email") or f"kakao_{info['id']}@kakao.local"
    name = profile.get("nickname", "카카오 사용자")
    picture = profile.get("thumbnail_image_url", "")

    user = user_service.upsert_user(email, name, picture)
    jwt_token = create_jwt(email)

    # 3. 프론트엔드로 리다이렉트 (토큰 전달)
    user_encoded = urllib.parse.quote(json.dumps(user, ensure_ascii=False))
    return RedirectResponse(f"/?_kt={jwt_token}&_ku={user_encoded}")
