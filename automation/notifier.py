from __future__ import annotations

import os
import urllib.parse
import urllib.request


def notify(message: str, level: str = "info", job_id: str = "") -> bool:
    """Send alert-only Telegram notifications with a Control Center deep link."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False
    prefix = {"error": "[ERROR]", "warning": "[WARNING]", "success": "[OK]"}.get(level, "[INFO]")
    control_url = os.environ.get("CONTROL_CENTER_PUBLIC_URL", "").rstrip("/")
    link = f"\n\n{control_url}/?video={job_id}" if control_url and job_id else (
        f"\n\n{control_url}" if control_url else ""
    )
    body = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": f"{prefix} {message}{link}",
        "disable_web_page_preview": "true",
    }).encode()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body),
            timeout=30,
        ):
            return True
    except Exception:
        return False
