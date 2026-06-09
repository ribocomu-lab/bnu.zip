import math
import re

from app.core.config import PNU_LAT, PNU_LNG


def haversine(lat: float, lng: float) -> int:
    """PNU 기준 직선거리(m) 계산"""
    R = 6371000
    p1, p2 = math.radians(lat), math.radians(PNU_LAT)
    dp = math.radians(PNU_LAT - lat)
    dl = math.radians(PNU_LNG - lng)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return int(2 * R * math.asin(math.sqrt(a)))


def calc_walk_time(distance_m) -> str:
    """직선거리 × 1.3 ÷ 67m/분"""
    if not distance_m or distance_m == "-":
        return "-"
    real_distance = int(distance_m) * 1.5
    minutes = real_distance / 67
    if minutes < 1:
        return "1분 이내"
    return f"약 {math.ceil(minutes)}분"


def get_main_category(category: str) -> str:
    c = category.replace(" ", "")
    if "치킨" in c:
        return "치킨"
    if "패스트푸드" in c or "햄버거" in c or "피자" in c or "버거" in c:
        return "패스트푸드"
    if "돈가스" in c or "돈까스" in c or "초밥" in c or "일식" in c or "회" in c:
        return "일식"
    if "베트남" in c or "아시아" in c or "아시안" in c or "인도" in c or "태국" in c:
        return "아시아"
    if "고기" in c or "구이" in c or "삼겹" in c or "갈비" in c or "불고기" in c or "주물럭" in c or "족발" in c or "보쌈" in c:
        return "고기"
    if "찜" in c or "탕" in c or "순대" in c or "국밥" in c or "한식" in c or "백반" in c or "솥밥" in c:
        return "한식"
    if "중식" in c or "중국" in c:
        return "중식"
    if "분식" in c:
        return "분식"
    if "양식" in c or "스테이크" in c or "파스타" in c or "이탈리안" in c:
        return "양식"
    return "기타"


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)
