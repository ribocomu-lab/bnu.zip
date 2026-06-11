from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from app.services import review_service
from app.api.auth import get_current_user

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


class ReviewBody(BaseModel):
    restaurant: str
    rating: int = Field(ge=1, le=5)
    text: str
    tag: str = ""  # 선후배 1:1 / 선후배 1:2 / 선후배 2:2 / 단체모임


@router.get("")
def list_reviews(restaurant: str = Query(...)):
    return review_service.get_reviews(restaurant)


@router.get("/mine")
def my_reviews(user=Depends(get_current_user)):
    return review_service.get_user_reviews(user["email"])


@router.post("")
def create_review(body: ReviewBody, user=Depends(get_current_user)):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "리뷰 내용을 입력해주세요.")
    return review_service.add_review(body.restaurant, user["email"], user["name"], body.rating, text, body.tag.strip())


@router.delete("/{review_id}")
def remove_review(review_id: str, user=Depends(get_current_user)):
    if not review_service.delete_review(review_id, user["email"]):
        raise HTTPException(404, "리뷰를 찾을 수 없어요.")
    return {"ok": True}
