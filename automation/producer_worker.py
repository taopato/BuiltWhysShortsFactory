from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont

from control_center_store import ControlCenterStore
from candidate_planner import channel_need, load_catalog, queue_best
from generate_pexels_batch import QUERIES as DEFAULT_PEXELS_QUERIES
from notifier import notify
from review_queue import DEFAULT_DB, QueueError, utc_now
from visual_puzzle import render as render_visual_puzzle, storyboard as visual_storyboard
from mechanism_animation import install_hybrid_mechanism


ROOT = Path(__file__).resolve().parents[1]
AUTOMATION = ROOT / "automation"
PILOTS = AUTOMATION / "pilots"


def ollama_json(prompt: str, temperature: float, max_tokens: int = 650) -> dict[str, Any]:
    """Use Ollama's native API so Qwen thinking can be disabled on CPU servers."""
    configured = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1").rstrip("/")
    base = configured[:-3] if configured.endswith("/v1") else configured
    last_error: Exception | None = None
    for attempt in range(2):
        request_prompt = prompt if attempt == 0 else (
            prompt + "\nYour previous response was invalid or truncated. Return one compact, complete JSON object only."
        )
        response = requests.post(
            f"{base}/api/chat",
            json={
                "model": os.environ.get("OLLAMA_MODEL", "qwen3:4b"),
                "messages": [{"role": "user", "content": request_prompt}],
                "format": "json", "stream": False, "think": False,
                "options": {
                    "temperature": temperature if attempt == 0 else min(temperature, 0.15),
                    "num_predict": max_tokens if attempt == 0 else max(1100, max_tokens),
                    "num_ctx": 4096,
                },
                "keep_alive": "30m",
            },
            timeout=600,
        )
        response.raise_for_status()
        content = str(response.json().get("message", {}).get("content") or "").strip()
        if not content:
            last_error = QueueError("local model returned an empty response")
            continue
        try:
            return json.loads(content.removeprefix("```json").removesuffix("```").strip())
        except json.JSONDecodeError as exc:
            last_error = exc
    raise QueueError(f"local model returned invalid JSON twice: {last_error}")


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48]


def safe_cover(value: str) -> str:
    value = value.translate(str.maketrans({"İ": "I", "ı": "I", "Ş": "S", "ş": "S", "Ğ": "G", "ğ": "G", "Ü": "U", "ü": "U", "Ö": "O", "ö": "O", "Ç": "C", "ç": "C"}))
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9 ?!-]+", "", value).strip()[:36] or "BUILT DIFFERENT"


def normalized_hashtags(values: Any) -> list[str]:
    if not isinstance(values, list):
        values = str(values or "").replace(",", " ").split()
    tags = []
    for value in values:
        tag = re.sub(r"[^\w]", "", str(value), flags=re.UNICODE).strip("_")
        if tag and f"#{tag}" not in tags:
            tags.append(f"#{tag}")
    return tags[:8]


def wiki_context(topic: str) -> tuple[list[dict[str, str]], str]:
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={"action": "query", "list": "search", "srsearch": topic, "format": "json", "utf8": 1, "srlimit": 4},
        headers={"User-Agent": "BuiltWhys/1.0 (educational content research)"}, timeout=30,
    )
    response.raise_for_status()
    results = response.json().get("query", {}).get("search", [])
    sources, context = [], []
    for item in results[:3]:
        title = str(item.get("title", ""))
        if not title:
            continue
        sources.append({
            "title": title, "publisher": "Wikipedia research seed",
            "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
            "accessed_at": utc_now()[:10],
        })
        context.append(re.sub("<[^>]+>", "", str(item.get("snippet", ""))))
    while len(sources) < 2:
        sources.append({
            "title": f"Research required: {topic}", "publisher": "BuiltWhys research queue",
            "url": "https://en.wikipedia.org/wiki/Special:Search?search=" + urllib.parse.quote(topic),
            "accessed_at": utc_now()[:10],
        })
    return sources, "\n".join(context)


def ollama_package(topic: str, context: str, existing_script: str = "", mode: str = "full",
                   language: str = "en-US", channel_key: str = "builtwhys",
                   revision_note: str = "") -> dict[str, Any]:
    language_name = "Turkish" if language == "tr-TR" else "English"
    channel = load_catalog().get(channel_key, load_catalog()["builtwhys"])
    prompt = f"""Create an original {channel['name']} vertical factual Short package.
Channel contract: {channel['idea_brief']}
Required scope: {', '.join(channel['must_include'])}
Forbidden scope: {', '.join(channel['exclude'])}
Topic: {topic}
Revision mode: {mode}
Output language: {language_name}
Research snippets (use only as factual seeds, do not copy wording): {context}
Existing script: {existing_script}
Owner revision request (mandatory; implement it exactly when present): {revision_note or "none"}
Return JSON only with: title, script, cover_text, pexels_queries, caption, hashtags.
Rules: title <=70 characters; script 85-115 words; curiosity hook in first sentence;
explain one concrete mechanism; no unsupported numbers; original wording; exactly six distinct,
specific English-language Pexels search queries; caption <=700 characters; hashtags is an array of 5 items.
Write title, script, cover_text, caption and hashtags in {language_name}."""
    package = ollama_json(prompt, 0.45, 750)
    queries = package.get("pexels_queries")
    if not isinstance(queries, list) or len(queries) < 6:
        raise QueueError("local model did not return six Pexels queries")
    script = str(package.get("script", "")).strip()
    if len(script.split()) < 80:
        for _ in range(2):
            repair_prompt = f"""Expand the following {language_name} Short narration to exactly 95-105 words.
Preserve its exact factual claims and mechanism. Do not introduce new numbers, claims, examples or history.
Keep the first sentence as a curiosity hook and avoid repetition. Count words before answering.
Return JSON only with: {{"script":"expanded narration"}}.
Narration: {script}"""
            repaired = ollama_json(repair_prompt, 0.15, 650)
            script = str(repaired.get("script", "")).strip()
            if len(script.split()) >= 80:
                break
        if len(script.split()) < 80:
            raise QueueError("local model returned a script below the 80-word delivery minimum")
        package["script"] = script
    package["hashtags"] = normalized_hashtags(package.get("hashtags"))
    return package


def revised_pexels_queries(topic: str, script: str, current: list[str], note: str) -> list[str]:
    """Turn the owner's visual feedback into a fresh, auditable stock plan."""
    prompt = f"""Revise the stock-footage search plan for a factual BuiltWhys Short.
Topic: {topic}
Narration: {script}
Current searches: {json.dumps(current, ensure_ascii=False)}
Owner request (mandatory): {note}
Return JSON only as {{"pexels_queries":["six concrete English searches"]}}.
Each query must name a visible real-world subject or action. Use six distinct searches.
Do not return abstract concepts, explanations or camera instructions."""
    package = ollama_json(prompt, 0.25, 400)
    queries = [str(item).strip() for item in package.get("pexels_queries", []) if str(item).strip()]
    if len(queries) < 6:
        raise QueueError("local model did not implement the visual revision as six Pexels queries")
    return queries[:6]


def revision_render_config(mode: str, note: str, language: str) -> dict[str, Any]:
    """Map common owner voice/subtitle requests to safe renderer settings."""
    lowered = note.casefold()
    config: dict[str, Any] = {"source_note": note, "revision_type": mode}
    if mode == "voice":
        if any(word in lowered for word in ("hızlı", "hizli", "faster", "fast")):
            config["voice_rate"] = 1.15
        elif any(word in lowered for word in ("yavaş", "yavas", "slower", "slow")):
            config["voice_rate"] = 0.92
        if any(word in lowered for word in ("kadın", "kadin", "female", "woman")):
            config["voice_name"] = "tr-TR-EmelNeural" if language == "tr-TR" else "en-US-AvaMultilingualNeural"
        elif any(word in lowered for word in ("erkek", "male", "man voice")):
            config["voice_name"] = "tr-TR-AhmetNeural" if language == "tr-TR" else "en-US-AndrewMultilingualNeural"
        if any(word in lowered for word in ("yüksek", "yuksek", "louder", "loud")):
            config["voice_volume"] = 1.15
        elif any(word in lowered for word in ("düşük", "dusuk", "quieter", "quiet")):
            config["voice_volume"] = 0.88
    elif mode == "subtitles":
        if any(word in lowered for word in ("alta", "aşağı", "asagi", "lower", "bottom")):
            config["custom_position"] = 78.0
        elif any(word in lowered for word in ("yukarı", "yukari", "higher", "upper")):
            config["custom_position"] = 57.0
        if any(word in lowered for word in ("büyük", "buyuk", "larger", "bigger")):
            config["font_size"] = 66
        elif any(word in lowered for word in ("küçük", "kucuk", "smaller")):
            config["font_size"] = 50
    return config


def ollama_localization(source: dict[str, Any], language: str) -> dict[str, Any]:
    if language != "tr-TR":
        raise QueueError(f"unsupported localization language: {language}")
    prompt = f"""Localize this original BuiltWhys engineering Short for a native Turkish audience.
Do not add facts, numbers or claims that are absent from the source. Preserve the concrete mechanism and meaning,
but use natural Turkish phrasing rather than a literal sentence-by-sentence translation.
Return JSON only with: title, script, cover_text, caption, hashtags.
Rules: title <=70 characters; narration 70-110 Turkish words; strong curiosity hook in the first sentence;
cover_text <=32 characters; caption <=700 characters; hashtags is an array of exactly 5 Turkish/brand tags.
Source title: {source.get('title', '')}
Source script: {source.get('script', '')}
Source caption: {source.get('description', '')}
Source hashtags: {source.get('hashtags', '')}"""
    package = ollama_json(prompt, 0.2, 850)
    if len(str(package.get("script") or "").split()) < 60:
        raise QueueError("local model returned a Turkish narration that is too short")
    if not isinstance(package.get("hashtags"), list) or len(package["hashtags"]) < 3:
        raise QueueError("local model returned invalid Turkish hashtags")
    package["hashtags"] = normalized_hashtags(package.get("hashtags"))
    return package


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        ROOT / "resource" / "fonts" / "BeVietnamPro-Bold.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def diagram(path: Path, title: str, subtitle: str, variant: int) -> None:
    image = Image.new("RGB", (1080, 1920), "#0a0d12")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((90, 280, 990, 1500), 50, fill="#151b25", outline="#586577", width=5)
    if variant == 1:
        draw.line((250, 1000, 830, 700), fill="#f4f1e8", width=38)
        draw.polygon([(830, 700), (748, 700), (805, 778)], fill="#f4f1e8")
        draw.ellipse((180, 920, 330, 1070), outline="#62d59d", width=24)
        draw.ellipse((750, 620, 900, 770), outline="#ffbd59", width=24)
    else:
        for x in range(220, 880, 130):
            draw.rounded_rectangle((x, 620, x + 65, 1280), 30, fill="#d9dde5")
        draw.line((180, 1370, 900, 1370), fill="#62d59d", width=30)
    draw.text((90, 110), title.upper()[:34], font=font(54), fill="#ffffff")
    draw.text((90, 1580), subtitle, font=font(42), fill="#c3c9d2")
    draw.text((90, 1740), "BUILTWHYS · ORIGINAL DIAGRAM", font=font(28), fill="#6f7784")
    image.save(path, quality=94)


def build_pilot(job: dict, mode: str) -> Path:
    pilot = PILOTS / f"generated-{job['id']}"
    parent_dir = Path(job.get("pilot_dir") or "")
    if (job.get("parent_job_id") or job.get("source_job_id")) and parent_dir.is_dir() and not pilot.exists():
        shutil.copytree(parent_dir, pilot)
    pilot.mkdir(parents=True, exist_ok=True)
    query_plan = pilot / "pexels_queries.json"
    if not query_plan.is_file() and parent_dir.name in DEFAULT_PEXELS_QUERIES:
        query_plan.write_text(
            json.dumps(DEFAULT_PEXELS_QUERIES[parent_dir.name], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    reusable = all((pilot / name).is_file() for name in (
        "script.txt", "shot_plan.json", "pexels_queries.json", "manifest.json",
    ))
    revision_note = str(job.get("revision_note") or job.get("decision_note") or "").strip()
    render_config_path = pilot / "revision_render_config.json"
    if mode == "full":
        render_config_path.unlink(missing_ok=True)
    if mode != "full" and revision_note:
        (pilot / "revision_request.json").write_text(json.dumps({
            "job_id": job["id"], "type": mode, "note": revision_note,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if mode == "localize" and job.get("source_job_id") and reusable:
        source = dict(job)
        source.update({
            "title": job.get("title", ""), "script": job.get("script", ""),
            "description": job.get("description", ""), "hashtags": job.get("hashtags", ""),
        })
        package = ollama_localization(source, str(job.get("language") or "tr-TR"))
        (pilot / "script.txt").write_text(str(package["script"]).strip() + "\n", encoding="utf-8")
        (pilot / "cover.txt").write_text(safe_cover(str(package.get("cover_text") or package["title"])), encoding="utf-8")
        (pilot / "shot_plan.json").write_text(json.dumps({
            "title": package["title"], "cover_text": package.get("cover_text"),
            "language": job.get("language", "tr-TR"), "localized_from": job["source_job_id"],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        (pilot / "social_metadata.json").write_text(json.dumps({
            "language": job.get("language", "tr-TR"), "caption": package.get("caption", ""),
            "hashtags": package.get("hashtags", []),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for name in ("manifest.json", "manifest-v3.json"):
            path = pilot / name
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                data["job_id"] = job["id"]
                data["localized_from"] = job["source_job_id"]
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return pilot
    if mode in {"visuals", "voice", "subtitles", "hybrid"} and reusable:
        # These revisions must preserve the approved editorial package. In
        # particular, a visuals-only request should never spend minutes asking
        # the local LLM to rewrite a script the owner chose to keep.
        social = pilot / "social_metadata.json"
        if not social.is_file():
            social.write_text(json.dumps({
                "language": job.get("language", "en-US"),
                "caption": job.get("description", ""),
                "hashtags": str(job.get("hashtags", "")).split(),
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for name in ("manifest.json", "manifest-v3.json"):
            path = pilot / name
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                data["job_id"] = job["id"]
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if mode in {"visuals", "hybrid"} and revision_note:
            current_queries = json.loads((pilot / "pexels_queries.json").read_text(encoding="utf-8"))
            fresh_queries = revised_pexels_queries(
                str(job["topic"]), str(job.get("script") or ""), current_queries, revision_note,
            )
            (pilot / "pexels_queries.json").write_text(
                json.dumps(fresh_queries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )
        if mode in {"voice", "subtitles"} and revision_note:
            render_config_path.write_text(
                json.dumps(revision_render_config(
                    mode, revision_note, str(job.get("language") or "en-US")
                ), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return pilot
    sources, context = wiki_context(job["topic"])
    package = ollama_package(
        job["topic"], context, job.get("script", ""), mode,
        str(job.get("language") or "en-US"),
        str(job.get("channel_key") or "builtwhys"),
        revision_note,
    )
    preserve_script = mode in {"visuals", "voice", "subtitles", "hybrid"} and str(job.get("script", "")).strip()
    script = str(job.get("script", "")).strip() if preserve_script else str(package["script"]).strip()
    if preserve_script:
        package["title"] = job.get("title") or package["title"]
    (pilot / "script.txt").write_text(script + "\n", encoding="utf-8")
    (pilot / "cover.txt").write_text(safe_cover(str(package.get("cover_text") or "BUILT DIFFERENT")), encoding="utf-8")
    (pilot / "pexels_queries.json").write_text(json.dumps(package["pexels_queries"][:6], ensure_ascii=False, indent=2), encoding="utf-8")
    (pilot / "shot_plan.json").write_text(json.dumps({"title": package["title"], "cover_text": package.get("cover_text"), "language": job.get("language", "en-US")}, ensure_ascii=False, indent=2), encoding="utf-8")
    (pilot / "social_metadata.json").write_text(json.dumps({
        "language": job.get("language", "en-US"), "caption": package.get("caption", ""),
        "hashtags": package.get("hashtags", []),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    assets = pilot / "assets"
    assets.mkdir(exist_ok=True)
    diagram(assets / "scene-01-hero.png", str(package["title"]), "HIDDEN DESIGN, VISIBLE REASON", 1)
    diagram(assets / "scene-02-mechanism.png", "MECHANISM", "HOW THE PART HANDLES THE LOAD", 1)
    diagram(assets / "scene-03-result.png", "RESULT", "WHY THE SHAPE WORKS", 2)
    manifest = {
        "job_id": job["id"], "ai_disclosure_required": False, "fact_sources": sources[:3],
        "assets": [
            {"type": "procedural_diagram", "source_url": f"local://{p.relative_to(ROOT).as_posix()}",
             "license": "Project-generated original diagram", "commercial_use": True}
            for p in sorted(assets.glob("scene-*.png"))
        ],
    }
    (pilot / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return pilot


def run(command: list[str], heartbeat=None) -> None:
    process = subprocess.Popen(command, cwd=ROOT, text=True)
    while process.poll() is None:
        if heartbeat:
            heartbeat()
        time.sleep(15)
    if process.returncode != 0:
        raise QueueError(f"command failed ({process.returncode}): {Path(command[0]).name}")


def make_thumbnail(job_id: str, video_path: Path) -> Path:
    output = ROOT / "storage" / "thumbnails" / f"{job_id}.jpg"
    output.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", "0.45", "-i", str(video_path),
         "-frames:v", "1", "-vf", "scale=540:-2", "-q:v", "3", "-y", str(output)])
    return output


def process_job(store: ControlCenterStore, job: dict) -> None:
    if str(job.get("channel_key") or "") == "visualwhys":
        pilot = PILOTS / f"visual-{job['id']}"
        script = visual_storyboard(str(job["topic"]))
        store.update_job(job["id"], {
            "pilot_dir": str(pilot), "title": str(job["topic"]), "script": script,
            "description": "A completely original, language-free visual engineering puzzle. Predict the result before the reveal.",
            "hashtags": "#VisualPuzzle #Engineering #Logic #Shorts #BuiltWhys",
            "language": "en-US", "platforms": "youtube,instagram,facebook",
        })
        current = store.queue.get_job(job["id"])
        if current["status"] == "draft":
            store.queue.start_render(job["id"])
        video, manifest, thumbnail = render_visual_puzzle(store.queue.get_job(job["id"]), pilot)
        store.queue.attach_render(job["id"], video, manifest)
        store.update_job(job["id"], {
            "thumbnail_path": str(thumbnail), "metadata_path": "",
            "decision_note": "", "quality_score": int(job.get("candidate_score") or 98),
        })
        report = store.refresh_policy(job["id"])
        quality = store.refresh_quality(job["id"])
        if report["status"] != "pass" or quality["status"] != "pass":
            reason = "visual puzzle quality gate failed: " + "; ".join(
                (report.get("blockers") or []) + (quality.get("blockers") or [])
            )
            store.connection.execute(
                "UPDATE jobs SET status='failed',is_reserve=0,decision_note=?,updated_at=? WHERE id=?",
                (reason[:2000], utc_now(), job["id"]),
            )
            store.connection.commit()
            store.event("error", "production_failed", reason, job["id"])
            return
        store.event("info", "render_ready", "Language-free visual puzzle is ready for review", job["id"])
        notify(f"Yeni görsel bulmaca incelemeye hazır: {job['topic']}", "info", job["id"])
        return
    action = job.get("review_action") or "full"
    parent = store.queue.get_job(job["parent_job_id"]) if job.get("parent_job_id") else None
    if action == "metadata" and parent:
        _, context = wiki_context(job["topic"])
        package = ollama_package(
            job["topic"], context, job.get("script", ""), "metadata",
            str(job.get("language") or "en-US"),
            str(job.get("channel_key") or "builtwhys"),
            str(job.get("revision_note") or job.get("decision_note") or ""),
        )
        store.connection.execute(
            """UPDATE jobs SET video_path=?,manifest_path=?,thumbnail_path=?,title=?,description=?,hashtags=?,
               status='pending_review',updated_at=? WHERE id=?""",
            (parent["video_path"], parent["manifest_path"], parent.get("thumbnail_path", ""),
             package["title"], package.get("caption", ""), " ".join(package.get("hashtags", [])), utc_now(), job["id"]),
        )
        store.connection.commit()
        return
    pilot = build_pilot(job, action)
    store.update_job(job["id"], {"pilot_dir": str(pilot), "title": json.loads((pilot / "shot_plan.json").read_text(encoding="utf-8"))["title"], "script": (pilot / "script.txt").read_text(encoding="utf-8").strip()})
    existing_manifest_path = pilot / "manifest-v3.json"
    existing_manifest = (
        json.loads(existing_manifest_path.read_text(encoding="utf-8"))
        if existing_manifest_path.is_file() else {}
    )
    keep_hybrid_layout = action == "hybrid" or bool(existing_manifest.get("hybrid_template"))
    needs_new_visuals = action in {"visuals", "hybrid", "hook", "full"} or not (pilot / "assets-v3").is_dir()
    if needs_new_visuals:
        run(
            [sys.executable, str(AUTOMATION / "generate_pexels_batch.py"), "--pilot", pilot.name, "--force"],
            lambda: store.heartbeat("producer-worker", detail=f"downloading visuals for {job['id']}"),
        )
        if keep_hybrid_layout:
            store.heartbeat("producer-worker", detail=f"building original mechanism animation for {job['id']}")
            install_hybrid_mechanism(pilot, str(job["topic"]))
    run(
        [sys.executable, str(AUTOMATION / "render_job.py"), job["id"], "--pilot-dir", str(pilot), "--db", str(store.queue.db_path)],
        lambda: store.heartbeat("producer-worker", detail=f"rendering {job['id']}"),
    )
    rendered = store.queue.get_job(job["id"])
    thumb = make_thumbnail(job["id"], Path(rendered["video_path"]))
    metadata = json.loads((pilot / "social_metadata.json").read_text(encoding="utf-8"))
    metadata["hashtags"] = normalized_hashtags(metadata.get("hashtags"))
    (pilot / "social_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    store.update_job(job["id"], {
        "thumbnail_path": str(thumb), "metadata_path": str(pilot / "social_metadata.json"),
        "description": metadata.get("caption", ""), "hashtags": " ".join(metadata.get("hashtags", [])),
        "decision_note": "",
    })
    report = store.refresh_policy(job["id"])
    quality = store.refresh_quality(job["id"])
    if report["status"] != "pass":
        store.event("warning", "policy_gate", "Video requires revision before approval", job["id"],
                    score=report["score"], blockers=report["blockers"])
    if quality["status"] != "pass":
        store.event("warning", "quality_gate", "Video failed technical/editorial delivery checks", job["id"],
                    score=quality["score"], blockers=quality["blockers"])
    store.event("info", "render_ready", "Video is ready for Control Center review", job["id"])
    notify(f"Yeni video incelemeye hazır: {rendered['title'] or rendered['topic']}", "info", job["id"])


def refill(store: ControlCenterStore) -> bool:
    catalog = load_catalog()
    needs = {
        key: channel_need(store, key, int(config.get("reserve_target", 10)))
        for key, config in catalog.items()
        if bool(config.get("active", False))
    }
    if not needs:
        return False
    now = int(time.time())
    eligible = [
        (key, need) for key, need in needs.items()
        if need > 0 and now - int(store.setting(f"candidate_last_attempt_{key}", "0")) >= 300
    ]
    if not eligible:
        return False
    channel_key, need = max(eligible, key=lambda item: item[1])
    store.set_setting(f"candidate_last_attempt_{channel_key}", str(now))
    queued = 0
    # Queue several small, freshly de-duplicated batches in one refill pass.
    # Previously the worker added at most three jobs and then waited 30 minutes,
    # which allowed a target of ten to remain stuck at six.
    for _ in range(max(4, min(10, need))):
        remaining = need - queued
        if remaining <= 0:
            break
        added = queue_best(store, channel_key, min(3, remaining))
        queued += added
        if not added:
            break
    if not queued:
        store.event("warning", "candidate_batch_empty", f"No qualified Pexels-ready idea for {channel_key}")
    return queued > 0


def queue_missing_localization(store: ControlCenterStore) -> bool:
    if store.setting("auto_localize_approved", "true").lower() != "true":
        return False
    languages = [item.strip() for item in store.setting("localization_languages", "tr-TR").split(",") if item.strip()]
    for language in languages:
        row = store.connection.execute(
            """SELECT j.id FROM jobs j WHERE j.language='en-US' AND j.status='approved'
               AND j.human_reviewed=1 AND j.policy_status='pass' AND j.quality_status='pass'
               AND NOT EXISTS (SELECT 1 FROM jobs localized
                               WHERE localized.story_id=j.story_id AND localized.language=?
                               AND localized.status NOT IN ('rejected','failed'))
               ORDER BY j.updated_at LIMIT 1""", (language,),
        ).fetchone()
        if row:
            store.create_localization(str(row["id"]), language)
            return True
    return False


def process_once(store: ControlCenterStore) -> bool:
    row = store.connection.execute(
        """SELECT * FROM jobs WHERE status='revision_requested' ORDER BY created_at LIMIT 1"""
    ).fetchone()
    if not row:
        # Keep the review inventory full even while older drafts are waiting to
        # render. Previously refill ran only after the last draft completed, so
        # a rejection or failed render could leave the inbox below target for
        # hours.
        if refill(store):
            return True
        row = store.connection.execute("SELECT * FROM jobs WHERE status='draft' ORDER BY created_at LIMIT 1").fetchone()
    if not row:
        return queue_missing_localization(store) or refill(store)
    job = dict(row)
    try:
        process_job(store, job)
    except Exception as exc:
        current = store.queue.get_job(job["id"])
        if current["status"] in {"draft", "revision_requested", "rendering"}:
            if current["status"] == "draft":
                store.connection.execute("UPDATE jobs SET status='failed',decision_note=?,updated_at=? WHERE id=?", (str(exc)[:2000], utc_now(), job["id"]))
                store.connection.commit()
            else:
                store.queue.mark_failed(job["id"], str(exc))
        store.event("error", "production_failed", str(exc), job["id"])
        notify(f"Video üretimi başarısız: {job['topic']}\n{exc}", "error", job["id"])
        raise
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=20)
    args = parser.parse_args()
    while True:
        store = ControlCenterStore(args.db)
        try:
            store.heartbeat("producer-worker")
            processed = process_once(store)
        except Exception as exc:
            store.heartbeat("producer-worker", "error", str(exc))
            processed = False
            if args.once:
                return 2
        finally:
            store.close()
        if args.once:
            return 0
        if not processed:
            time.sleep(max(5, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
