# Server render feasibility — lock pilot

Measured on 2026-10-25. This is a deliberately isolated smoke test, not a
production deployment or a new publishing path.

## What was tested

- The existing `lock-cinematic-v4.blend` was copied to the BuiltWhys VPS.
- Official Blender 4.3.2 Linux x64 was installed separately from the running
  Docker services; its archive SHA-256 was verified against Blender's release
  checksum. No container was stopped or restarted.
- Three 720x1280 EEVEE frames were rendered headlessly with low process
  priority and `-t 2`.
- Frame 365 rendered in 133.27 seconds. Consecutive frames 366 and 367 rendered
  in 103.75 and 98.67 seconds, respectively. These are per-frame costs, not
  just first-run shader setup.
- The server's frame 365 and the local frame 365 had 55.80 dB average PSNR,
  meaning the outputs are visually very close. The server did not intrinsically
  lower image quality.
- At approximately 100 seconds per frame, 864 frames would consume about
  24 hours of sustained rendering, before scene construction, audio, QA, and
  competing applications. Do not enable this renderer in the production queue
  on the current CPU-only VPS.

## Hardware and storage observed

- 4 shared vCPU, 7.6 GiB RAM, no GPU renderer.
- Roughly 10 GiB free disk before installation, with production workloads
  already running. The pinned Blender binary uses about 1.3 GiB; the smoke
  scene about 147 MiB. The downloaded installer was removed after validation.

## Production design consequence

Build a shot-template library and asset catalog before attempting autonomous
multi-topic production. Keep Blender for selected reusable hero/cutaway shots;
use a lighter, server-friendly motion-graphics compositor for captions,
annotations, diagrams, transitions, and repeated scene grammar. Do not ask a
small local language model to synthesize arbitrary 3D geometry and animation
for unsupported topics. Unsupported topics must fail the production gate rather
than publishing inaccurate or generic visuals.

Measure a full server-rendered sample in the new style, its visual review,
peak RAM, disk use, runtime, and license provenance before connecting it to
the approval pool or publisher.
