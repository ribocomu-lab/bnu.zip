import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.api.auth import router as auth_router
from app.api.reviews import router as reviews_router

app = FastAPI(title="PNUeat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.include_router(reviews_router)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))


@app.get("/home")
def home():
    return FileResponse(os.path.join(STATIC_DIR, "home.html"))


@app.get("/search")
def search():
    return FileResponse(os.path.join(STATIC_DIR, "search.html"))


@app.get("/recommend")
def recommend_page():
    return FileResponse(os.path.join(STATIC_DIR, "recommend.html"))


@app.get("/mylist")
def mylist():
    return FileResponse(os.path.join(STATIC_DIR, "mylist.html"))


@app.get("/login")
def login_page():
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))


@app.get("/detail")
def detail_page():
    return FileResponse(os.path.join(STATIC_DIR, "detail.html"))


@app.get("/reviews")
def reviews_page():
    return FileResponse(os.path.join(STATIC_DIR, "reviews.html"))


@app.get("/health")
def health():
    return {"status": "ok"}
