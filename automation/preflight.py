from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a BuiltWhys server before live deployment.")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env.automation")
    parser.add_argument("--online", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []
    if not args.env_file.is_file():
        print(f"FAIL missing {args.env_file}")
        return 2
    env = load_env(args.env_file)
    required = (
        "PEXELS_API_KEY", "CONTROL_CENTER_SESSION_SECRET", "CONTROL_CENTER_DOMAIN",
        "META_PAGE_ACCESS_TOKEN", "META_PAGE_ID", "META_IG_USER_ID",
    )
    auth_mode = env.get("CONTROL_CENTER_AUTH_MODE", "google").lower()
    if auth_mode == "basic":
        required += ("CONTROL_CENTER_USER", "CONTROL_CENTER_PASSWORD_HASH")
    else:
        required += ("CONTROL_CENTER_ALLOWED_EMAIL", "CONTROL_CENTER_GOOGLE_CLIENT_ID",
                     "CONTROL_CENTER_GOOGLE_CLIENT_SECRET")
    for key in required:
        value = env.get(key, "")
        if not value or value.startswith("PENDING_"):
            errors.append(f"{key} is missing")
    if len(env.get("CONTROL_CENTER_SESSION_SECRET", "")) < 32 or "CHANGE_" in env.get("CONTROL_CENTER_SESSION_SECRET", ""):
        errors.append("CONTROL_CENTER_SESSION_SECRET must be a long random value")
    if auth_mode not in ("google", "basic"):
        errors.append("CONTROL_CENTER_AUTH_MODE must be google or basic")
    if auth_mode == "basic" and not env.get("CONTROL_CENTER_PASSWORD_HASH", "").startswith("pbkdf2_sha256$"):
        errors.append("CONTROL_CENTER_PASSWORD_HASH must use PBKDF2-SHA256")
    if "example.com" in env.get("CONTROL_CENTER_DOMAIN", ""):
        errors.append("CONTROL_CENTER_DOMAIN is still a placeholder")
    google = all(env.get(key) for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"))
    if not google:
        warnings.append("Google OAuth is incomplete: YouTube publishing/analytics and Drive archive stay unavailable")
    if env.get("PUBLISH_ENABLED", "false").lower() == "true" and not google:
        errors.append("PUBLISH_ENABLED cannot be true before Google OAuth is complete")
    for path in (ROOT / "config.toml", ROOT / "Caddyfile.control-center", ROOT / "docker-compose.production.yml"):
        if not path.is_file():
            errors.append(f"required file missing: {path.name}")
    if shutil.disk_usage(ROOT).free < 20 * 1024**3:
        warnings.append("less than 20 GB disk space is free")
    try:
        result = subprocess.run(
            ["docker", "compose", "--env-file", str(args.env_file), "-f",
             str(ROOT / "docker-compose.production.yml"), "config", "--quiet"],
            cwd=ROOT, capture_output=True, text=True, timeout=60, check=False,
        )
        if result.returncode:
            errors.append("Docker Compose config: " + (result.stderr.strip() or result.stdout.strip()))
    except (OSError, subprocess.TimeoutExpired) as exc:
        errors.append(f"Docker Compose unavailable: {exc}")
    if args.online and not errors:
        try:
            response = requests.get("https://api.pexels.com/v1/collections?per_page=1",
                                    headers={"Authorization": env["PEXELS_API_KEY"]}, timeout=20)
            if not response.ok:
                errors.append(f"Pexels authentication returned HTTP {response.status_code}")
        except requests.RequestException as exc:
            errors.append(f"Pexels connection failed: {exc}")
        try:
            version = env.get("META_GRAPH_VERSION", "v25.0")
            response = requests.get(
                f"https://graph.facebook.com/{version}/{env['META_PAGE_ID']}",
                params={"fields": "id,name,instagram_business_account{id,username}",
                        "access_token": env["META_PAGE_ACCESS_TOKEN"]}, timeout=20,
            )
            if not response.ok:
                errors.append(f"Meta verification returned HTTP {response.status_code}")
        except requests.RequestException as exc:
            errors.append(f"Meta connection failed: {exc}")
        if google:
            try:
                token_response = requests.post(
                    "https://oauth2.googleapis.com/token",
                    data={"client_id": env["GOOGLE_CLIENT_ID"], "client_secret": env["GOOGLE_CLIENT_SECRET"],
                          "refresh_token": env["GOOGLE_REFRESH_TOKEN"], "grant_type": "refresh_token"},
                    timeout=20,
                )
                if not token_response.ok or not token_response.json().get("access_token"):
                    errors.append(f"Google OAuth verification returned HTTP {token_response.status_code}")
                else:
                    channel = requests.get(
                        "https://www.googleapis.com/youtube/v3/channels",
                        params={"part": "id,snippet", "mine": "true"},
                        headers={"Authorization": f"Bearer {token_response.json()['access_token']}"}, timeout=20,
                    )
                    if not channel.ok or not (channel.json().get("items") or []):
                        errors.append("Google OAuth is valid but no YouTube channel was returned")
            except (requests.RequestException, ValueError) as exc:
                errors.append(f"Google verification failed: {exc}")
    for item in warnings:
        print("WARN", item)
    for item in errors:
        print("FAIL", item)
    if errors:
        return 2
    print("PASS BuiltWhys preflight completed; live publishing flag:", env.get("PUBLISH_ENABLED", "false"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
