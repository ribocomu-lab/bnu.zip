"""
에브리타임 리뷰 서비스
- 로그인: Playwright (JS 처리 필요)
- 리뷰 검색: httpx (쿠키 재사용)
- 세션: 인메모리, 1시간 TTL, 서버 미저장
"""

import re
import time
import hashlib
import asyncio
from collections import Counter
from typing import Optional
import httpx

# ── 인메모리 세션 ────────────────────────────────────────────
_sessions: dict[str, dict] = {}
SESSION_TTL = 3600

_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/21A329"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# ── 감정 키워드 ──────────────────────────────────────────────
_POS = [
    "맛있", "좋아", "좋았", "추천", "최고", "대박", "또 갔", "다시", "또 가",
    "친절", "깨끗", "괜찮", "만족", "훈훈", "완벽", "합리", "저렴", "가성비",
    "신선", "맛집", "강추", "인기", "성공", "재방문",
]
_NEG = [
    "별로", "실망", "최악", "비싸", "불친절", "더러", "다신", "안좋",
    "아쉬", "별로였", "못했", "실패", "후회", "비추", "구려",
    "짜다", "싱겁", "차갑", "식었", "위생",
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


# ── 로그인 (Playwright) ──────────────────────────────────────

async def login_everytime(et_id: str, password: str) -> Optional[str]:
    """
    에브리타임 로그인 — Playwright로 실제 브라우저 동작 재현.
    성공 → 세션 토큰 / 실패 → None
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--single-process",
                ],
            )
            ctx = await browser.new_context(user_agent=_UA)
            page = await ctx.new_page()

            # 1) 로그인 페이지
            await page.goto(
                "https://account.everytime.kr/login",
                wait_until="networkidle",
                timeout=15000,
            )

            # 2) 폼 입력
            await page.fill('input[name="id"]', et_id)
            await page.fill('input[name="password"]', password)

            # 3) 제출
            submit = await page.query_selector(
                'input[type="submit"], button[type="submit"]'
            )
            if submit:
                await submit.click()
            else:
                await page.keyboard.press("Enter")

            # 4) 리다이렉트 대기
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await asyncio.sleep(1)

            # 5) 성공 여부 판별
            current_url = page.url
            if "account.everytime.kr/login" in current_url:
                # 여전히 로그인 페이지 = 실패
                await browser.close()
                return None

            # 6) 쿠키 수집
            cookies = await ctx.cookies()
            cookie_dict = {c["name"]: c["value"] for c in cookies}
            await browser.close()

            if not cookie_dict:
                return None

            # 7) 세션 저장
            token = hashlib.sha256(
                f"{et_id}{time.time()}".encode()
            ).hexdigest()[:32]
            _sessions[token] = {
                "cookies": cookie_dict,
                "user_id": et_id,
                "expires": time.time() + SESSION_TTL,
            }
            _purge()
            return token

    except ImportError:
        # Playwright 미설치 시 httpx 폴백 (기능 제한)
        return await _login_httpx(et_id, password)
    except Exception as e:
        print(f"[everytime] playwright login error: {e}")
        return None


async def _login_httpx(et_id: str, password: str) -> Optional[str]:
    """Playwright 없을 때 폴백 (일부 환경에서 작동 안 할 수 있음)"""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=15, headers=_HEADERS
        ) as c:
            get_resp = await c.get("https://account.everytime.kr/login")

            # hidden 필드(CSRF 등) 추출
            form_data: dict[str, str] = {"id": et_id, "password": password}
            for inp in re.findall(r"<input[^>]+>", get_resp.text, re.IGNORECASE):
                t = re.search(r'type=["\']([^"\']+)["\']', inp, re.IGNORECASE)
                n = re.search(r'name=["\']([^"\']+)["\']', inp, re.IGNORECASE)
                v = re.search(r'value=["\']([^"\']*)["\']', inp, re.IGNORECASE)
                if t and t.group(1).lower() == "hidden" and n:
                    form_data[n.group(1)] = v.group(1) if v else ""

            resp = await c.post(
                "https://account.everytime.kr/login",
                data=form_data,
                headers={
                    **_HEADERS,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://account.everytime.kr",
                    "Referer": str(get_resp.url),
                },
            )

            if "account.everytime.kr/login" in str(resp.url):
                return None

            cookies = dict(c.cookies)
            if not cookies:
                return None

            token = hashlib.sha256(
                f"{et_id}{time.time()}".encode()
            ).hexdigest()[:32]
            _sessions[token] = {
                "cookies": cookies,
                "user_id": et_id,
                "expires": time.time() + SESSION_TTL,
            }
            _purge()
            return token
    except Exception as e:
        print(f"[everytime] httpx login error: {e}")
        return None


# ── 리뷰 검색 (httpx + 세션 쿠키) ───────────────────────────

async def fetch_reviews(token: str, restaurant_name: str) -> dict:
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
            resp = await c.get(
                f"https://everytime.kr/search/all/{restaurant_name}"
            )
            if resp.status_code != 200:
                return {"error": f"검색 요청 실패 (HTTP {resp.status_code})"}

            html = resp.text
            if len(html) < 2000 and "로그인" in html:
                return {"error": "에브리타임 세션이 만료됐어요. 다시 로그인해주세요."}

            # 게시글 링크 추출
            links: list[str] = []
            for pattern in [
                r'<a[^>]+class="[^"]*article[^"]*"[^>]+href="([^"]+)"',
                r'href="(/(?:community|board|free|library)[^"]*?/\d+)"',
                r'href="(/[^"?#]+/\d{5,})"',
            ]:
                links = re.findall(pattern, html)
                if links:
                    break

            links = list(dict.fromkeys(links))[:15]

            if not links:
                if len(html) < 3000:
                    return {
                        "error": (
                            "검색 결과를 불러오지 못했어요. "
                            "로그인 세션이 유효한지 확인하거나 다시 로그인해주세요."
                        )
                    }
                return {
                    "count": 0, "reviews": [],
                    "summary": f"'{restaurant_name}' 관련 게시글을 찾지 못했어요.",
                    "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
                    "keywords": [],
                }

            # 게시글 텍스트 수집
            texts: list[str] = []
            for link in links[:10]:
                url = f"https://everytime.kr{link}" if link.startswith("/") else link
                try:
                    pr = await c.get(url)
                    if pr.status_code == 200:
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
                    "summary": f"게시글 {len(links)}개를 찾았지만 텍스트를 추출하지 못했어요.",
                    "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
                    "keywords": [],
                }

            return _analyze(texts, restaurant_name, len(links))

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

        for s in re.split(r"[.!?\n]", text):
            s = s.strip()
            if 15 <= len(s) <= 120:
                rep.append(s)

        words.extend(re.findall(r"[가-힣]{2,5}", text))

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
        return f"'{query}'에 대한 후기를 찾지 못했어요."
    pct = int(pos / total * 100)
    mood = (
        "대체로 긍정적이에요 👍" if pct >= 65
        else "호불호가 갈려요 🤔" if pct >= 40
        else "부정적 의견이 많아요 😕"
    )
    kw_str = "  ".join(f"#{d['word']}" for d in kws[:5])
    return f"에브리타임 {n}개 게시글 기준 — {mood}\n{kw_str}"
