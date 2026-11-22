import os
import hmac
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt

APP_PASSWORD = os.getenv("APP_PASSWORD", "martech2026")
SECRET_KEY = os.getenv("SECRET_KEY", "martech-super-secure-secret-token-key-2026")
ALGORITHM = "HS256"
SESSION_DURATION_DAYS = 7


def verify_password(plain_password: str) -> bool:
    """Safely checks password against APP_PASSWORD using constant-time comparison."""
    if not plain_password:
        return False
    configured = os.getenv("APP_PASSWORD", "martech2026")
    return hmac.compare_digest(plain_password.encode("utf-8"), configured.encode("utf-8"))


def create_session_token() -> str:
    """Issues a signed JWT token valid for 7 days."""
    secret = os.getenv("SECRET_KEY", SECRET_KEY)
    expire = datetime.now(timezone.utc) + timedelta(days=SESSION_DURATION_DAYS)
    payload = {
        "sub": "admin",
        "role": "authenticated_user",
        "iat": int(time.time()),
        "exp": expire
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def verify_session_token(token: Optional[str]) -> bool:
    """Verifies validity and expiration of session token."""
    if not token:
        return False
    secret = os.getenv("SECRET_KEY", SECRET_KEY)
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return payload.get("sub") == "admin"
    except (jwt.PyJWTError, Exception):
        return False
