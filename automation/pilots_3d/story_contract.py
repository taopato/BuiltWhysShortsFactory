"""Fail-closed editorial contract for server-rendered 3D Shorts pilots.

This module is deliberately separate from the current stock-video producer.
Passing this contract is necessary, not sufficient, for publication: a human
still has to inspect the final video and the existing policy gates still apply.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ALLOWED_TEMPLATES = {"pin_tumbler_lock", "seatbelt_retractor", "room_thermostat"}
REQUIRED_BEAT_FIELDS = {"start", "end", "narration", "visible_action", "objects"}


def validate_story(story: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if story.get("template") not in ALLOWED_TEMPLATES:
        errors.append("unsupported 3D template")
    if story.get("language") != "en-US":
        errors.append("pilot language must be en-US")
    if not isinstance(story.get("fact_sources"), list) or not story["fact_sources"]:
        errors.append("at least one fact source is required")
    else:
        for source in story["fact_sources"]:
            if not isinstance(source, dict) or not all(source.get(k) for k in ("claim", "url")):
                errors.append("each fact source needs a claim and URL")
                break
            if not str(source["url"]).startswith("https://"):
                errors.append("fact source URL must use HTTPS")
                break
    beats = story.get("beats")
    if not isinstance(beats, list) or len(beats) < 7:
        return errors + ["a story needs at least seven visual beats"]
    previous_end = 0.0
    actions = set()
    for index, beat in enumerate(beats):
        if not isinstance(beat, dict) or not REQUIRED_BEAT_FIELDS.issubset(beat):
            errors.append(f"beat {index + 1} is incomplete")
            continue
        try:
            start, end = float(beat["start"]), float(beat["end"])
        except (TypeError, ValueError):
            errors.append(f"beat {index + 1} has invalid timing")
            continue
        if abs(start - previous_end) > 0.05 or end <= start or end - start > 5.0:
            errors.append(f"beat {index + 1} has a gap, overlap, or lasts over five seconds")
        previous_end = end
        if not str(beat["narration"]).strip() or not str(beat["visible_action"]).strip():
            errors.append(f"beat {index + 1} needs narration and a visible action")
        if len(str(beat["narration"]).split()) > (end - start) * 3.8:
            errors.append(f"beat {index + 1} narration is too fast for its visual")
        if not isinstance(beat["objects"], list) or not beat["objects"]:
            errors.append(f"beat {index + 1} needs named on-screen objects")
        actions.add(str(beat["visible_action"]).strip().lower())
    if previous_end < 26 or previous_end > 40:
        errors.append("pilot duration must be 26–40 seconds")
    if len(actions) < 5:
        errors.append("too few distinct visual actions")
    if beats[0].get("start") != 0 or float(beats[0].get("end", 100)) > 2.5:
        errors.append("the opening hook must begin immediately and change by 2.5 seconds")
    if not story.get("loop_resolution"):
        errors.append("end-to-start loop resolution is required")
    return errors


def validate_file(path: Path) -> list[str]:
    return validate_story(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: story_contract.py STORYBOARD.json")
    findings = validate_file(Path(sys.argv[1]))
    for finding in findings:
        print(finding, file=sys.stderr)
    if findings:
        raise SystemExit(1)
    print("Pilot storyboard contract: pass")
