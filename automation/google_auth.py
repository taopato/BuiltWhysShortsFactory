from __future__ import annotations

import os
import time
from typing import Any

import requests


class GoogleAuthError(RuntimeError):
    pass


_cache: dict[str, Any] = {}


def _suffix(profile: str) -> str:
    value = (profile or "en-US").strip().lower()
    return "" if value in {"en", "en-us", "default"} else "_" + value.split("-")[0].upper()


def access_token(profile: str = "en-US") -> str:
    now = time.time()
    suffix = _suffix(profile)
    cache_key = suffix or "_EN"
    cached = _cache.get(cache_key, {})
    if cached.get("token") and float(cached.get("expires", 0)) > now + 60:
        return str(cached["token"])
    client_id = os.environ.get(f"GOOGLE_CLIENT_ID{suffix}", "").strip()
    client_secret = os.environ.get(f"GOOGLE_CLIENT_SECRET{suffix}", "").strip()
    refresh_token = os.environ.get(f"GOOGLE_REFRESH_TOKEN{suffix}", "").strip()
    if not all((client_id, client_secret, refresh_token)):
        raise GoogleAuthError("Google OAuth credentials are missing")
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise GoogleAuthError(f"Google OAuth returned HTTP {response.status_code}") from exc
    if not response.ok or not payload.get("access_token"):
        raise GoogleAuthError(f"Google OAuth failed: {payload.get('error_description') or payload}")
    _cache[cache_key] = {"token": payload["access_token"], "expires": now + int(payload.get("expires_in", 3600))}
    return str(payload["access_token"])


def headers(profile: str = "en-US") -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token(profile)}"}
