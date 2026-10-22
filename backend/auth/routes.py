"""
backend/auth/routes.py
======================
FastAPI APIRouter for user registration, authentication, logout,
session status (/me), and password reset flows.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status

from backend.auth.models import (
    AuthStatusResponse,
    CurrentUserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from backend.auth.rate_limiter import login_rate_limiter
from backend.auth.service import AuthService

logger = logging.getLogger("privsight.auth")

auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
auth_service = AuthService()

SESSION_COOKIE_NAME = "privsight_session"


def _extract_token(
    cookie_token: Optional[str] = None,
    authorization: Optional[str] = None,
) -> Optional[str]:
    """Helper to extract token from HttpOnly cookie or Authorization Bearer header."""
    if cookie_token:
        return cookie_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def get_authenticated_user(
    privsight_session: Optional[str] = Cookie(None),
    authorization: Optional[str] = Header(None),
) -> UserResponse:
    """
    FastAPI dependency for enforcing server-side authentication on private endpoints.
    Extracts session token from cookie or Authorization header and returns UserResponse.
    Raises HTTP 401 Unauthorized if token is missing, invalid, or expired.
    """
    token = _extract_token(privsight_session, authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in to access this resource.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = auth_service.get_user_by_session(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or is invalid. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    payload: UserRegisterRequest,
    response: Response,
    request: Request,
):
    """
    Registers a new PrivSight user account, enforces password validation,
    hashes credentials with bcrypt, and initiates an authenticated session.
    """
    try:
        user = auth_service.register_user(
            full_name=payload.full_name,
            email=payload.email,
            password=payload.password,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as e:
        logger.error("Registration error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration could not be completed. Please try again.",
        )

    # Automatically establish session after successful registration
    token, _, max_age = auth_service.create_session(user.id, remember_me=False)
    is_secure = request.url.scheme == "https"

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        path="/",
    )

    return {
        "status": "success",
        "message": "Account created successfully.",
        "user": user,
    }


@auth_router.post("/login")
def login(
    payload: UserLoginRequest,
    response: Response,
    request: Request,
    privsight_session: Optional[str] = Cookie(None),
    authorization: Optional[str] = Header(None),
):
    """
    Authenticates user with email and password via bcrypt.
    Enforces login rate limiting (5 attempts / 5 mins).
    Performs session regeneration to prevent session fixation.
    Sets HttpOnly session cookie on success.
    """
    # 1. Rate limiting check per (client_ip, email)
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_limited, retry_after = login_rate_limiter.is_rate_limited(client_ip, payload.email)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please wait {retry_after} seconds before trying again.",
            headers={"Retry-After": str(retry_after)},
        )

    # 2. Authenticate credentials
    user = auth_service.authenticate_user(
        email=payload.email,
        password=payload.password,
    )

    if not user:
        login_rate_limiter.record_failure(client_ip, payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please verify your credentials.",
        )

    # 3. Successful authentication: reset rate limiter failures
    login_rate_limiter.reset(client_ip, payload.email)

    # 4. Session regeneration: invalidate existing session if present
    old_token = _extract_token(privsight_session, authorization)
    token, _, max_age = auth_service.create_session(
        user.id,
        remember_me=payload.remember_me,
        old_token=old_token,
    )
    is_secure = request.url.scheme == "https"

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        path="/",
    )

    return {
        "status": "success",
        "message": "Signed in successfully.",
        "user": user,
    }


@auth_router.post("/logout")
def logout(
    response: Response,
    privsight_session: Optional[str] = Cookie(None),
    authorization: Optional[str] = Header(None),
):
    """Terminates the active session and clears the HttpOnly cookie."""
    token = _extract_token(privsight_session, authorization)
    if token:
        auth_service.destroy_session(token)

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
    )

    return {
        "status": "success",
        "message": "Session terminated successfully.",
    }


@auth_router.get("/me", response_model=CurrentUserResponse)
def get_current_user(
    current_user: UserResponse = Depends(get_authenticated_user),
):
    """
    Returns the currently authenticated user based on session token.
    Rejects unauthenticated requests with HTTP 401 Unauthorized.
    Never exposes passwords or sensitive internal hashes.
    """
    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        created_at=current_user.created_at,
        authenticated=True,
        user=current_user,
    )


@auth_router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    """
    Initiates real password reset flow. Generates token and records instructions.
    If external email gateway is not configured, provides clear transparent notice.
    """
    token, email_sent = auth_service.create_password_reset(payload.email)

    if email_sent:
        message = "Password reset instructions have been dispatched to your email address."
    else:
        message = (
            "If an account with that email exists, password reset instructions have been generated. "
            "(Note: SMTP delivery is unconfigured; reset token generated in secure server logs for local dev environment)."
        )

    return {
        "status": "success",
        "message": message,
        "email_sent": email_sent,
        "dev_token_available": token is not None,
    }


@auth_router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    """Resets password using valid unexpired reset token."""
    try:
        success = auth_service.reset_password(
            token=payload.token,
            new_password=payload.new_password,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The password reset link is invalid, has expired, or was already used.",
        )

    return {
        "status": "success",
        "message": "Password has been reset successfully. Please sign in with your new password.",
    }
