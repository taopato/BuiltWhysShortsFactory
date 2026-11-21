# BuiltWhys 3D factory: evaluated approach (2026-11-22)

This is a design decision, not permission to publish. The current stock-video
producer and scheduled publisher remain unchanged until pilots are accepted.

## Source projects assessed

| Project | Useful part | Decision |
| --- | --- | --- |
| [procedural-anime](https://github.com/kvothesson/procedural-anime) (MIT) | JSON-described shots, deterministic rendering/post effects, frame-anchored sound, draft/contact sheets | Adapt architecture; do not copy its anime visual style or require Blender 5.2 |
| [anim-studio](https://github.com/DvaitAI-tech/anim-studio) (MIT code; third-party assets separately licensed) | Story-to-shot-to-voice-to-mux contract | Learn from schema; do not deploy its GPU/character-focused pipeline to this CPU-only VPS |
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) (BSD-3-Clause) | Shot detection on any external footage | Optional QA if a pilot uses licensed footage; no need in fully rendered thermostat pilot |
| [OpenCLIP](https://github.com/mlfoundations/open_clip) (MIT code; model weights separately licensed) | Semantic frame/text ranking | Optional *advisory* asset check; never a sole pass/fail for factual or aesthetic quality |
| [Blender Python API](https://docs.blender.org/api/current/info_quickstart.html) | Existing Blender 4.3.2 server renderer | Keep and build a constrained, reusable mechanism/room scene library |
| [Poly Haven](https://polyhaven.com/license) (CC0 assets) | Lighting/environment textures | Use selectively with recorded asset provenance, not as a substitute for a relevant model |

Cloudflare Workers AI FLUX image generation can make still/reference art, but
not the timed, physically consistent room/boiler/radiator motion. It is not the
core engine. A chat subscription is not an API allowance.

## Repeatable pipeline

1. Pick an idea only if it has a source-backed claim and a renderable visual
   mechanism. Reject ideas outside the approved scene library.
2. Build a 26–40 second storyboard as timed visual beats. Each line of speech
   names an object/action visible at the same time. Keep source URL per claim.
3. Run storyboard checks, then render **draft frames** (first frame, 1.5 s,
   every shot boundary, and final frame) and a contact sheet. Reject cropping,
   implausible shapes, unreadable text, and missing action before full render.
4. Render on the server, mux voice and frame-anchored SFX, then inspect all
   frames mechanically: resolution, safe margins, black/duplicate frames,
   subtitle overflow, speech/caption timing, loudness and missing audio.
5. Run a second skeptical factual review against original manufacturer or
   engineering sources; quarantine any uncertain claim. An embedding score is
   not proof that the drawing or explanation is correct.
6. Keep an *approval-required* queue for uncertain/novel templates. Consider
   confidence-calibrated auto-publication only after several different
   template pilots and real published outcomes are reviewed by the owner.
   No tool can guarantee that every video meets the owner's aesthetic bar.

## Thermostat pilot

The first pilot is a conventional room thermostat connected to a boiler, not
a modulating OpenTherm thermostat. Verified hook: raising a room thermostat's
setpoint does not make the heating system warm the room faster; it keeps the
call for heat active longer. Source: [Resideo homeowner guide](https://homecomfort-techlit.resideo.com/emeadocuments/pim%20-%20renamed/s42010941-007uk07.pdf).

Visual story: 18°C room -> 22°C setpoint -> thermostat closes heat call ->
boiler heats water -> radiator transfers heat -> room reaches 22°C -> heat
call stops -> compare with 30°C setpoint. Do not imply the thermostat directly
changes flame intensity or that all boilers use identical wiring.

The storyboard is `thermostat_storyboard_v1.json`. A full narrated review MP4
is **not yet produced**. Render no production queue items or uploads from it.
