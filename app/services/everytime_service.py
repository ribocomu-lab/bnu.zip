"""
에브리타임 리뷰 서비스
- 사용자 인증 (세션 쿠키를 인메모리에만 보관, 서버 DB 미저장)
- 식당명 검색 → 게시글 텍스트 수집
- 키워드 기반 감정 분석 + 요약 생성
"""

import re
import time
import hashlib
import asyncio
from collections import Counter
from typing import Optional
import httpx

# ── 인메모리 세션 (서버 재시작 시 초기화, 1시간 TTL) ────────
_sessions: dict[str, dict] = {}
SESSION_TTL = 3600

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/21A329"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ── 감정 키워드 ──────────────────────────────────────────────
_POS = [
    "맛있", "좋아", "좋았", "추천", "최고", "대박", "또 갔", "다시 갔", "또 가",
    "친절", "깨끗", "괜찮", "만족", "훈훈", "완벽", "합리", "저렴", "가성비",
    "신선", "맛집", "강추", "인기", "성공", "또 가고", "재방문",
]
_NEG = [
    "별로", "실망", "최악", "비싸", "불친절", "더러", "다신", "안좋",
    "아쉬", "별로였", "못했", "실패", "후회", "개별로", "구려", "비추",
    "짜다", "싱겁", "차갑", "식었", "위생", "불결",
]
_STOP = {
    "에서", "하고", "이고", "이다", "있다", "없다", "것이", "했다", "한다",
    "그냥", "진짜", "정말", "되게", "너무", "아주", "매우", "조금", "약간",
    "있어", "없어", "인데", "이랑", "한테", "에게", "으로", "부터", "까지",
    "하는", "하면", "해서", "해도", "했어", "했는", "근데", "그런", "이런",
}


# ── 세션 유틸 ────────────────────────────────────────────────

def _purge():
    now = time.time()
    for k in [k for k, v in _sessions.items() if v["expires"] < now]:
        del _sessions[k]


def get_session(token: str) -> Optional[dict]:
    s = _sessions.get(token)
    if not s or s["expires"] < time.time():
        return None
    return s


def delete_session(token: str) -> None:
    _sessions.pop(token, None)


# ── 로그인 ───────────────────────────────────────────────────

async def login_everytime(et_id: str, password: str) -> Optional[str]:
    """
    에브리타임 로그인.
    성공 → 세션 토큰(str) / 실패 → None
    """
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=20,
            headers=_HEADERS,
        ) as c:
            # 1) 로그인 페이지 방문 — 초기 쿠키 획득
            await c.get("https://account.everytime.kr/login")

            # 2) 폼 POST
            resp = await c.post(
                "https://account.everytime.kr/login",
                data={"id": et_id, "password": password},
                headers={
                    **_HEADERS,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://account.everytime.kr",
                    "Referer": "https://account.everytime.kr/login",
                },
            )

            body = resp.text
            # 실패 판별: 오류 메시지 또는 로그인 페이지 재표시
            if (
                "아이디 또는 비밀번호" in body
                or "로그인에 실패" in body
                or ("login" in str(resp.url) and "logout" not in body)
            ):
                return None

            cookies = dict(c.cookies)
            if not cookies:
                return None

            token = hashlib.sha256(f"{et_id}{time.time()}".encode()).hexdigest()[:32]
            _sessions[token] = {
                "cookies": cookies,
                "user_id": et_id,
                "expires": time.time() + SESSION_TTL,
            }
            _purge()
            return token

    except Exception as e:
        print(f"[everytime] login error: {e}")
        return None


# ── 리뷰 검색 ────────────────────────────────────────────────

async def fetch_reviews(token: str, restaurant_name: str) -> dict:
    """식당 이름 검색 → 분석 결과 dict 반환"""
    session = get_session(token)
    if not session:
        return {"error": "세션이 만료됐어요. 다시 로그인해주세요."}

    try:
        async with httpx.AsyncClient(
            timeout=20,
            headers=_HEADERS,
            cookies=session["cookies"],
            follow_redirects=True,
        ) as c:
            # 1) 검색
            resp = await c.get(
                f"https://everytime.kr/search/all/{restaurant_name}"
            )
            if resp.status_code != 200:
                return {"error": f"검색 요청 실패 (HTTP {resp.status_code})"}

            html = resp.text

            # 세션 만료 감지
            if "로그인" in html and len(html) < 5000:
                return {"error": "에브리타임 세션이 만료됐어요. 다시 로그인해주세요."}

            # 2) 게시글 링크 추출 (다양한 패턴 시도)
            links: list[str] = []
            for pattern in [
                r'href="(/(?:community|board|free|library|review|pnu)[^"]*?/\d+)"',
                r'<a[^>]+class="[^"]*article[^"]*"[^>]+href="([^"]+)"',
                r'href="(/[^"?#]+/\d{5,})"',
            ]:
                found = re.findall(pattern, html)
                links.extend(found)
                if links:
                    break

            links = list(dict.fromkeys(links))[:15]  # 중복 제거, 최대 15개

            if not links:
                if len(html) < 3000:
                    return {
                        "error": (
                            "에브리타임 콘텐츠를 불러오지 못했어요. "
                            "브라우저 기반 실행(Playwright)이 필요합니다."
                        )
                    }
                return {
                    "count": 0, "reviews": [],
                    "summary": f"'{restaurant_name}' 관련 게시글을 찾지 못했어요.",
                    "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
                    "keywords": [],
                }

            # 3) 게시글 텍스트 수집
            texts: list[str] = []
            for link in links[:10]:
                url = f"https://everytime.kr{link}" if link.startswith("/") else link
                try:
                    pr = await c.get(url)
                    if pr.status_code == 200:
                        # <p class="text"> 패턴
                        for raw in re.findall(
                            r'<p[^>]*class="[^"]*\btext\b[^"]*"[^>]*>(.*?)</p>',
                            pr.text, re.DOTALL
                        ):
                            clean = re.sub(r"<[^>]+>", "", raw)
                            clean = re.sub(r"\s+", " ", clean).strip()
                            if clean and len(clean) > 5:
                                texts.append(clean)
                    await asyncio.sleep(0.4)
                except Exception:
                    continue

            if not texts:
                return {
                    "count": len(links),
                    "reviews": [],
                    "summary": (
                        f"게시글 {len(links)}개를 찾았지만 텍스트를 추출하지 못했어요. "
                        "에브리타임이 JavaScript 렌더링을 사용 중일 수 있어요."
                    ),
                    "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
                    "keywords": [],
                }

            return _analyze(texts, restaurant_name, len(links))

    except httpx.RequestError as e:
        return {"error": f"네트워크 오류: {e}"}
    except Exception as e:
        return {"error": f"오류 발생: {e}"}


# ── 분석 ─────────────────────────────────────────────────────

def _analyze(texts: list[str], query: str, post_count: int) -> dict:
    pos = neg = neu = 0
    rep: list[str] = []
    words: list[str] = []

    for text in texts:
        p = sum(1 for kw in _POS if kw in text)
        n = sum(1 for kw in _NEG if kw in text)
        if p > n:
            pos += 1
        elif n > p:
            neg += 1
        else:
            neu += 1

        # 대표 문장 수집
        for s in re.split(r"[.!?\n]", text):
            s = s.strip()
            if 15 <= len(s) <= 120:
                rep.append(s)

        words.extend(re.findall(r"[가-힣]{2,5}", text))

    # 중복 제거된 대표 문장 최대 5개
    seen: set[str] = set()
    rep_out: list[str] = []
    for s in rep:
        key = re.sub(r"\s", "", s[:15])
        if key not in seen:
            seen.add(key)
            rep_out.append(s)
        if len(rep_out) >= 5:
            break

    keywords = [
        {"word": w, "count": c}
        for w, c in Counter(w for w in words if w not in _STOP).most_common(12)
    ]

    total = pos + neg + neu
    return {
        "count": post_count,
        "text_count": total,
        "reviews": rep_out,
        "sentiment": {"positive": pos, "negative": neg, "neutral": neu},
        "keywords": keywords,
        "summary": _make_summary(pos, neg, neu, keywords, query, post_count),
    }


def _make_summary(pos: int, neg: int, neu: int, kws: list, query: str, n: int) -> str:
    total = pos + neg + neu
    if total == 0:
        return f"'{query}'에 대한 의미 있는 후기를 찾지 못했어요."
    pct = int(pos / total * 100)
    mood = (
        "대체로 긍정적이에요 👍" if pct >= 65
        else "호불호가 갈려요 🤔" if pct >= 40
        else "부정적 의견이 많아요 😕"
    )
    kw_str = "  ".join(f"#{d['word']}" for d in kws[:5])
    return f"에브리타임 {n}개 게시글 기준 — {mood}\n{kw_str}"
