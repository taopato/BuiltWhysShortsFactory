from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
ROOT = Path(__file__).resolve().parents[1]
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "but", "by",
    "for", "from", "how", "in", "into", "is", "it", "of", "on", "or",
    "that", "the", "their", "this", "to", "was", "what", "when", "why",
    "with", "your",
}


def _tokens(value: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(value.lower()) if token not in STOP_WORDS and len(token) > 1]


def cosine_similarity(left: str, right: str) -> float:
    a, b = Counter(_tokens(left)), Counter(_tokens(right))
    if not a or not b:
        return 0.0
    numerator = sum(a[token] * b[token] for token in set(a) & set(b))
    denominator = math.sqrt(sum(value * value for value in a.values())) * math.sqrt(
        sum(value * value for value in b.values())
    )
    return numerator / denominator if denominator else 0.0


def _manifest(path_value: str) -> tuple[dict[str, Any], list[str]]:
    if not path_value:
        return {}, ["Asset manifest is missing"]
    try:
        return json.loads(Path(path_value).read_text(encoding="utf-8")), []
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}, ["Asset manifest could not be read"]


def _asset_ids(assets: Iterable[dict[str, Any]]) -> list[int]:
    result: list[int] = []
    for asset in assets:
        try:
            value = int(asset.get("pexels_id") or 0)
        except (TypeError, ValueError):
            value = 0
        if not value and asset.get("local_file"):
            try:
                sidecar = (ROOT / str(asset["local_file"])).with_suffix(".json")
                value = int(json.loads(sidecar.read_text(encoding="utf-8")).get("pexels_id") or 0)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                value = 0
        if value:
            result.append(value)
    return result


def assess_job(connection, job: dict[str, Any]) -> dict[str, Any]:
    """Evaluate locally provable originality evidence; never promise monetization."""
    blockers: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []
    score = 100
    manifest, manifest_warnings = _manifest(str(job.get("manifest_path") or ""))
    warnings.extend(manifest_warnings)
    assets = [item for item in manifest.get("assets", []) if isinstance(item, dict)]
    sources = [item for item in manifest.get("fact_sources", []) if isinstance(item, dict) and item.get("url")]
    stock = [item for item in assets if item.get("type") == "stock_video"]
    original = [item for item in assets if item.get("type") in {
        "procedural_diagram", "procedural_animation", "original_video", "original_image"
    }]
    visual_puzzle = str(job.get("channel_key") or "") == "visualwhys"
    hybrid = bool(manifest.get("hybrid_template"))
    pexels_ids = _asset_ids(stock)

    def check(name: str, passed: bool, detail: str, penalty: int = 0, blocking: bool = False) -> None:
        nonlocal score
        checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            score -= penalty
            (blockers if blocking else warnings).append(detail)

    check("research_sources", len(sources) >= 2, f"{len(sources)} research sources recorded", 20, True)
    minimum_assets = 7 if hybrid else 8
    minimum_stock = 3 if hybrid else 6
    minimum_original = 4 if hybrid else (8 if visual_puzzle else 2)
    check("visual_count", len(assets) >= minimum_assets, f"{len(assets)} licensed/original visual assets recorded", 20, True)
    check("stock_variety", visual_puzzle or len(stock) >= minimum_stock,
          "Stock footage is intentionally not used" if visual_puzzle else f"{len(stock)} distinct stock scenes recorded", 15, True)
    check("original_visuals", len(original) >= minimum_original,
          f"{len(original)} project-generated explanatory visuals recorded", 12, True)
    check("within_video_asset_dedupe", not pexels_ids or len(pexels_ids) == len(set(pexels_ids)),
          "No stock clip is repeated inside this video", 20, True)
    all_commercial = bool(assets) and all(
        item.get("commercial_use") is True and str(item.get("license") or "").strip() for item in assets
    )
    check("commercial_rights", all_commercial, "Every visual has a commercial-use license record", 30, True)

    columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}
    if "story_id" in columns:
        rows = connection.execute(
            """SELECT id,topic,title,script,manifest_path,story_id FROM jobs
               WHERE id<>? AND id<>? AND parent_job_id<>?
               AND story_id<>?
               AND status NOT IN ('draft','rendering','failed','rejected')""",
            (job["id"], str(job.get("parent_job_id") or ""), job["id"],
             str(job.get("story_id") or job["id"])),
        ).fetchall()
    else:
        rows = connection.execute(
            """SELECT id,topic,title,script,manifest_path FROM jobs
               WHERE id<>? AND id<>? AND parent_job_id<>?
               AND status NOT IN ('draft','rendering','failed','rejected')""",
            (job["id"], str(job.get("parent_job_id") or ""), job["id"]),
        ).fetchall()
    max_topic, max_script, similar_id, similar_title = 0.0, 0.0, "", ""
    used_elsewhere: set[int] = set()
    for row in rows:
        other = dict(row)
        topic_similarity = cosine_similarity(
            f"{job.get('topic', '')} {job.get('title', '')}",
            f"{other.get('topic', '')} {other.get('title', '')}",
        )
        script_similarity = cosine_similarity(str(job.get("script") or ""), str(other.get("script") or ""))
        if max(topic_similarity, script_similarity) > max(max_topic, max_script):
            similar_id = str(other.get("id") or "")
            similar_title = str(other.get("title") or other.get("topic") or "")
        max_topic = max(max_topic, topic_similarity)
        max_script = max(max_script, script_similarity)
        other_manifest, _ = _manifest(str(other.get("manifest_path") or ""))
        used_elsewhere.update(_asset_ids(item for item in other_manifest.get("assets", []) if isinstance(item, dict)))

    cross_reuse = sorted(set(pexels_ids) & used_elsewhere)
    closest_label = f" — {similar_title}" if similar_title else ""
    check("topic_uniqueness", max_topic < 0.82, f"Closest topic/title similarity: {max_topic:.0%}{closest_label}", 22, True)
    check("script_uniqueness", max_script < 0.72, f"Closest script similarity: {max_script:.0%}{closest_label}", 28, True)
    check("cross_video_asset_dedupe", not cross_reuse, f"Reused stock clip IDs: {cross_reuse or 'none'}", 25, True)
    word_count = len(_tokens(str(job.get("script") or "")))
    check("narrative_depth", word_count >= (20 if visual_puzzle else 65),
          f"{'Storyboard' if visual_puzzle else 'Narration'} contains {word_count} meaningful words", 18, True)

    score = max(0, min(100, score))
    status = "pass" if not blockers and score >= 75 else "blocked"
    return {
        "status": status, "score": score, "checks": checks, "blockers": blockers,
        "warnings": warnings, "closest_job_id": similar_id, "closest_job_title": similar_title,
        "metrics": {"research_sources": len(sources), "visual_assets": len(assets),
                    "stock_scenes": len(stock), "original_visuals": len(original),
                    "topic_similarity": round(max_topic, 4), "script_similarity": round(max_script, 4)},
        "disclaimer": "Automated evidence check; it does not guarantee platform monetization.",
    }
