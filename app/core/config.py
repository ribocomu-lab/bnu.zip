from dotenv import load_dotenv
import os, secrets

load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
KAKAO_API_KEY = os.getenv("KAKAO_API_KEY", "")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "")
KAKAO_JS_KEY = os.getenv("KAKAO_JS_KEY") or KAKAO_API_KEY

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

PNU_LAT = 35.2323
PNU_LNG = 129.0847

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
