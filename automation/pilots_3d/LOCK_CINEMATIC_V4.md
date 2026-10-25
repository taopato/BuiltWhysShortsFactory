# Lock cinematic pilot (review only)

This experiment is isolated from the BuiltWhys production queue and upload
services. Nothing in this directory schedules or publishes a video.

## Story and causal sequence

1. A person approaches one front door with a key.
2. A close shot follows that key to that door's cylinder.
3. The door shell disappears to reveal the same cylinder as an enlarged
   technical cutaway. The key's notches lift five lower pins independently.
4. Only when each key/driver pin boundary meets the shear line does the plug
   rotate. The key and plug use one rotation control.
5. A bolt retracts from the plug turn parameter; the shell returns and the
   door swings open.

The exterior key and lock are normal sized. The internal cutaway is enlarged
for legibility. This is an illustration of a generic pin-tumbler deadbolt, not
an engineering drawing of a particular commercial product.

## Tools and assets

- Blender 4.3.2, EEVEE, 720 x 1280, 24 fps, 36 s.
- FFmpeg for H.264/AAC final assembly and burnt-in safe-zone captions.
- A locally stored MakeHuman-based rigged character exported from
  [3d-gen](https://github.com/olatunde85/3d-gen). Its project states that the
  shipped MakeHuman assets are CC0. The source application code is MIT. The
  exact character here is the `Athletic man` preset exported to GLB.
- Narration is generated independently of Codex image generation, using the
  installed `edge-tts` client. Production use of any voice service must be
  checked against its current service terms before enabling automation.
- Metallic housing, key, pins, spring curves, bolt, room, lighting, camera,
  animation, score and captions are generated locally by the scripts here.

## Reproduce locally

From the repository root on the pilot workstation:

```powershell
& 'D:\CreatorLab\Tools\blender-4.3.2-windows-x64\blender.exe' --background --factory-startup --python 'automation\pilots_3d\lock_cinematic_v4.py' -- preview
& 'D:\CreatorLab\Tools\blender-4.3.2-windows-x64\blender.exe' --background --factory-startup --python 'automation\pilots_3d\lock_cinematic_v4.py' -- render
python 'automation\pilots_3d\compose_lock_cinematic_v4.py' --compose
```

The render saves individual frames in `D:\CreatorLab\ShortsFactory\pilots\lock-v4\frames\` and
the final review MP4 in `D:\CreatorLab\ShortsFactory\pilots\lock-v4\`. This makes interruption
and resumption possible without rerendering completed frames. The directory is
not a production asset path and lives off the space-constrained C: drive.

## Review gate

Do not integrate or publish this pilot unless the owner explicitly approves
its visual quality, the mechanical explanation, voice/captions, asset and
voice rights, and target-channel fit. Inspect the full MP4 at phone size, not
only still images. No promise of reach or monetization follows from a render.
