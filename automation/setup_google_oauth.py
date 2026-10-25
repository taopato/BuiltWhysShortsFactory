from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import secrets
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests


SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/drive.file",
)


def update_env(path: Path, values: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    found: set[str] = set()
    output: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
        if key in values:
            output.append(f"{key}={values[key]}")
            found.add(key)
        else:
            output.append(line)
    for key, value in values.items():
        if key not in found:
            output.append(f"{key}={value}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Authorize BuiltWhys YouTube Analytics/Upload and Drive.")
    parser.add_argument("--env-file", type=Path, default=Path(".env.automation"))
    parser.add_argument("--client-id")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    client_id = (args.client_id or input("Google OAuth Desktop Client ID: ")).strip()
    client_secret = getpass.getpass("Google OAuth Client Secret: ").strip()
    if not client_id or not client_secret:
        raise SystemExit("Client ID and secret are required.")

    state = secrets.token_urlsafe(24)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")
    result: dict[str, str] = {}

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result["code"] = (query.get("code") or [""])[0]
            result["state"] = (query.get("state") or [""])[0]
            body = b"BuiltWhys authorization completed. You can close this tab."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args) -> None:
            return

    server = HTTPServer(("127.0.0.1", args.port), Callback)
    redirect = f"http://127.0.0.1:{args.port}/callback"
    params = {
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code",
        "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent", "state": state,
        "code_challenge": code_challenge, "code_challenge_method": "S256",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    print("Opening Google authorization in your browser...")
    print(url)
    webbrowser.open(url)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    thread.join(timeout=300)
    server.server_close()
    if not result.get("code") or result.get("state") != state:
        raise SystemExit("Authorization was not completed or state verification failed.")
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={"code": result["code"], "client_id": client_id, "client_secret": client_secret,
              "redirect_uri": redirect, "grant_type": "authorization_code",
              "code_verifier": code_verifier}, timeout=30,
    )
    payload = response.json()
    if not response.ok or not payload.get("refresh_token"):
        detail = payload.get("error_description") or payload.get("error") or f"HTTP {response.status_code}"
        raise SystemExit("Google token exchange failed: " + str(detail))
    granted = set(str(payload.get("scope", "")).split())
    missing = set(SCOPES) - granted
    if missing:
        raise SystemExit("Required Google permissions were not granted: " + ", ".join(sorted(missing)))
    update_env(args.env_file, {
        "GOOGLE_CLIENT_ID": client_id,
        "GOOGLE_CLIENT_SECRET": client_secret,
        "GOOGLE_REFRESH_TOKEN": str(payload["refresh_token"]),
    })
    print(f"Google OAuth values were written to {args.env_file}. Keep this file private.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
