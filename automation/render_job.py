from __future__ import annotations

import argparse
import json
import os
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from brand_video import brand_video
from review_queue import ApprovalQueue, QueueError


ROOT_DIR = Path(__file__).resolve().parents[1]
API_BASE = os.environ.get("MONEYPRINTER_API_BASE", "http://127.0.0.1:8080/api/v1").rstrip("/")
MINIMUM_UNIQUE_SCENES = 7


def request_json(method: str, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise QueueError(f"MoneyPrinter API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise QueueError(f"MoneyPrinter API is unavailable: {exc}") from exc
    if int(result.get("status", 500)) != 200:
        raise QueueError(f"MoneyPrinter API rejected the request: {result}")
    return result


def stage_assets(assets_dir: Path, prefix: str) -> list[dict[str, Any]]:
    source_dir = assets_dir.resolve()
    if not source_dir.is_dir():
        raise QueueError(f"assets directory does not exist: {source_dir}")
    supported_suffixes = {".png", ".jpg", ".jpeg", ".mp4", ".mov", ".webm"}
    sources = sorted(
        path for path in source_dir.glob("scene-*")
        if path.is_file() and path.suffix.lower() in supported_suffixes
    )
    if len(sources) < MINIMUM_UNIQUE_SCENES:
        raise QueueError(
            f"at least {MINIMUM_UNIQUE_SCENES} unique scene image/video files are required "
            "to prevent visible repetition"
        )
    destination_dir = ROOT_DIR / "storage" / "local_videos"
    destination_dir.mkdir(parents=True, exist_ok=True)
    materials = []
    for index, source in enumerate(sources, start=1):
        destination_name = f"{prefix}-{index:02d}{source.suffix.lower()}"
        destination = destination_dir / destination_name
        shutil.copy2(source, destination)
        materials.append(
            {
                "provider": "local",
                # The API resolves local materials inside its allow-listed
                # storage/local_videos directory. Passing only the filename
                # works on both the Windows host and the Linux container.
                "url": destination_name,
                "duration": 0,
            }
        )
    return materials


def wait_for_task(task_id: str, timeout_seconds: int = 900) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = request_json("GET", f"{API_BASE}/tasks/{task_id}")
        task = result["data"]
        state = int(task.get("state", 0))
        print(f"render state={state} progress={task.get('progress')}%", flush=True)
        if state == 1:
            return task
        if state == -1:
            raise QueueError(
                f"render failed at {task.get('failed_stage')}: {task.get('error')}"
            )
        time.sleep(3)
    raise QueueError(f"render timed out after {timeout_seconds} seconds")


def locate_final_video(task_id: str) -> Path:
    task_dir = ROOT_DIR / "storage" / "tasks" / task_id
    candidates = sorted(task_dir.glob("final-*.mp4"))
    if not candidates:
        raise QueueError(f"MoneyPrinter completed without a final video in {task_dir}")
    return candidates[0].resolve()


def render(job_id: str, pilot_dir: Path, db_path: Path) -> dict[str, Any]:
    pilot = pilot_dir.resolve()
    script_path = pilot / "script.txt"
    manifest_path = next(
        (candidate for candidate in (pilot / "manifest-v3.json", pilot / "manifest-v2.json", pilot / "manifest.json") if candidate.is_file()),
        pilot / "manifest.json",
    )
    assets_dir = next(
        (candidate for candidate in (pilot / "assets-v3", pilot / "assets-v2", pilot / "assets") if candidate.is_dir()),
        pilot / "assets",
    )
    shot_plan_path = pilot / "shot_plan.json"
    cover_path = pilot / "cover.txt"
    if not script_path.is_file():
        raise QueueError(f"script not found: {script_path}")
    script = script_path.read_text(encoding="utf-8").strip()
    shot_plan = json.loads(shot_plan_path.read_text(encoding="utf-8")) if shot_plan_path.is_file() else {}
    cover_text = (
        cover_path.read_text(encoding="utf-8").strip()
        if cover_path.is_file()
        else str(shot_plan.get("cover_text") or "BUILT DIFFERENT")
    )
    revision_config_path = pilot / "revision_render_config.json"
    revision_config = (
        json.loads(revision_config_path.read_text(encoding="utf-8"))
        if revision_config_path.is_file() else {}
    )
    queue = ApprovalQueue(db_path)
    try:
        job = queue.get_job(job_id)
        queue.start_render(job_id)
        materials = stage_assets(assets_dir, f"job-{job_id}")
        language = str(job.get("language") or "en-US")
        voices = {
            "en-US": os.environ.get("VOICE_EN_US", "en-US-AndrewMultilingualNeural"),
            "tr-TR": os.environ.get("VOICE_TR_TR", "tr-TR-AhmetNeural"),
        }
        body = {
            "video_subject": job["topic"],
            "video_script": script,
            "video_terms": [job["topic"], "engineering design"],
            "video_aspect": "9:16",
            "video_concat_mode": "sequential",
            # Stock clips already contain camera movement. A global ZoomIn made every
            # scene feel identical and also needlessly resampled real footage.
            "video_transition_mode": None,
            "video_clip_duration": 5,
            "video_clip_speed": 1.0,
            "match_materials_to_script": True,
            "video_count": 1,
            "video_source": "local",
            "video_materials": materials,
            "video_language": language,
            "voice_name": str(revision_config.get("voice_name") or voices.get(language, voices["en-US"])),
            "voice_volume": max(0.75, min(1.25, float(revision_config.get("voice_volume", 1.0)))),
            "voice_rate": max(0.85, min(1.20, float(revision_config.get("voice_rate", 1.05)))),
            "bgm_type": "",
            "bgm_file": "",
            "bgm_volume": 0.0,
            "subtitle_enabled": True,
            "subtitle_position": "custom",
            "custom_position": max(52.0, min(82.0, float(revision_config.get("custom_position", 68.0)))),
            "font_name": "BeVietnamPro-Bold.ttf",
            "text_fore_color": "#FFFFFF",
            "text_background_color": "#00000080",
            "rounded_subtitle_background": True,
            "font_size": max(46, min(70, int(revision_config.get("font_size", 58)))),
            "stroke_color": "#000000",
            "stroke_width": 2.0,
            "n_threads": 4,
            "paragraph_number": 1,
        }
        response = request_json("POST", f"{API_BASE}/videos", body)
        task_id = response["data"]["task_id"]
        print(f"MoneyPrinter task: {task_id}", flush=True)
        wait_for_task(task_id)
        video_path = locate_final_video(task_id)
        brand_video(video_path, cover_text=cover_text)
        attached = queue.attach_render(job_id, video_path, manifest_path)
        # The API staging copies are no longer needed after the completed task;
        # originals remain in the pilot and the final master remains in tasks.
        staging = ROOT_DIR / "storage" / "local_videos"
        for material in materials:
            (staging / str(material["url"])).unlink(missing_ok=True)
        return attached
    except Exception as exc:
        try:
            current = queue.get_job(job_id)
            if current["status"] == "rendering":
                queue.mark_failed(job_id, str(exc))
        finally:
            if isinstance(exc, QueueError):
                raise
            raise QueueError(str(exc)) from exc
    finally:
        queue.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a queued Short with MoneyPrinterTurbo")
    parser.add_argument("job_id")
    parser.add_argument("--pilot-dir", type=Path, required=True)
    parser.add_argument(
        "--db", type=Path, default=ROOT_DIR / "storage" / "approval_queue.sqlite3"
    )
    args = parser.parse_args()
    try:
        result = render(args.job_id, args.pilot_dir, args.db)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except QueueError as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
