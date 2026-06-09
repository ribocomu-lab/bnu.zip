import json, os
from app.core.config import DATA_DIR

USERS_JSON = os.path.join(DATA_DIR, "users.json")


def _load() -> dict:
    if not os.path.exists(USERS_JSON):
        return {}
    with open(USERS_JSON, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    os.makedirs(os.path.dirname(USERS_JSON), exist_ok=True)
    with open(USERS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def upsert_user(email: str, name: str, picture: str) -> dict:
    users = _load()
    if email not in users:
        users[email] = {"email": email, "name": name, "picture": picture, "bookmarks": [], "visited": []}
    else:
        users[email]["name"] = name
        users[email]["picture"] = picture
        if "visited" not in users[email]:
            users[email]["visited"] = []
    _save(users)
    return users[email]


def get_user(email: str) -> dict | None:
    return _load().get(email)


def get_bookmarks(email: str) -> list:
    user = get_user(email)
    return user.get("bookmarks", []) if user else []


def set_bookmarks(email: str, bookmarks: list) -> list:
    users = _load()
    if email in users:
        users[email]["bookmarks"] = bookmarks
        _save(users)
    return bookmarks


def get_visited(email: str) -> list:
    user = get_user(email)
    return user.get("visited", []) if user else []


def set_visited(email: str, visited: list) -> list:
    users = _load()
    if email in users:
        users[email]["visited"] = visited
        _save(users)
    return visited
