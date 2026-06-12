import json
import os
import time
import hashlib
import random
from app.core.config import DATA_DIR
from app.services import user_service

REVIEWS_JSON = os.path.join(DATA_DIR, "reviews.json")

# 익명 닉네임: 댓글 달 때마다 랜덤 생성 (리뷰에 저장돼 해당 댓글에선 고정)
NICK_ADJ = ['배고픈', '행복한', '졸린', '수줍은', '씩씩한', '느긋한', '야무진', '용감한', '신난', '과제하는', '밥약하는', '지각한']
NICK_NOUN = ['산지니', '금정산다람쥐', '넉터비둘기', '효원이', '웅비탑지킴이', '새벽벌요정', '문창회관단골', '미리내오리', '부엉이', '곰두리']


def _anon_nick() -> str:
    return f"{random.choice(NICK_ADJ)} {random.choice(NICK_NOUN)}"


def _load() -> list[dict]:
    if not os.path.exists(REVIEWS_JSON):
        return []
    with open(REVIEWS_JSON, encoding="utf-8") as f:
        return json.load(f)


def _save(data: list[dict]):
    os.makedirs(os.path.dirname(REVIEWS_JSON), exist_ok=True)
    with open(REVIEWS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_reviews(restaurant: str) -> dict:
    reviews = [r for r in _load() if r["restaurant"] == restaurant]
    reviews.sort(key=lambda r: r["created_at"], reverse=True)
    count = len(reviews)
    average = round(sum(r["rating"] for r in reviews) / count, 1) if count else 0
    return {"reviews": reviews, "average": average, "count": count}


def get_user_reviews(user_email: str) -> list[dict]:
    reviews = [r for r in _load() if r["user_email"] == user_email]
    reviews.sort(key=lambda r: r["created_at"], reverse=True)
    return reviews


def add_review(restaurant: str, user_email: str, user_name: str, rating: int, text: str, tag: str = "") -> dict:
    reviews = _load()
    review = {
        "id": hashlib.sha256(f"{user_email}{restaurant}{time.time()}".encode()).hexdigest()[:16],
        "restaurant": restaurant,
        "user_email": user_email,
        "user_name": user_name,
        "anon_name": _anon_nick(),
        "rating": rating,
        "text": text,
        "tag": tag,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    reviews.append(review)
    _save(reviews)
    user_service.add_review_ref(user_email, review)
    return review


def delete_review(review_id: str, user_email: str) -> bool:
    reviews = _load()
    filtered = [r for r in reviews if not (r["id"] == review_id and r["user_email"] == user_email)]
    if len(filtered) == len(reviews):
        return False
    _save(filtered)
    user_service.remove_review_ref(user_email, review_id)
    return True
