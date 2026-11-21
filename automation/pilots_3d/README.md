# BuiltWhys 3D review pilots

These are isolated review renders, not part of the automatic publication queue.
They use original Blender geometry and the English narration already produced
for BuiltWhys train-wheel and escalator stories. No third-party Reel audio or
visual assets are included.

## Render locally

Run `blender --background --python automation/pilots_3d/blender_pilot.py -- train`
and repeat with `escalator`. The script writes PNG frame sequences to
`storage/3d-pilots/`. It uses Blender 5.2's EEVEE renderer, 480×854 at 20 fps.
Composition interpolates to 720×1280 at 30 fps. This is a pilot-quality test;
final production should benchmark native 720×1280 rendering on the server.

Run `python automation/pilots_3d/compose_pilot.py train --source-task-dir <task>`
with a BuiltWhys task containing `audio.mp3` and `subtitle.srt`; repeat for
`escalator`. The composer writes reviewed MP4 files into `storage/3d-pilots/`.

## Before production integration

- Confirm render throughput on the actual server; EEVEE availability there has
  not been verified.
- Replace pilot reuse of existing narration with an appropriately licensed,
  self-hosted TTS model if all production steps must run locally.
- Fact-check each storyboard and inspect opening, middle, and final frames.
- Keep approval and publishing disabled until the owner accepts the pilots.
- Never reuse the reference creator's footage, voice, music, branding, or exact
  composition.

## Multi-shot tape-measure story

`tape_story.py` is a separate, more dynamic pilot. Its 40-second story has six
different 3D sets and ten narrated camera beats: loose hook, outside pull,
inside push, rivet-slot travel, fixed-hook error, and corrected comparison.
It uses the owner's existing English BuiltWhys narration about tape-measure
calibration; no reference creator audio or video is copied.

Render with Blender in background mode using `-- render`, then run
`compose_pilot.py tape --source-task-dir <existing-tape-task>` to create the
review MP4. Only the MP4 is a deliverable; frame sequences are temporary.
`render_review.py` performs both steps and checks that all 810 frames exist and
the completed MP4 decodes. It accepts `--blender-bin`, `--ffmpeg-bin`, and
`--source-task-dir`. It never adds a video to the publishing queue.

This pilot is **not yet a server automation**. The current production image
does not include Blender and the producer worker still uses the stock-video
pipeline. A supported template catalog, server render worker, voice generation
input, quality gate, Control Center preview, and publisher handoff must be
tested on the server before any 3D jobs can be published autonomously.

## Pin-tumbler lock story

`lock_story.py` is an independently modeled, simplified educational cutaway.
It shows the wrong key leaving pins across the shear line, the matching key
aligning five pin-pair seams, the plug turning, and a cam retracting a bolt.
It explains ordinary key operation, not lock bypass. Its geometry, camera
movement, lights, titles, and mechanism sounds are original to this project.

Run `blender --background --python automation/pilots_3d/lock_story.py -- render`
to create 600 frames, then run `python automation/pilots_3d/compose_lock.py`.
The resulting `builtwhys-lock-3d-pilot.mp4` is an English **visual review
pilot**, with English on-screen explanatory text and synthetic mechanism sound,
but **no spoken narration**. The isolated local renderer could not access a
suitable TTS voice; do not treat this as release-ready audio or queue it for
publication. Before server integration, generate an original English voiceover
through the existing voice service or a suitable self-hosted TTS, align it to
the beats, verify technical accuracy and phone-screen readability, and obtain
owner approval. No server worker or publishing behavior is changed here.

## Revised lock pilot (2026-10-25)

`lock_realistic_story.py` and `compose_lock_realistic.py` are the second,
independent review version. The original `lock_story.py` and `compose_lock.py`
remain intact. The revised output is
`storage/3d-pilots/builtwhys-lock-realistic-pilot.mp4`: 24 seconds, 720x1280,
English on-screen text, original mechanical effects, **no narration**.

Its keyway, cutaway cylinder, five pin pairs, springs, cam and bolt are
illustrative geometry, not verified lock CAD. The key-entry-to-pin-lift causal
sequence still needs a continuous, readable close-up. See
`docs/LOCK_PILOT_REVIEW_TR.md` and `docs/BUILTWHYS_ARCHITECTURE_TR.md` for the
assessment and pipeline diagrams. This pilot does not satisfy current
production delivery gates and must not be auto-published.

## Controlled revival pilot (2026-11-21)

`story_contract.py` validates the sourced, 30-second `lock_storyboard_v5.json`
and `seatbelt_storyboard_v1.json` before any render. It rejects missing sources,
overlong/repeated-action beats, narration that cannot fit the beat, and unsupported templates.
It does **not** prove factual or visual quality; both still require review.

`lock_causal_shot_v5.py` creates a new five-second cutaway where the moving
key's actual notch height at each chamber determines the rise of that pin
pair. The camera shows the key and pins together. Run Blender with
`--python automation/pilots_3d/lock_causal_shot_v5.py -- build --out DIR`, then
render the saved `.blend` with `render_range.py -- --start 1 --end 120 --step 1
--samples 8 --out DIR/frames`. `compose_lock_v5.py` replaces seconds 10.1–15.1
of the prior 36-second human/door review pilot with this new shot while keeping
the original English narration. The resulting MP4 is a **review candidate**,
not a new production format or an approved upload. The seat-belt pilot currently
has a storyboard but no modeled scene or MP4.

Measured on the CPU-only VPS with low process priority: the new, simpler
cutaway frame took about 8 seconds at 720×1280/8 EEVEE samples and about 68 MB
peak scene memory. A complete five-second shot therefore needs roughly
15–20 minutes, subject to server load. The much heavier v4 scene took 15.45
seconds/frame even at 8 samples. Use short 3D shots, not 30–40 seconds of
continuous full-resolution rendering, until a full-pilot benchmark is complete.

On 2026-11-22 the physical-profile shot completed all 120 server-rendered
frames in 911.36 seconds. The assembled review MP4 is at
`/opt/builtwhys/storage/3d-pilots/lock-causal-v5-final2/lock-causal-hybrid-v5-review.mp4`
on the server and under `D:/CreatorLab/ShortsFactory/pilots/lock-v5/` locally.
It is 36.02 seconds, 720×1280, 24 fps, H.264/AAC; complete decode and
black-frame check passed. The human/door scene and new cutaway still have
different art directions, so this is not approved for publication. The
seat-belt pilot remains a storyboard only.
