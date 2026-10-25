from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)?", re.UNICODE)


def _probe(path_value: str) -> tuple[dict[str, Any], str]:
    path = Path(path_value)
    if not path.is_file():
        return {}, "Rendered video is missing"
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=45, check=False,
    )
    if result.returncode != 0:
        return {}, "Rendered video could not be inspected"
    try:
        return json.loads(result.stdout), ""
    except json.JSONDecodeError:
        return {}, "Rendered video metadata is invalid"


def assess_production(job: dict[str, Any]) -> dict[str, Any]:
    """Deterministic delivery checks; this is not a prediction of monetization."""
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    score = 100

    def check(name: str, passed: bool, detail: str, penalty: int, blocking: bool = True) -> None:
        nonlocal score
        checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            score -= penalty
            (blockers if blocking else warnings).append(detail)

    probe, probe_error = _probe(str(job.get("video_path") or ""))
    check("render_readable", not probe_error, probe_error or "Rendered video is readable", 40)
    video = next((item for item in probe.get("streams", []) if item.get("codec_type") == "video"), {})
    audio = next((item for item in probe.get("streams", []) if item.get("codec_type") == "audio"), {})
    width, height = int(video.get("width") or 0), int(video.get("height") or 0)
    duration = float((probe.get("format") or {}).get("duration") or 0)
    check("vertical_full_hd", width == 1080 and height == 1920,
          f"Output resolution is {width}x{height}; required 1080x1920", 25)
    check("short_duration", 30 <= duration <= 60,
          f"Duration is {duration:.1f}s; target is 30-60s", 18)
    visual_puzzle = str(job.get("channel_key") or "") == "visualwhys"
    check("audio_track", bool(audio),
          ("Sound-design audio track is present" if visual_puzzle else "Narration audio track is present")
          if audio else "Audio track is missing", 35)

    language = str(job.get("language") or "en-US")
    words = WORD_RE.findall(str(job.get("script") or ""))
    minimum, maximum = (20, 140) if visual_puzzle else ((65, 125) if language == "tr-TR" else (80, 140))
    check("script_length", minimum <= len(words) <= maximum,
          f"{'Storyboard' if visual_puzzle else 'Narration'} contains {len(words)} words; target is {minimum}-{maximum}", 18)
    first_sentence = re.split(r"[.!?]", str(job.get("script") or ""), maxsplit=1)[0]
    hook_words = len(WORD_RE.findall(first_sentence))
    check("concise_hook", 4 <= hook_words <= 24,
          f"Opening hook contains {hook_words} words; target is 4-24", 10, False)
    title_length = len(str(job.get("title") or "").strip())
    check("title_length", 15 <= title_length <= 72,
          f"Title contains {title_length} characters; target is 15-72", 10)
    description_length = len(str(job.get("description") or "").strip())
    check("description", description_length >= 80,
          f"Description contains {description_length} characters; minimum is 80", 8, False)
    hashtags = re.findall(r"#[\w-]+", str(job.get("hashtags") or ""), re.UNICODE)
    check("hashtags", 3 <= len(hashtags) <= 8,
          f"Metadata contains {len(hashtags)} hashtags; target is 3-8", 6, False)

    score = max(0, min(100, score))
    return {
        "status": "pass" if not blockers and score >= 75 else "blocked",
        "score": score, "checks": checks, "blockers": blockers, "warnings": warnings,
        "metrics": {"width": width, "height": height, "duration_seconds": round(duration, 2),
                    "script_words": len(words), "hook_words": hook_words},
        "disclaimer": "Technical/editorial delivery check; platform acceptance and monetization are not guaranteed.",
    }
