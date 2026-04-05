import jwt
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

SECRET = os.getenv("JWT_SECRET", "dev-secret")
EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", 24))


def create_token(user_id: int, user_type: str) -> str:
    payload = {
        "sub": str(user_id),
        "type": user_type,
        "exp": datetime.now(timezone.utc) + timedelta(hours=EXPIRY_HOURS),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"])
