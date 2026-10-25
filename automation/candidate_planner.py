from __future__ import annotations

import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any

import requests


AUTOMATION = Path(__file__).resolve().parent
CATALOG_PATH = AUTOMATION / "channel_catalog.json"
# Approved videos belong to the publish pool, not the owner's review inbox.
# Only work that is still being produced/reviewed counts toward the review
# inventory target.
REVIEW_PIPELINE_STATUSES = ("draft", "rendering", "pending_review", "revision_requested")


def load_catalog() -> dict[str, dict[str, Any]]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _local_json(prompt: str, max_tokens: int = 1400) -> dict[str, Any]:
    configured = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1").rstrip("/")
    base = configured[:-3] if configured.endswith("/v1") else configured
    response = requests.post(
        f"{base}/api/chat",
        json={
            "model": os.environ.get("OLLAMA_MODEL", "qwen3:4b"),
            "messages": [{"role": "user", "content": prompt}],
            "format": "json", "stream": False, "think": False,
            "options": {"temperature": 0.65, "num_predict": max_tokens, "num_ctx": 4096},
            "keep_alive": "30m",
        },
        timeout=600,
    )
    response.raise_for_status()
    content = str(response.json().get("message", {}).get("content") or "").strip()
    return json.loads(content.removeprefix("```json").removesuffix("```").strip())


def generate_ideas(channel_key: str, existing_topics: list[str], count: int = 8) -> list[dict[str, Any]]:
    catalog = load_catalog()
    channel = catalog[channel_key]
    seeds = [str(item) for item in channel.get("seed_topics", [])]
    existing_normalized = {_normalized(item) for item in existing_topics}
    available_seeds = [item for item in seeds if _normalized(item) not in existing_normalized]
    allowed = available_seeds[:count * 2]
    if channel.get("visual_puzzle"):
        return [{
            "topic": topic,
            "hook": "A visual mechanism with three possible outcomes.",
            "channel_fit_score": 100,
            "fit_reason": "Original procedural motion creates a language-free engineering puzzle.",
            "pexels_queries": [],
        } for topic in allowed[:count]]
    prompt = f"""You plan factual 35-55 second vertical videos for {channel['name']}.
CHANNEL CONTRACT: {channel['idea_brief']}
Every idea must include: {', '.join(channel['must_include'])}.
Never include: {', '.join(channel['exclude'])}.
Examples show scope only; do not repeat them: {', '.join(channel['examples'])}.
Already used topics (never repeat or paraphrase closely): {json.dumps(existing_topics[-80:])}
Allowed verified topics: {json.dumps(allowed)}
Return JSON only: {{"ideas":[{{"topic":"specific question in English","hook":"one-sentence visual hook","channel_fit_score":95,"fit_reason":"why it belongs only to this channel","pexels_queries":["six concrete English stock-video searches"]}}]}}.
Generate exactly {count} distinct ideas. Queries must name visible subjects, not abstract concepts.
When allowed verified topics are present, copy topic text exactly from that list. Never invent or rewrite a topic.
"""
    payload = _local_json(prompt)
    ideas = [item for item in payload.get("ideas", []) if isinstance(item, dict)]
    if allowed:
        lookup = {_normalized(item): item for item in allowed}
        ideas = [item for item in ideas if _normalized(str(item.get("topic", ""))) in lookup]
        for item in ideas:
            item["topic"] = lookup[_normalized(str(item["topic"]))]
            # Small local models sometimes return semantically equivalent keys
            # (reason/queries) even when the requested JSON schema says
            # fit_reason/pexels_queries. Normalize those harmless variations so
            # a valid curated topic is not discarded before Pexels validation.
            item["fit_reason"] = str(
                item.get("fit_reason") or item.get("reason") or item.get("explanation")
                or "A visible feature of an everyday physical object is explained through a concrete mechanism."
            ).strip()
            raw_queries = item.get("pexels_queries") or item.get("search_queries") or item.get("queries") or []
            if not isinstance(raw_queries, list):
                raw_queries = []
            queries = [str(query).strip() for query in raw_queries if str(query).strip()]
            item["pexels_queries"] = _complete_queries(item["topic"], queries)
            item["hook"] = str(item.get("hook") or f"This familiar detail on {item['topic'].removeprefix('Why ').lower()} has a practical job.").strip()
            try:
                item["channel_fit_score"] = int(item.get("channel_fit_score") or item.get("fit_score") or 95)
            except (TypeError, ValueError):
                item["channel_fit_score"] = 95
    return ideas[:count]


def _complete_queries(topic: str, queries: list[str]) -> list[str]:
    """Return six concrete stock-footage queries without another model call."""
    clean = re.sub(r"^(why|how)\s+", "", topic, flags=re.IGNORECASE)
    clean = re.sub(r"\b(have|has|use|uses|contain|contains|cannot|are|is)\b.*$", "", clean, flags=re.IGNORECASE).strip()
    clean = clean or topic
    fallbacks = [
        clean,
        f"{clean} close up",
        f"{clean} detail",
        f"{clean} in use",
        f"{clean} macro",
        f"{clean} manufacturing",
    ]
    result: list[str] = []
    for query in [*queries, *fallbacks]:
        normalized = _normalized(query)
        if normalized and normalized not in {_normalized(item) for item in result}:
            result.append(query)
        if len(result) == 6:
            break
    return result


def research_count(topic: str) -> int:
    # Exact question-shaped searches are often empty even when the physical
    # object has several useful reference pages. Retry with the subject noun
    # instead of discarding an otherwise strong, filmable candidate.
    subject = re.sub(r"^(why|how)\s+", "", topic, flags=re.IGNORECASE)
    subject = re.sub(r"\b(have|has|use|uses|contain|contains|cannot|are|is)\b.*$", "", subject,
                     flags=re.IGNORECASE).strip()
    found: set[str] = set()
    for query in dict.fromkeys((topic, subject)):
        if not query:
            continue
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": 4},
            headers={"User-Agent": "BuiltWhys/1.0 (content research)"}, timeout=25,
        )
        response.raise_for_status()
        found.update(str(item.get("title")) for item in response.json().get("query", {}).get("search", [])
                     if item.get("title"))
        if len(found) >= 2:
            break
    return len(found)


def pexels_availability(queries: list[str]) -> dict[str, Any]:
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PEXELS_API_KEY is required for candidate validation")
    unique_ids: set[int] = set()
    successful_queries = 0
    results: dict[str, int] = {}
    for query in queries[:6]:
        response = requests.get(
            "https://api.pexels.com/videos/search",
            params={"query": query, "per_page": 8, "orientation": "portrait"},
            headers={"Authorization": key}, timeout=30,
        )
        response.raise_for_status()
        videos = response.json().get("videos", [])
        count = len(videos)
        results[query] = count
        if count:
            successful_queries += 1
        unique_ids.update(int(video["id"]) for video in videos if video.get("id") is not None)
    return {
        "unique_video_count": len(unique_ids),
        "successful_query_count": successful_queries,
        "query_results": results,
        "pass": len(unique_ids) >= 8 and successful_queries >= 4,
    }


def score_candidate(idea: dict[str, Any], research: int, footage: dict[str, Any], novelty: int) -> int:
    queries = idea.get("pexels_queries") if isinstance(idea.get("pexels_queries"), list) else []
    fit = min(20, max(0, int(idea.get("channel_fit_score", 0))) // 5)
    visual = min(35, footage["unique_video_count"] * 2 + footage["successful_query_count"] * 3)
    evidence = min(20, research * 7)
    hook = min(10, 5 + int(bool(str(idea.get("hook", "")).strip())) * 3 + int(len(queries) >= 6) * 2)
    return min(100, fit + visual + evidence + min(15, novelty) + hook)


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def evaluate(channel_key: str, idea: dict[str, Any], existing_topics: list[str]) -> dict[str, Any]:
    channel = load_catalog()[channel_key]
    topic = str(idea.get("topic") or "").strip()
    queries = [str(q).strip() for q in idea.get("pexels_queries", []) if str(q).strip()][:6]
    fit_score = int(idea.get("channel_fit_score", 0) or 0)
    if channel.get("visual_puzzle"):
        normalized = _normalized(topic)
        similarities = [len(set(normalized.split()) & set(_normalized(old).split())) for old in existing_topics]
        novelty = 5 if similarities and max(similarities) >= 5 else 20
        # Editorial score reflects how clearly the mechanism reads on a small
        # phone screen. It also gives the review inbox a deterministic best pick.
        visual_score = 95
        for word, score in (("ball", 99), ("marble", 99), ("lever", 98),
                            ("gear", 97), ("wheel", 97), ("tank", 96),
                            ("pipe", 96), ("domino", 95), ("stack", 95)):
            if word in normalized.split():
                visual_score = score
                break
        return {
            "pass": bool(len(topic) >= 12 and novelty >= 20),
            "score": visual_score if novelty >= 20 else 0,
            "channel_key": channel_key,
            "research_count": 2,
            "novelty_score": novelty,
            "channel_fit_score": 100,
            "footage": {"pass": True, "source": "original_procedural_animation"},
            "idea": idea,
        }
    if len(topic) < 12 or len(queries) < 6 or not str(idea.get("fit_reason") or "").strip():
        return {"pass": False, "score": 0, "reason": "incomplete channel candidate"}
    if fit_score < 90:
        return {"pass": False, "score": 0, "reason": "channel fit below 90", "channel_fit_score": fit_score}
    normalized = _normalized(topic)
    similarities = [len(set(normalized.split()) & set(_normalized(old).split())) for old in existing_topics]
    novelty = 5 if similarities and max(similarities) >= 5 else 20
    research = research_count(topic)
    footage = pexels_availability(queries)
    score = score_candidate(idea, research, footage, novelty)
    return {
        "pass": bool(footage["pass"] and novelty >= 20 and score >= 75),
        "score": score, "channel_key": channel_key, "research_count": research,
        "novelty_score": novelty, "channel_fit_score": fit_score, "footage": footage, "idea": idea,
    }


def queue_best(store: Any, channel_key: str, limit: int = 1) -> int:
    existing = [str(row["topic"]) for row in store.connection.execute("SELECT topic FROM jobs")]
    evaluated: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}
    for idea in generate_ideas(channel_key, existing):
        try:
            report = evaluate(channel_key, idea, existing)
        except requests.RequestException as exc:
            store.event("warning", "candidate_network", str(exc), details_json={"channel": channel_key})
            continue
        if report.get("pass"):
            evaluated.append(report)
        else:
            reason = str(report.get("reason") or "score_or_footage_gate")
            if report.get("footage") and not report["footage"].get("pass"):
                reason = "pexels_footage_gate"
            rejected[reason] = rejected.get(reason, 0) + 1
    evaluated.sort(key=lambda item: int(item["score"]), reverse=True)
    queued = 0
    for report in evaluated[:limit]:
        topic = str(report["idea"]["topic"]).strip()
        created = store.queue.create_job(topic)
        store.update_job(created["id"], {
            "channel_key": channel_key, "language": "en-US", "story_id": created["id"],
            "candidate_score": report["score"],
            "candidate_report": json.dumps(report, ensure_ascii=False),
        })
        store.event("info", "candidate_selected", f"{channel_key}: {topic} ({report['score']})", created["id"])
        queued += 1
    store.event(
        "info", "candidate_batch_evaluated",
        f"{channel_key}: {queued} queued, {sum(rejected.values())} rejected",
        channel=channel_key, rejected=rejected,
    )
    return queued


def channel_need(store: Any, channel_key: str, target: int) -> int:
    placeholders = ",".join("?" for _ in REVIEW_PIPELINE_STATUSES)
    active = store.connection.execute(
        f"SELECT COUNT(*) count FROM jobs WHERE channel_key=? AND language='en-US' AND status IN ({placeholders})",
        (channel_key, *REVIEW_PIPELINE_STATUSES),
    ).fetchone()["count"]
    return max(0, target - int(active))
