from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PILOTS = ROOT / "automation" / "pilots"

TOPICS = {
    "002-train-wheels": (
        "a modern passenger train wheelset with subtly conical steel wheel treads",
        "Show authentic railway engineering, clean unbranded equipment, and make the conical tread shape physically believable.",
    ),
    "003-escalator-grooves": (
        "deep grooves in a clean modern escalator step approaching the landing comb plate",
        "Show accurate interlocking grooves and comb teeth, realistic brushed metal, and a safe empty escalator.",
    ),
    "004-windshield-frit": (
        "the black ceramic frit band and fading dot pattern around a modern car windshield",
        "Make the baked ceramic edge, adhesive region, glass curvature, and dot gradient technically credible.",
    ),
    "005-container-corrugation": (
        "corrugated steel walls and structural frame of an unbranded shipping container",
        "Emphasize how folded steel gains stiffness while keeping realistic industrial geometry and scale.",
    ),
    "006-keyboard-bumps": (
        "the tactile raised bars on the F and J keys of a clean unbranded computer keyboard",
        "Keep the standard QWERTY layout accurate and clearly show how index fingers locate the home row.",
    ),
    "007-soda-can-dome": (
        "the inward domed bottom and circular standing ring of an unbranded aluminum soda can",
        "Show accurate thin aluminum geometry, internal pressure context, and no logos or readable packaging text.",
    ),
    "008-tape-hook": (
        "the sliding metal hook and elongated rivet holes on an unbranded tape measure",
        "Show the tiny intentional hook movement accurately for both inside and outside measurements.",
    ),
}

SHOTS = (
    "Extreme macro hook shot, shallow depth of field, the key design detail immediately obvious.",
    "Wider real-world context shot showing the object being used naturally, hands only if useful.",
    "Low side angle with directional lighting revealing shape, material, depth, and construction.",
    "Top-down or straight-on documentary product photograph with a clearly different composition.",
    "Realistic workshop or engineering inspection scene demonstrating the mechanism in use.",
    "Premium cinematic payoff shot from a new angle, visually striking but still technically accurate.",
)

STYLE = (
    "Create one original photorealistic vertical image for an English educational YouTube Short. "
    "9:16 portrait composition, documentary product photography, crisp subject, cinematic practical lighting, "
    "high detail, natural materials, generous safe space near the lower quarter for subtitles. "
    "No text, captions, letters added by the artist, logos, trademarks, watermarks, collage, split screen, "
    "borders, duplicated objects, or fantastical elements. Do not imitate an existing creator."
)


def generate(api_key: str, model: str, prompt: str) -> bytes:
    encoded_key = urllib.parse.quote(api_key, safe="")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={encoded_key}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": "9:16"},
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini returned HTTP {exc.code}: {detail[:1000]}") from exc

    candidates = result.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidate: {json.dumps(result)[:1000]}")
    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    raise RuntimeError(f"Gemini returned no image data: {json.dumps(result)[:1000]}")


def copy_diagrams(pilot_dir: Path, destination: Path) -> None:
    existing = sorted((pilot_dir / "assets").glob("scene-*.png"))
    diagrams = [path for path in existing if "scene-01" not in path.name]
    if len(diagrams) < 2:
        raise RuntimeError(f"Two existing diagrams are required for {pilot_dir.name}")
    for index, source in enumerate(diagrams[:2], start=7):
        shutil.copy2(source, destination / f"scene-{index:02d}-diagram.png")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the richer BuiltWhys visual batch with Gemini.")
    parser.add_argument("--model", default="gemini-2.5-flash-image")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set. Use run_gemini_images.ps1.")

    for pilot_name, (subject, accuracy) in TOPICS.items():
        pilot_dir = PILOTS / pilot_name
        destination = pilot_dir / "assets-v2"
        destination.mkdir(parents=True, exist_ok=True)
        print(f"\n{pilot_name}: generating six unique photographs", flush=True)
        for index, shot in enumerate(SHOTS, start=1):
            output = destination / f"scene-{index:02d}-photo.png"
            if output.exists() and not args.force:
                print(f"  {output.name}: already exists", flush=True)
                continue
            prompt = f"{STYLE}\n\nSubject: {subject}.\nAccuracy: {accuracy}\nShot: {shot}"
            for attempt in range(1, 4):
                try:
                    image = generate(api_key, args.model, prompt)
                    temporary = output.with_suffix(".tmp")
                    temporary.write_bytes(image)
                    temporary.replace(output)
                    print(f"  {output.name}: generated", flush=True)
                    break
                except Exception as exc:
                    if "limit: 0" in str(exc) or "billing details" in str(exc).lower():
                        raise RuntimeError(
                            "Gemini image quota is zero. Enable paid Gemini API billing for the API-key project, "
                            "then run this command again. No image was generated."
                        ) from exc
                    if attempt == 3:
                        raise
                    print(f"  attempt {attempt} failed: {exc}; retrying", flush=True)
                    time.sleep(attempt * 5)
        copy_diagrams(pilot_dir, destination)
        metadata = {
            "model": args.model,
            "unique_photos": 6,
            "original_diagrams": 2,
            "scene_reuse": 0,
        }
        (destination / "generation.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
    print("\nAll v2 visual packs are ready.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
