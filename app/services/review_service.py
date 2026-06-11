import json
import os
import time
import hashlib
from app.core.config import DATA_DIR
from app.services import user_service

REVIEWS_JSON = os.path.join(DATA_DIR, "reviews.json")


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


def add_review(restaurant: str, user_email: str, user_name: str, rating: int, text: str) -> dict:
    reviews = _load()
    review = {
        "id": hashlib.sha256(f"{user_email}{restaurant}{time.time()}".encode()).hexdigest()[:16],
        "restaurant": restaurant,
        "user_email": user_email,
        "user_name": user_name,
        "rating": rating,
        "text": text,
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
