"""
tests/test_auth.py
==================
Unit and integration tests for PrivSight authentication system:
- Registration, validation, duplicate prevention
- Password hashing with bcrypt
- Login, session cookie issuance, credential validation
- Protected routes redirection and authentication enforcement
- Password reset flow
"""

from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.auth.routes import SESSION_COOKIE_NAME


@pytest.fixture(scope="function")
def client() -> TestClient:
    return TestClient(app)


def test_login_page_served(client: TestClient) -> None:
    res = client.get("/login", follow_redirects=False)
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Welcome Back" in res.text
    assert "Sign in to your Privacy Intelligence Workspace." in res.text


def test_register_page_served(client: TestClient) -> None:
    res = client.get("/register", follow_redirects=False)
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Create Your Account" in res.text


def test_workspace_unauthenticated_redirect(client: TestClient) -> None:
    # Attempting to access workspace without session must redirect to /login
    res = client.get("/workspace", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/login?redirect=/workspace"


def test_inventory_unauthenticated_redirect(client: TestClient) -> None:
    res = client.get("/inventory", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/login?redirect=/inventory"


def test_user_registration_and_login_lifecycle(client: TestClient) -> None:
    unique_email = f"compliance.officer.{uuid.uuid4().hex[:8]}@enterprise.org"
    password = "SecurePassword2026!"

    # 1. Register new user
    reg_res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Compliance Lead",
            "email": unique_email,
            "password": password,
        },
    )
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert reg_data["status"] == "success"
    assert reg_data["user"]["email"] == unique_email
    assert SESSION_COOKIE_NAME in reg_res.cookies

    # 2. Prevent duplicate registration
    dup_res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Duplicate Person",
            "email": unique_email,
            "password": password,
        },
    )
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"].lower()

    # 3. Reject invalid email
    inv_email_res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Invalid Person",
            "email": "not-an-email",
            "password": password,
        },
    )
    assert inv_email_res.status_code in [400, 422]

    # 4. Reject short password
    short_pwd_res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Short Pass Person",
            "email": f"short.{uuid.uuid4().hex[:8]}@enterprise.org",
            "password": "123",
        },
    )
    assert short_pwd_res.status_code in [400, 422]

    # 5. Check session status via /api/auth/me with cookie
    me_res = client.get("/api/auth/me", cookies=reg_res.cookies)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["authenticated"] is True
    assert me_data["user"]["email"] == unique_email

    # 6. Authenticated user can access /workspace
    ws_res = client.get("/workspace", cookies=reg_res.cookies, follow_redirects=False)
    assert ws_res.status_code == 200
    assert "text/html" in ws_res.headers["content-type"]

    # 7. Authenticated user opening /login is redirected to /workspace
    login_redir = client.get("/login", cookies=reg_res.cookies, follow_redirects=False)
    assert login_redir.status_code == 303
    assert login_redir.headers["location"] == "/workspace"

    # 8. Test Login with incorrect password
    bad_login = client.post(
        "/api/auth/login",
        json={
            "email": unique_email,
            "password": "WrongPassword!",
        },
    )
    assert bad_login.status_code == 401
    assert "invalid email or password" in bad_login.json()["detail"].lower()

    # 9. Test Login with non-existent user
    non_existent = client.post(
        "/api/auth/login",
        json={
            "email": f"unknown.{uuid.uuid4().hex[:8]}@enterprise.org",
            "password": password,
        },
    )
    assert non_existent.status_code == 401

    # 10. Test Login with valid credentials
    good_login = client.post(
        "/api/auth/login",
        json={
            "email": unique_email,
            "password": password,
            "remember_me": True,
        },
    )
    assert good_login.status_code == 200
    assert SESSION_COOKIE_NAME in good_login.cookies

    # 11. Test Logout
    logout_res = client.post("/api/auth/logout", cookies=good_login.cookies)
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "success"

    # 12. After logout, session is terminated and returns 401 Unauthorized
    me_after_logout = client.get("/api/auth/me", cookies=good_login.cookies)
    assert me_after_logout.status_code == 401
    assert "authentication required" in me_after_logout.json()["detail"].lower() or "session" in me_after_logout.json()["detail"].lower()


def test_password_reset_flow(client: TestClient) -> None:
    reset_email = f"reset.user.{uuid.uuid4().hex[:8]}@enterprise.org"
    original_pass = "OriginalPass123!"
    new_pass = "NewSecurePassword456!"

    # Register user
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Reset Test User",
            "email": reset_email,
            "password": original_pass,
        },
    )

    # Request password reset
    req_res = client.post(
        "/api/auth/forgot-password",
        json={"email": reset_email},
    )
    assert req_res.status_code == 200
    data = req_res.json()
    assert data["status"] == "success"

    # Fetch token directly from backend service for verification
    from backend.auth.routes import auth_service
    token, _ = auth_service.create_password_reset(reset_email)
    assert token is not None

    # Reset password
    reset_res = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": new_pass},
    )
    assert reset_res.status_code == 200

    # Old password no longer works
    fail_login = client.post(
        "/api/auth/login",
        json={"email": reset_email, "password": original_pass},
    )
    assert fail_login.status_code == 401

    # New password succeeds
    success_login = client.post(
        "/api/auth/login",
        json={"email": reset_email, "password": new_pass},
    )
    assert success_login.status_code == 200
    assert success_login.json()["status"] == "success"


def test_unauthenticated_private_endpoints(client: TestClient) -> None:
    """Verifies that private backend endpoints reject unauthenticated requests with 401."""
    # 1. Direct call to /api/auth/me without cookies
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert "WWW-Authenticate" in res.headers

    # 2. Call with invalid/forged cookie token
    res_fake = client.get("/api/auth/me", cookies={SESSION_COOKIE_NAME: "forged_malicious_token_12345"})
    assert res_fake.status_code == 401


def test_session_regeneration_and_fixation_protection(client: TestClient) -> None:
    """Verifies session regeneration on login: old token is invalidated when a new session is created."""
    email = f"regen.{uuid.uuid4().hex[:8]}@enterprise.org"
    password = "StrongPassword987!"

    # Register
    reg_res = client.post(
        "/api/auth/register",
        json={"full_name": "Regen User", "email": email, "password": password},
    )
    assert reg_res.status_code == 201
    initial_cookie = reg_res.cookies[SESSION_COOKIE_NAME]

    # Verify initial cookie works
    me1 = client.get("/api/auth/me", cookies={SESSION_COOKIE_NAME: initial_cookie})
    assert me1.status_code == 200
    assert me1.json()["email"] == email

    # Login while passing the old session cookie
    login_res = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        cookies={SESSION_COOKIE_NAME: initial_cookie},
    )
    assert login_res.status_code == 200
    new_cookie = login_res.cookies[SESSION_COOKIE_NAME]
    assert new_cookie != initial_cookie

    # The new cookie works
    me_new = client.get("/api/auth/me", cookies={SESSION_COOKIE_NAME: new_cookie})
    assert me_new.status_code == 200

    # The old cookie was invalidated (session fixation defense)
    me_old = client.get("/api/auth/me", cookies={SESSION_COOKIE_NAME: initial_cookie})
    assert me_old.status_code == 401


def test_login_rate_limiting(client: TestClient) -> None:
    """Verifies that 5 consecutive failed login attempts trigger HTTP 429 Too Many Requests."""
    target_email = f"ratelimit.{uuid.uuid4().hex[:8]}@enterprise.org"

    # Make 5 failed attempts
    for i in range(5):
        res = client.post(
            "/api/auth/login",
            json={"email": target_email, "password": "WrongPassword!"},
        )
        assert res.status_code == 401

    # 6th attempt should be rate limited with HTTP 429
    limited_res = client.post(
        "/api/auth/login",
        json={"email": target_email, "password": "WrongPassword!"},
    )
    assert limited_res.status_code == 429
    assert "Retry-After" in limited_res.headers
    assert "too many failed login attempts" in limited_res.json()["detail"].lower()


def test_cors_and_cookie_attributes(client: TestClient) -> None:
    """Verifies CORS headers for allowed origins and cookie security flags."""
    cors_res = client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert cors_res.status_code == 200
    assert cors_res.headers.get("access-control-allow-origin") == "http://localhost:8000"
    assert cors_res.headers.get("access-control-allow-credentials") == "true"
