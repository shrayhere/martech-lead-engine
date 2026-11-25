import os
from fastapi import APIRouter, Response, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.services.auth_service import verify_password, create_session_token, verify_session_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
def login(req: LoginRequest, response: Response):
    """
    Authenticates user with APP_PASSWORD.
    Sets signed JWT session cookie (httpOnly) and returns session token.
    """
    if not verify_password(req.password):
        raise HTTPException(status_code=401, detail="Invalid application password.")

    token = create_session_token()
    is_prod = os.getenv("ENV", os.getenv("ENVIRONMENT", "development")).lower() in ("production", "prod")
    # Set httpOnly session cookie
    response.set_cookie(
        key="session_token",
        value=token,
        max_age=7 * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=is_prod  # secure=True in production
    )
    return {
        "success": True,
        "token": token,
        "message": "Login successful"
    }


@router.get("/status")
def auth_status(request: Request):
    """
    Checks if current session is authenticated via cookie or Authorization header.
    """
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    is_valid = verify_session_token(token)
    return {
        "authenticated": is_valid
    }


@router.post("/logout")
def logout(response: Response):
    """
    Logs out user by clearing session cookie.
    """
    response.delete_cookie(key="session_token", httponly=True, samesite="lax")
    return {
        "success": True,
        "message": "Logged out successfully"
    }
