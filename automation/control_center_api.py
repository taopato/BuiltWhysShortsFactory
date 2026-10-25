from __future__ import annotations

import os
import base64
import hashlib
import hmac
import json
import secrets
import shutil
import sqlite3
import subprocess
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlencode

import requests
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:  # Package import (uvicorn automation.control_center_api:app)
    from automation.control_center_store import ControlCenterStore, DEFAULT_PLATFORMS
    from automation.review_queue import DEFAULT_DB, QueueError
    from automation.candidate_planner import load_catalog
except ImportError:  # Direct script/import from the automation directory
    from control_center_store import ControlCenterStore, DEFAULT_PLATFORMS
    from review_queue import DEFAULT_DB, QueueError
    from candidate_planner import load_catalog


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "automation" / "control_center_static"
DB_PATH = Path(os.environ.get("CONTROL_CENTER_DB", str(DEFAULT_DB)))
security = HTTPBasic(auto_error=False)

app = FastAPI(title="BuiltWhys Control Center", version="1.0.0", docs_url=None, redoc_url=None)
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


SESSION_COOKIE = "builtwhys_session"
OAUTH_STATE_COOKIE = "builtwhys_oauth_state"


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _session_secret() -> str:
    value = os.environ.get("CONTROL_CENTER_SESSION_SECRET", "")
    if len(value) < 32:
        raise HTTPException(status_code=503, detail="Control Center session secret is not configured")
    return value


def _sign(values: dict[str, Any]) -> str:
    body = _b64encode(json.dumps(values, separators=(",", ":"), sort_keys=True).encode())
    signature = hmac.new(_session_secret().encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64encode(signature)}"


def _verify(value: str, kind: str) -> dict[str, Any] | None:
    try:
        body, supplied = value.split(".", 1)
        expected = hmac.new(_session_secret().encode(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(supplied)):
            return None
        payload = json.loads(_b64decode(body))
        if payload.get("kind") != kind or int(payload.get("exp", 0)) < int(datetime.now().timestamp()):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _current_user(request: Request) -> str | None:
    session = request.cookies.get(SESSION_COOKIE, "")
    payload = _verify(session, "session") if session else None
    return str(payload["email"]) if payload and payload.get("email") else None


def _password_matches(password: str) -> bool:
    encoded = os.environ.get("CONTROL_CENTER_PASSWORD_HASH", "")
    try:
        scheme, iterations, salt_hex, expected_hex = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations), dklen=32,
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected_hex))
    except (ValueError, TypeError):
        return False


def authenticate(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
) -> str:
    user = _current_user(request)
    if user:
        return user
    if os.environ.get("CONTROL_CENTER_AUTH_MODE", "google").lower() != "basic":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    expected_user = os.environ.get("CONTROL_CENTER_USER", "builtwhys")
    if not os.environ.get("CONTROL_CENTER_PASSWORD_HASH", ""):
        raise HTTPException(status_code=503, detail="Control Center password is not configured")
    if not credentials or not (
        secrets.compare_digest(credentials.username.encode(), expected_user.encode())
        and _password_matches(credentials.password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": 'Basic realm="BuiltWhys Control Center"'},
        )
    return credentials.username


@contextmanager
def store() -> Iterator[ControlCenterStore]:
    instance = ControlCenterStore(DB_PATH)
    try:
        yield instance
    finally:
        instance.close()


def handle_queue_error(exc: QueueError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


def safe_media(path_value: str) -> Path:
    path = Path(path_value).resolve()
    allowed = (ROOT / "storage").resolve(), (ROOT / "automation" / "pilots").resolve()
    if not path.is_file() or not any(path == base or base in path.parents for base in allowed):
        raise HTTPException(status_code=404, detail="Media not found")
    return path


class JobPatch(BaseModel):
    title: str | None = None
    topic: str | None = None
    script: str | None = None
    description: str | None = None
    hashtags: str | None = None
    language: str | None = None
    platforms: str | None = None
    quality_score: int | None = Field(None, ge=0, le=100)
    is_reserve: bool | None = None
    youtube_privacy: str | None = None
    channel_key: str | None = None


class JobCreate(BaseModel):
    topic: str = Field(min_length=3, max_length=240)
    title: str = Field("", max_length=100)
    language: str = "en-US"
    channel_key: str = "builtwhys"


class ActionRequest(BaseModel):
    action: str
    note: str = ""
    revision_type: str = "visuals"
    human_confirmed: bool = False


class ScheduleRequest(BaseModel):
    job_id: str
    scheduled_at: str
    platforms: str = DEFAULT_PLATFORMS


class SlotRequest(BaseModel):
    weekday: int = Field(ge=0, le=6)
    local_time: str
    platforms: str = DEFAULT_PLATFORMS


class SettingPatch(BaseModel):
    values: dict[str, str]


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    try:
        with store() as data:
            data.heartbeat("control-center-api")
        return {"status": "ok", "database": "ok"}
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"database: {exc}") from exc


def _public_page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · BuiltWhys</title>
<style>body{{margin:0;background:#0a0c10;color:#f4f4f5;font:16px/1.65 system-ui}}main{{max-width:800px;margin:auto;padding:48px 24px}}
a{{color:#75b8ff}}nav{{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:42px}}h1,h2{{line-height:1.2}}h2{{margin-top:32px}}
.muted{{color:#a9b0bb}}.card{{padding:24px;border:1px solid #30343b;border-radius:16px;background:#14171c}}</style></head>
<body><main><nav><a href="/about">About</a><a href="/privacy">Privacy</a><a href="/terms">Terms</a>
<a href="/data-deletion">Data deletion</a></nav>{body}<p class="muted">Last updated: July 16, 2026 · Contact:
<a href="mailto:ttarikcetinturk@gmail.com">ttarikcetinturk@gmail.com</a></p></main></body></html>""")


@app.get("/about", response_class=HTMLResponse)
def about_page() -> HTMLResponse:
    return _public_page("About", """<h1>BuiltWhys Publisher</h1><div class="card"><p>BuiltWhys creates original,
short educational videos about why engineered objects are designed the way they are. BuiltWhys Publisher is a
private, owner-operated workflow for reviewing, scheduling, publishing and measuring those videos.</p><p>No third
party can create an account or use this application.</p><p><strong>Human approval is mandatory:</strong> every video
must pass source, asset-license, originality and duplicate checks, and the owner must watch and approve it before it
can be scheduled.</p></div><h2>Connected publishing services</h2><p>The application uses YouTube API Services to upload
owner-approved videos to the <a href="https://www.youtube.com/channel/UC_owbRSmCX1dtpXXN5VX3MQ">BuiltWhys channel</a>
and retrieve owner-authorized performance data. It also supports owner-authorized Meta publishing and Google Drive
archives.</p><p><a href="https://www.youtube.com/channel/UC_owbRSmCX1dtpXXN5VX3MQ"><img
src="/assets/developed-with-youtube.png" alt="Developed with YouTube" style="width:170px;max-width:100%"></a></p>""")


@app.get("/privacy", response_class=HTMLResponse)
def privacy_page() -> HTMLResponse:
    return _public_page("Privacy Policy", """<h1>Privacy Policy</h1><p>This policy describes the private BuiltWhys
Publisher application and its use of Google and YouTube API Services.</p><h2>Data we access</h2><p>With the owner's
explicit OAuth consent, the application accesses the connected YouTube channel identifier, uploaded video identifiers,
video metadata, upload status and channel/video analytics. It also creates BuiltWhys archive files in Google Drive.
The application does not request the owner's Google password.</p><h2>How data is used</h2><p>Data is used only to
upload owner-approved BuiltWhys videos, prevent duplicate publication, display performance reports and archive the
owner's publication packages. Data is not sold, rented or used for advertising.</p><h2>Storage and sharing</h2><p>OAuth
credentials and publication records are stored on a private server with restricted access. They are not exposed to
website visitors. Data is shared only with Google/YouTube and the publishing platforms selected by the owner to perform
the requested operation.</p><h2>Retention and control</h2><p>Records are retained while the owner uses the service or
until deletion is requested. The owner may revoke Google access at any time from
<a href="https://security.google.com/settings/security/permissions">Google security settings</a> and may request deletion using the
instructions on the <a href="/data-deletion">data deletion page</a>.</p><h2>Google and YouTube</h2><p>Use of YouTube
features is also governed by the <a href="https://www.youtube.com/t/terms">YouTube Terms of Service</a> and
<a href="https://policies.google.com/privacy">Google Privacy Policy</a>.</p>""")


@app.get("/terms", response_class=HTMLResponse)
def terms_page() -> HTMLResponse:
    return _public_page("Terms of Use", """<h1>Terms of Use</h1><p>BuiltWhys Publisher is a private tool available
only to the BuiltWhys owner. The owner remains responsible for reviewing factual accuracy, media licenses, platform
rules and publication choices before enabling a release.</p><p>The application may use YouTube API Services, Google
Drive and Meta publishing services only after explicit authorization. Access may be revoked at any time. The service
is provided without a guarantee of uninterrupted availability or specific audience, revenue or monetization results.</p>
<p>By using the YouTube functionality in this application, the owner agrees to be bound by the
<a href="https://www.youtube.com/t/terms">YouTube Terms of Service</a>.</p>""")


@app.get("/data-deletion", response_class=HTMLResponse)
def data_deletion_page() -> HTMLResponse:
    return _public_page("Data Deletion", """<h1>Data deletion and revocation</h1><ol><li>Revoke BuiltWhys Publisher
from <a href="https://security.google.com/settings/security/permissions">Google security settings</a> to stop future API access.</li>
<li>Email <a href="mailto:ttarikcetinturk@gmail.com">ttarikcetinturk@gmail.com</a> with the subject
<strong>BuiltWhys data deletion</strong>.</li><li>Stored OAuth credentials, API-derived channel records and associated
archives will be removed from the private application within seven days, except records that must be retained for
security or legal obligations.</li></ol><p>Deleting local application records does not automatically delete videos or
files already published to YouTube, Meta or Google Drive; those can be deleted directly from the respective account.</p>""")


@app.get("/login", response_class=HTMLResponse)
def login(request: Request) -> Any:
    if _current_user(request):
        return RedirectResponse("/", status_code=302)
    auth_mode = os.environ.get("CONTROL_CENTER_AUTH_MODE", "google").lower()
    allowed = os.environ.get("CONTROL_CENTER_ALLOWED_EMAIL", "")
    login_values = (allowed, os.environ.get("CONTROL_CENTER_GOOGLE_CLIENT_ID", ""),
                    os.environ.get("CONTROL_CENTER_GOOGLE_CLIENT_SECRET", ""))
    configured = all(login_values) and not any(value.startswith("PENDING_") for value in login_values)
    if auth_mode == "basic":
        action = '''<form method="post" action="/auth/login">
        <input type="email" name="email" autocomplete="username" placeholder="E-posta" required>
        <input type="password" name="password" autocomplete="current-password" placeholder="Şifre" required>
        <label style="display:flex;gap:8px;text-align:left;margin-top:14px;font-size:13px;color:#a9b0bb">
        <input type="checkbox" required style="width:auto;margin:2px 0 0">I agree to the <a href="/terms">Terms</a>
        and <a href="/privacy">Privacy Policy</a>.</label>
        <button class="button" type="submit">Giriş yap</button></form>'''
    else:
        action = '<a class="button" href="/auth/google">Google ile giriş yap</a>' if configured else (
            '<p class="error">Google giriş ayarları henüz tamamlanmadı.</p>'
        )
    return HTMLResponse(f"""<!doctype html><html lang=\"tr\"><head><meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>BuiltWhys Giriş</title>
<style>body{{margin:0;background:#0a0c10;color:#f4f4f5;font:16px system-ui;display:grid;place-items:center;min-height:100vh}}
.card{{width:min(420px,85vw);padding:36px;border:1px solid #30343b;border-radius:20px;background:#14171c;text-align:center}}
.brand{{font-size:32px;font-weight:800}}p{{color:#a9b0bb;line-height:1.55}}input{{box-sizing:border-box;width:100%;margin-top:12px;
padding:14px;border:1px solid #30343b;border-radius:12px;background:#0a0c10;color:#fff}}.button{{box-sizing:border-box;width:100%;display:block;
margin-top:20px;padding:14px;border:0;border-radius:12px;background:#fff;color:#111;text-decoration:none;font-weight:700;cursor:pointer}}.error{{color:#ff8b8b}}</style></head>
<body><main class=\"card\"><div class=\"brand\">BW</div><h1>Control Center</h1>
<p>Bu panel yalnızca BuiltWhys yöneticisine açıktır.</p>{action}</main></body></html>""")


@app.post("/auth/login")
def basic_login(email: str = Form(...), password: str = Form(...)) -> RedirectResponse:
    if os.environ.get("CONTROL_CENTER_AUTH_MODE", "google").lower() != "basic":
        raise HTTPException(status_code=404, detail="Not found")
    expected_user = os.environ.get("CONTROL_CENTER_USER", "").strip().lower()
    supplied_user = email.strip().lower()
    if not expected_user or not (
        secrets.compare_digest(supplied_user.encode(), expected_user.encode())
        and _password_matches(password)
    ):
        return RedirectResponse("/login?error=1", status_code=303)
    session = _sign({"kind": "session", "email": supplied_user,
                     "exp": int((datetime.now() + timedelta(days=7)).timestamp())})
    public_url = os.environ.get("CONTROL_CENTER_PUBLIC_URL", "")
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(SESSION_COOKIE, session, max_age=7 * 86400, httponly=True,
                        secure=public_url.startswith("https://"), samesite="strict")
    return response


@app.get("/auth/google")
def google_auth() -> RedirectResponse:
    client_id = os.environ.get("CONTROL_CENTER_GOOGLE_CLIENT_ID", "")
    public_url = os.environ.get("CONTROL_CENTER_PUBLIC_URL", "").rstrip("/")
    if not client_id or not public_url:
        raise HTTPException(status_code=503, detail="Google login is not configured")
    nonce = secrets.token_urlsafe(32)
    state = _sign({"kind": "oauth_state", "nonce": nonce,
                   "exp": int((datetime.now() + timedelta(minutes=10)).timestamp())})
    query = urlencode({"client_id": client_id, "redirect_uri": f"{public_url}/auth/callback",
                       "response_type": "code", "scope": "openid email profile",
                       "state": nonce, "prompt": "select_account"})
    response = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}", status_code=302)
    response.set_cookie(OAUTH_STATE_COOKIE, state, max_age=600, httponly=True,
                        secure=public_url.startswith("https://"), samesite="lax")
    return response


@app.get("/auth/callback")
def google_callback(request: Request, code: str = "", state: str = "") -> RedirectResponse:
    saved = _verify(request.cookies.get(OAUTH_STATE_COOKIE, ""), "oauth_state")
    if not code or not saved or not secrets.compare_digest(str(saved.get("nonce", "")), state):
        raise HTTPException(status_code=400, detail="Invalid or expired Google login request")
    public_url = os.environ.get("CONTROL_CENTER_PUBLIC_URL", "").rstrip("/")
    try:
        token_response = requests.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": os.environ.get("CONTROL_CENTER_GOOGLE_CLIENT_ID", ""),
            "client_secret": os.environ.get("CONTROL_CENTER_GOOGLE_CLIENT_SECRET", ""),
            "redirect_uri": f"{public_url}/auth/callback", "grant_type": "authorization_code",
        }, timeout=20)
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]
        user_response = requests.get("https://openidconnect.googleapis.com/v1/userinfo",
                                     headers={"Authorization": f"Bearer {access_token}"}, timeout=20)
        user_response.raise_for_status()
        profile = user_response.json()
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Google account verification failed") from exc
    email = str(profile.get("email", "")).lower()
    allowed = os.environ.get("CONTROL_CENTER_ALLOWED_EMAIL", "").strip().lower()
    if not profile.get("email_verified") or not allowed or not secrets.compare_digest(email, allowed):
        raise HTTPException(status_code=403, detail="This Google account is not authorized")
    session = _sign({"kind": "session", "email": email,
                     "exp": int((datetime.now() + timedelta(days=7)).timestamp())})
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(SESSION_COOKIE, session, max_age=7 * 86400, httponly=True,
                        secure=public_url.startswith("https://"), samesite="lax")
    response.delete_cookie(OAUTH_STATE_COOKIE)
    return response


@app.get("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/", response_class=HTMLResponse)
def index(request: Request, credentials: HTTPBasicCredentials | None = Depends(security)) -> Any:
    if not _current_user(request):
        return RedirectResponse("/login", status_code=302)
    return FileResponse(STATIC / "index.html")


@app.get("/api/me", dependencies=[Depends(authenticate)])
def current_user(request: Request) -> dict[str, str]:
    return {"email": _current_user(request) or os.environ.get("CONTROL_CENTER_USER", "builtwhys")}


@app.get("/api/dashboard", dependencies=[Depends(authenticate)])
def dashboard() -> dict[str, Any]:
    with store() as data:
        data.ensure_schedule_horizon()
        if data.setting("auto_fill_schedule", "true") == "true":
            data.auto_assign()
        result = data.dashboard()
    usage = shutil.disk_usage(ROOT)
    result["host"] = {
        "disk_total": usage.total,
        "disk_used": usage.used,
        "disk_free": usage.free,
        "disk_percent": round(usage.used * 100 / usage.total, 1),
        "server_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return result


@app.get("/api/jobs", dependencies=[Depends(authenticate)])
def jobs(status_filter: str = Query("", alias="status"), q: str = "",
         language: str = "", channel_key: str = "", view: str = "pending") -> list[dict[str, Any]]:
    if view not in {"pending", "pool", "rejected", "published", "all"}:
        raise HTTPException(status_code=400, detail="unsupported video pool view")
    with store() as data:
        return data.jobs(status_filter, q, language, channel_key, view)


@app.get("/api/factory", dependencies=[Depends(authenticate)])
def factory() -> dict[str, Any]:
    catalog = load_catalog()
    with store() as data:
        channels = []
        for key, config in catalog.items():
            rows = data.connection.execute(
                "SELECT status,COUNT(*) count FROM jobs WHERE channel_key=? GROUP BY status", (key,),
            ).fetchall()
            counts = {row["status"]: int(row["count"]) for row in rows}
            qualified = data.connection.execute(
                "SELECT COUNT(*) count FROM jobs WHERE channel_key=? AND candidate_score>=75", (key,),
            ).fetchone()["count"]
            channels.append({
                "key": key, "name": config["name"], "counts": counts,
                "qualified_candidates": int(qualified),
                "active": bool(config.get("active", False)),
                "reserve_target": int(config.get("reserve_target", 10)),
                "weekly_publish_target": int(config.get("weekly_publish_target", 5)),
            })
        return {"channels": channels, "publishing_requires_human_review": True}


@app.post("/api/jobs", dependencies=[Depends(authenticate)])
def create_job(request: JobCreate) -> dict[str, Any]:
    if request.language not in {"en-US", "tr-TR"}:
        raise HTTPException(status_code=400, detail="unsupported language")
    if request.channel_key not in {"builtwhys", "visualwhys", "wildwhys", "worldwhys"}:
        raise HTTPException(status_code=400, detail="unsupported channel")
    with store() as data:
        created = data.queue.create_job(request.topic, request.title)
        data.update_job(created["id"], {
            "language": request.language, "story_id": created["id"],
            "channel_key": request.channel_key,
        })
        data.event("info", "candidate_created", f"Manual candidate created: {request.topic}", created["id"])
        return data.job(created["id"])


@app.get("/api/jobs/{job_id}", dependencies=[Depends(authenticate)])
def job(job_id: str) -> dict[str, Any]:
    try:
        with store() as data:
            return data.job(job_id)
    except QueueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch("/api/jobs/{job_id}", dependencies=[Depends(authenticate)])
def patch_job(job_id: str, patch: JobPatch) -> dict[str, Any]:
    try:
        values = patch.model_dump(exclude_none=True)
        with store() as data:
            result = data.update_job(job_id, values)
            data.event("info", "job_updated", "Video metadata updated", job_id, fields=list(values))
            return result
    except QueueError as exc:
        raise handle_queue_error(exc) from exc


@app.post("/api/jobs/{job_id}/action", dependencies=[Depends(authenticate)])
def job_action(job_id: str, request: ActionRequest) -> dict[str, Any]:
    try:
        with store() as data:
            if request.action == "approve":
                return data.approve(job_id, request.note or "Control Center human approval",
                                    request.human_confirmed)
            if request.action == "reject":
                return data.reject(job_id, request.note or "Rejected in Control Center")
            if request.action == "revision":
                return data.request_revision(job_id, request.revision_type, request.note)
            if request.action == "localize_tr":
                return data.create_localization(job_id, "tr-TR")
            if request.action == "reject_family":
                return data.reject_family(job_id, request.note or "Content family rejected in Control Center")
            if request.action == "reserve":
                job_data = data.queue.get_job(job_id)
                if job_data["status"] != "approved":
                    raise QueueError("only approved videos can enter reserve")
                result = data.update_job(job_id, {"is_reserve": True})
                data.event("info", "reserve", "Video added to reserve", job_id)
                return result
            if request.action == "unreserve":
                return data.update_job(job_id, {"is_reserve": False})
            if request.action == "publish_now":
                job_data = data.queue.get_job(job_id)
                if job_data["status"] != "approved" or not job_data.get("human_reviewed"):
                    raise QueueError("only a human-approved video can be queued for immediate publishing")
                now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                existing = data.connection.execute(
                    "SELECT id FROM schedule_entries WHERE job_id=? AND status='planned' ORDER BY scheduled_at LIMIT 1",
                    (job_id,),
                ).fetchone()
                if existing:
                    data.connection.execute(
                        "UPDATE schedule_entries SET scheduled_at=?,source='manual',note='Explicit publish-now consent',updated_at=? WHERE id=?",
                        (now, now, existing["id"]),
                    )
                    data.connection.commit()
                else:
                    data.schedule(job_id, now, job_data.get("platforms", DEFAULT_PLATFORMS), "manual")
                data.event("info", "publish_now_queued", "Human-approved video queued for immediate publishing", job_id)
                return data.job(job_id)
            if request.action == "retry_publish":
                job_data = data.queue.get_job(job_id)
                if job_data["status"] != "failed":
                    raise QueueError("only failed publications can be retried")
                data.queue._transition(job_id, "pending_review")
                data.queue.decide(job_id, "approved", "Publication retry approved in Control Center")
                data.connection.execute(
                    "UPDATE schedule_entries SET status='planned',note='',updated_at=? WHERE job_id=? AND status='failed'",
                    (datetime.now(timezone.utc).isoformat(timespec="seconds"), job_id),
                )
                data.connection.commit()
                data.event("info", "publication_retry", "Publication retry queued", job_id)
                return data.job(job_id)
            raise QueueError("unsupported action")
    except QueueError as exc:
        raise handle_queue_error(exc) from exc


@app.get("/api/jobs/{job_id}/video", dependencies=[Depends(authenticate)])
def video(job_id: str) -> FileResponse:
    with store() as data:
        try:
            path = safe_media(data.queue.get_job(job_id)["video_path"])
        except QueueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type="video/mp4", filename=path.name, content_disposition_type="inline")


@app.get("/api/jobs/{job_id}/thumbnail", dependencies=[Depends(authenticate)])
def thumbnail(job_id: str) -> FileResponse:
    with store() as data:
        item = data.queue.get_job(job_id)
        path_value = item.get("thumbnail_path")
        if not path_value:
            video_path = safe_media(item.get("video_path", ""))
            thumbnail_dir = ROOT / "storage" / "control_thumbnails"
            thumbnail_dir.mkdir(parents=True, exist_ok=True)
            generated = thumbnail_dir / f"{job_id}.jpg"
            if not generated.is_file():
                result = subprocess.run(
                    ["ffmpeg", "-y", "-ss", "00:00:00.450", "-i", str(video_path),
                     "-frames:v", "1", "-vf", "scale=540:-2", "-q:v", "3", str(generated)],
                    capture_output=True, text=True, timeout=45, check=False,
                )
                if result.returncode != 0 or not generated.is_file():
                    raise HTTPException(status_code=404, detail="Thumbnail could not be generated")
            data.update_job(job_id, {"thumbnail_path": str(generated.resolve())})
            path_value = str(generated)
        path = safe_media(path_value)
    return FileResponse(path)


@app.get("/api/schedule", dependencies=[Depends(authenticate)])
def schedule(days: int = Query(35, ge=1, le=180)) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    with store() as data:
        data.ensure_schedule_horizon(now)
        if data.setting("auto_fill_schedule", "true") == "true":
            data.auto_assign()
        return data.schedules(
            (now - timedelta(days=2)).isoformat(timespec="seconds"),
            (now + timedelta(days=days)).isoformat(timespec="seconds"),
        )


@app.post("/api/schedule", dependencies=[Depends(authenticate)])
def create_schedule(request: ScheduleRequest) -> dict[str, Any]:
    try:
        with store() as data:
            return data.schedule(request.job_id, request.scheduled_at, request.platforms)
    except QueueError as exc:
        raise handle_queue_error(exc) from exc


@app.delete("/api/schedule/{schedule_id}", dependencies=[Depends(authenticate)])
def delete_schedule(schedule_id: int) -> dict[str, bool]:
    try:
        with store() as data:
            data.unschedule(schedule_id)
        return {"deleted": True}
    except QueueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/slots", dependencies=[Depends(authenticate)])
def slots() -> list[dict[str, Any]]:
    with store() as data:
        return data.queue.list_weekly_slots()


@app.post("/api/slots", dependencies=[Depends(authenticate)])
def add_slot(request: SlotRequest) -> dict[str, bool]:
    try:
        with store() as data:
            data.queue.add_weekly_slot(request.weekday, request.local_time)
            data.connection.execute(
                "UPDATE weekly_slots SET platforms=? WHERE weekday=? AND local_time=?",
                (request.platforms, request.weekday, request.local_time),
            )
            data.connection.commit()
        return {"created": True}
    except QueueError as exc:
        raise handle_queue_error(exc) from exc


@app.delete("/api/slots/{weekday}/{local_time}", dependencies=[Depends(authenticate)])
def remove_slot(weekday: int, local_time: str) -> dict[str, bool]:
    with store() as data:
        data.queue.remove_weekly_slot(weekday, local_time)
    return {"deleted": True}


@app.get("/api/settings", dependencies=[Depends(authenticate)])
def settings() -> dict[str, str]:
    with store() as data:
        return data.settings()


@app.patch("/api/settings", dependencies=[Depends(authenticate)])
def patch_settings(patch: SettingPatch) -> dict[str, str]:
    allowed = {
        "timezone", "reserve_minimum", "reserve_target", "schedule_horizon_days",
        "auto_fill_schedule", "allow_unapproved_fallback", "publishing_enabled",
        "telegram_notifications", "max_publications_per_day",
        "localization_languages", "auto_localize_approved",
    }
    with store() as data:
        for key, value in patch.values.items():
            if key not in allowed:
                raise HTTPException(status_code=400, detail=f"unsupported setting: {key}")
            data.set_setting(key, str(value))
        return data.settings()


@app.get("/api/analytics", dependencies=[Depends(authenticate)])
def analytics() -> dict[str, Any]:
    with store() as data:
        by_platform = [dict(row) for row in data.connection.execute(
            """SELECT platform,SUM(views) views,SUM(likes) likes,SUM(comments) comments,
               SUM(shares) shares,SUM(saves) saves FROM analytics_snapshots a
               WHERE captured_at IN (SELECT MAX(captured_at) FROM analytics_snapshots GROUP BY job_id,platform)
               GROUP BY platform"""
        )]
        top_videos = [dict(row) for row in data.connection.execute(
            """SELECT j.id,j.title,j.topic,a.platform,SUM(a.views) views,SUM(a.likes) likes,
               SUM(a.comments) comments,SUM(a.shares) shares
               FROM analytics_snapshots a JOIN jobs j ON j.id=a.job_id
               WHERE a.captured_at IN (SELECT MAX(captured_at) FROM analytics_snapshots GROUP BY job_id,platform)
               GROUP BY j.id,a.platform ORDER BY views DESC LIMIT 20"""
        )]
        channels = [dict(row) for row in data.connection.execute(
            """SELECT c.platform,c.captured_at,c.views,c.followers,c.media_count
               FROM channel_analytics_snapshots c
               JOIN (SELECT platform,MAX(captured_at) captured_at
                     FROM channel_analytics_snapshots GROUP BY platform) latest
               ON latest.platform=c.platform AND latest.captured_at=c.captured_at
               ORDER BY c.platform"""
        )]
        publication_counts = {
            row["platform"]: dict(row) for row in data.connection.execute(
                """SELECT platform,COUNT(*) total,
                   SUM(CASE WHEN status='published' AND remote_id<>'' THEN 1 ELSE 0 END) linked
                   FROM publications GROUP BY platform"""
            )
        }
        for platform in ("youtube", "instagram", "facebook"):
            if not any(row["platform"] == platform for row in channels):
                channels.append({"platform": platform, "captured_at": "", "views": 0,
                                 "followers": 0, "media_count": 0})
        countries = [dict(row) for row in data.connection.execute(
            """SELECT platform,captured_at,period_days,country,views,watch_seconds,likes,comments,shares
               FROM geo_analytics_snapshots g
               WHERE captured_at=(SELECT MAX(captured_at) FROM geo_analytics_snapshots
                                  WHERE platform=g.platform)
               ORDER BY platform,views DESC LIMIT 100"""
        )]
        geo_availability = {
            "youtube": {
                "available": bool(countries),
                "note": "Son 90 gunun izleyici ulkeleri YouTube Analytics API'den gelir.",
            },
            "instagram": {
                "available": False,
                "note": "Instagram bu baglanti turunde video bazli izleyici ulkesi vermiyor; erisim ve etkilesim gosterilir.",
            },
            "facebook": {
                "available": False,
                "note": "Facebook bu baglanti turunde Reels izleyici ulkesini vermiyor; erisim ve etkilesim gosterilir.",
            },
        }
        return {"platforms": by_platform, "channels": channels,
                "publication_counts": publication_counts, "top_videos": top_videos,
                "countries": countries, "geo_availability": geo_availability}


@app.post("/api/analytics/refresh", dependencies=[Depends(authenticate)])
def refresh_analytics() -> dict[str, Any]:
    # Lazy import avoids coupling application startup to worker-only dependencies.
    try:
        from automation.analytics_worker import collect
    except ImportError:
        from analytics_worker import collect
    with store() as data:
        updated = collect(data)
        data.heartbeat("analytics-worker", detail=f"manual updated={updated}")
        return {"updated": updated}


@app.exception_handler(sqlite3.Error)
async def sqlite_error(_: Request, exc: sqlite3.Error) -> HTMLResponse:
    return HTMLResponse(str(exc), status_code=503)
