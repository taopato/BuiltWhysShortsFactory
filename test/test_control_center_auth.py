from __future__ import annotations

from datetime import datetime, timedelta
import hashlib

from fastapi.testclient import TestClient

from automation.control_center_api import SESSION_COOKIE, _sign, app


def configure(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_CENTER_AUTH_MODE", "google")
    monkeypatch.setenv("CONTROL_CENTER_SESSION_SECRET", "test-session-secret-that-is-longer-than-32-characters")
    monkeypatch.setenv("CONTROL_CENTER_ALLOWED_EMAIL", "owner@example.com")


def test_google_gate_redirects_anonymous_browser(monkeypatch) -> None:
    configure(monkeypatch)
    client = TestClient(app, follow_redirects=False)
    assert client.get("/").status_code == 302
    assert client.get("/").headers["location"] == "/login"
    assert client.get("/api/me").status_code == 401


def test_policy_pages_are_public(monkeypatch) -> None:
    configure(monkeypatch)
    client = TestClient(app, follow_redirects=False)
    for path in ("/about", "/privacy", "/terms", "/data-deletion"):
        assert client.get(path).status_code == 200


def test_signed_session_allows_only_stored_identity(monkeypatch) -> None:
    configure(monkeypatch)
    client = TestClient(app, follow_redirects=False)
    session = _sign({
        "kind": "session",
        "email": "owner@example.com",
        "exp": int((datetime.now() + timedelta(minutes=5)).timestamp()),
    })
    client.cookies.set(SESSION_COOKIE, session)
    response = client.get("/api/me")
    assert response.status_code == 200
    assert response.json() == {"email": "owner@example.com"}


def test_expired_session_is_rejected(monkeypatch) -> None:
    configure(monkeypatch)
    client = TestClient(app, follow_redirects=False)
    session = _sign({
        "kind": "session",
        "email": "owner@example.com",
        "exp": int((datetime.now() - timedelta(minutes=1)).timestamp()),
    })
    client.cookies.set(SESSION_COOKIE, session)
    assert client.get("/api/me").status_code == 401


def test_basic_form_login_creates_session(monkeypatch) -> None:
    salt = bytes.fromhex("00112233445566778899aabbccddeeff")
    digest = hashlib.pbkdf2_hmac("sha256", b"safe-test-password", salt, 310000, dklen=32)
    monkeypatch.setenv("CONTROL_CENTER_AUTH_MODE", "basic")
    monkeypatch.setenv("CONTROL_CENTER_SESSION_SECRET", "test-session-secret-that-is-longer-than-32-characters")
    monkeypatch.setenv("CONTROL_CENTER_USER", "owner@example.com")
    monkeypatch.setenv(
        "CONTROL_CENTER_PASSWORD_HASH",
        f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}",
    )
    monkeypatch.setenv("CONTROL_CENTER_PUBLIC_URL", "http://control.example.com")
    client = TestClient(app, follow_redirects=False)

    assert client.get("/").headers["location"] == "/login"
    response = client.post(
        "/auth/login", data={"email": "owner@example.com", "password": "safe-test-password"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert client.get("/api/me").json() == {"email": "owner@example.com"}


def test_basic_form_rejects_wrong_password(monkeypatch) -> None:
    salt = bytes.fromhex("00112233445566778899aabbccddeeff")
    digest = hashlib.pbkdf2_hmac("sha256", b"right-password", salt, 310000, dklen=32)
    monkeypatch.setenv("CONTROL_CENTER_AUTH_MODE", "basic")
    monkeypatch.setenv("CONTROL_CENTER_SESSION_SECRET", "test-session-secret-that-is-longer-than-32-characters")
    monkeypatch.setenv("CONTROL_CENTER_USER", "owner@example.com")
    monkeypatch.setenv(
        "CONTROL_CENTER_PASSWORD_HASH",
        f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}",
    )
    client = TestClient(app, follow_redirects=False)
    response = client.post(
        "/auth/login", data={"email": "owner@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=1"
    assert client.get("/api/me").status_code == 401
