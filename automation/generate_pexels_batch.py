from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PILOTS = ROOT / "automation" / "pilots"
PEXELS_API = "https://api.pexels.com/v1/videos/search"
USED_LEDGER = ROOT / "storage" / "pexels_used_ids.json"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

QUERIES = {
    "002-train-wheels": ["train wheels railway", "passenger train track", "train axle maintenance", "railway curve train", "train undercarriage", "railway engineering"],
    "003-escalator-grooves": ["escalator steps close up", "moving escalator", "escalator maintenance", "shopping mall escalator", "escalator landing", "escalator mechanism"],
    "004-windshield-frit": ["car windshield close up", "auto glass installation", "windshield factory", "driving through windshield", "car glass detail", "automotive glass"],
    "005-container-corrugation": ["shipping container wall", "cargo containers port", "corrugated steel", "container crane", "shipping yard containers", "freight container close up"],
    "006-keyboard-bumps": ["keyboard close up", "hands typing keyboard", "touch typing", "computer keys macro", "office keyboard", "typing fingers macro"],
    "007-soda-can-dome": ["aluminum soda can", "soda can close up", "beverage can factory", "opening soda can", "canned drinks", "aluminum can production"],
    "008-tape-hook": ["tape measure close up", "measuring wood", "carpenter tape measure", "construction measurement", "measuring wall", "tape measure workshop"],
}


def api_json(api_key: str, query: str) -> dict[str, Any]:
    params = urllib.parse.urlencode({"query": query, "orientation": "portrait", "size": "medium", "per_page": 30})
    request = urllib.request.Request(
        f"{PEXELS_API}?{params}",
        headers={"Authorization": api_key, "User-Agent": "BuiltWhys/1.0"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def choose_video(data: dict[str, Any], used_ids: set[int]) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    for video in data.get("videos") or []:
        video_id = int(video.get("id") or 0)
        if not video_id or video_id in used_ids or float(video.get("duration") or 0) < 5:
            continue
        for media in video.get("video_files") or []:
            if media.get("file_type") != "video/mp4" or not media.get("link"):
                continue
            width, height = int(media.get("width") or 0), int(media.get("height") or 0)
            if min(width, height) < 720:
                continue
            portrait_bonus = 10_000_000 if height > width else 0
            target_penalty = abs(width - 1080) + abs(height - 1920)
            exact_size_bonus = 5_000_000 if (width, height) == (1080, 1920) else 0
            practical_size_bonus = 2_000_000 if width <= 1440 and height <= 2560 else 0
            score = (
                portrait_bonus
                + exact_size_bonus
                + practical_size_bonus
                + min(width * height, 2_500_000)
                - target_penalty * 1000
            )
            candidates.append((score, video, media))
    if not candidates:
        raise RuntimeError("Pexels returned no unused clip with acceptable resolution")
    _, video, media = max(candidates, key=lambda item: item[0])
    return video, media


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "BuiltWhys/1.0"})
    temporary = destination.with_suffix(destination.suffix + ".part")
    normalized = destination.with_suffix(".normalized.mp4")
    with urllib.request.urlopen(request, timeout=240) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output)
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(temporary)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded Pexels clip is invalid: {result.stderr.strip()}")
    transcode = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(temporary),
            "-t", "8", "-vf",
            "scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1",
            "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart",
            "-y", str(normalized),
        ],
        capture_output=True,
        text=True,
    )
    temporary.unlink(missing_ok=True)
    if transcode.returncode != 0:
        normalized.unlink(missing_ok=True)
        raise RuntimeError(f"Pexels normalization failed: {transcode.stderr.strip()}")
    normalized.replace(destination)


def local_asset(pilot_name: str, path: Path, asset_type: str, license_text: str) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    asset: dict[str, Any] = {
        "type": asset_type,
        "source_url": f"local://{relative}",
        "license": license_text,
        "commercial_use": True,
    }
    if asset_type == "ai_generated_image":
        asset["generation_status"] = "generated"
    return asset


def main() -> int:
    parser = argparse.ArgumentParser(description="Build eight-scene visual packs from free Pexels footage.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--pilot", help="Generate only one pilot visual pack")
    args = parser.parse_args()
    api_key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("PEXELS_API_KEY is missing. Use run_pexels_assets.ps1.")

    try:
        used_history = [int(item) for item in json.loads(USED_LEDGER.read_text(encoding="utf-8"))]
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        used_history = []
    used_ids: set[int] = set(used_history[-120:])
    if args.pilot:
        pilot_path = PILOTS / args.pilot
        query_path = pilot_path / "pexels_queries.json"
        if args.pilot in QUERIES:
            pilot_queries = QUERIES[args.pilot]
        elif query_path.is_file():
            pilot_queries = json.loads(query_path.read_text(encoding="utf-8"))
        else:
            raise RuntimeError(f"No Pexels query plan found for {args.pilot}")
        if not isinstance(pilot_queries, list) or len(pilot_queries) < 6:
            raise RuntimeError("Pexels query plan must contain at least six searches")
        selected = {args.pilot: [str(item) for item in pilot_queries[:6]]}
    else:
        selected = QUERIES
    for pilot_name, queries in selected.items():
        pilot = PILOTS / pilot_name
        source_assets = pilot / "assets"
        destination = pilot / "assets-v3"
        destination.mkdir(parents=True, exist_ok=True)
        original_manifest = json.loads((pilot / "manifest.json").read_text(encoding="utf-8"))

        # Forced visual revisions exclude the clips used by the previous pack.
        for previous in destination.glob("scene-*-pexels.json") if args.force else ():
            try:
                used_ids.add(int(json.loads(previous.read_text(encoding="utf-8"))["pexels_id"]))
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                pass

        originals = sorted(source_assets.glob("scene-*.png"))
        if len(originals) < 3:
            raise RuntimeError(f"Expected one hero and two diagrams in {source_assets}")
        manifest_assets: list[dict[str, Any]] = []

        print(f"\n{pilot_name}: downloading six distinct Pexels clips", flush=True)
        for index, query in enumerate(queries, start=1):
            output = destination / f"scene-{index:02d}-pexels.mp4"
            metadata_file = destination / f"scene-{index:02d}-pexels.json"
            if output.exists() and metadata_file.exists() and not args.force:
                metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
                used_ids.add(int(metadata["pexels_id"]))
                print(f"  {output.name}: already exists", flush=True)
            else:
                video, media = choose_video(api_json(api_key, query), used_ids)
                download(str(media["link"]), output)
                metadata = {
                    "pexels_id": int(video["id"]),
                    "query": query,
                    "source_url": video.get("url", ""),
                    "contributor": (video.get("user") or {}).get("name", "Pexels contributor"),
                    "contributor_url": (video.get("user") or {}).get("url", ""),
                    "width": media.get("width"),
                    "height": media.get("height"),
                }
                metadata_file.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
                used_ids.add(int(video["id"]))
                print(f"  {output.name}: {query} / {metadata['contributor']}", flush=True)
            manifest_assets.append({
                "type": "stock_video",
                "pexels_id": metadata["pexels_id"],
                "search_query": metadata["query"],
                "source_url": metadata["source_url"],
                "license": "Pexels License; edited as part of an original educational video",
                "commercial_use": True,
                "contributor": metadata["contributor"],
                "contributor_url": metadata["contributor_url"],
                "local_file": output.relative_to(ROOT).as_posix(),
            })

        for index, source in enumerate(originals[1:3], start=7):
            diagram = destination / f"scene-{index:02d}-diagram.png"
            shutil.copy2(source, diagram)
            manifest_assets.append(local_asset(pilot_name, diagram, "procedural_diagram", "Project-generated original diagram"))

        manifest_v3 = dict(original_manifest)
        manifest_v3["assets"] = manifest_assets
        manifest_v3["visual_strategy"] = "six distinct Pexels clips and two original technical diagrams; stock-first, no scene reuse, no global zoom"
        (pilot / "manifest-v3.json").write_text(json.dumps(manifest_v3, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    USED_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    merged_history = (used_history + [item for item in used_ids if item not in used_history])[-120:]
    USED_LEDGER.write_text(json.dumps(merged_history, indent=2) + "\n", encoding="utf-8")
    print("\nAll free Pexels visual packs are ready.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
