# BuiltWhys Content Factory Algorithm

This file is the durable operating contract for the content factory. Both the
operator and automation should consult it before expanding channels or languages.

## Channel portfolio

- `builtwhys`: everyday objects, visible design details and their engineering purpose.
- `wildwhys`: animal behaviour, anatomy and adaptation with an observable mechanism.
- `worldwhys`: geography, cities, borders and natural formations using maps and diagrams.

Ideas may never be placed into a channel merely because they are interesting. They
must satisfy that channel's brief and exclusions in `automation/channel_catalog.json`.

## Candidate funnel

1. Generate channel-specific ideas with the local Ollama model.
2. Reject duplicates and ideas outside the selected channel's brief.
3. Check research readiness; require at least two usable research results.
4. Generate six specific English Pexels searches.
5. Query Pexels before rendering; require at least eight unique usable videos and
   at least four of the six searches to return footage.
6. Calculate a preliminary score from channel fit, research readiness and visual
   availability. Discard candidates below 75/100.
7. Queue only the highest-scoring candidates needed to restore that channel's reserve.
8. Produce sequentially, then apply originality and production-quality gates.
9. Keep at least ten publishable videos per active channel when capacity permits.
10. Schedule only videos that pass every gate. Live publishing additionally follows
    the active YouTube API audit commitments and account-specific OAuth state.

## Language order

English is the source story. Turkish is the first localization. A localized version
reuses the licensed visual pack but must have native narration, subtitles, title,
description and tags. Further languages are added only after EN/TR performance data.

## Publishing safety

The system may generate, rank, revise and prepare a schedule without the owner being
online. The current YouTube API audit declares mandatory human approval, so unattended
live publishing remains locked until that declaration is formally changed and accepted.
This constraint must not be silently bypassed.

After Google/YouTube formally accepts an amended unattended-publishing workflow,
the dormant fallback rule may be enabled: if the owner has not acted before the
planning deadline, select only a video that passed policy and production gates,
rank eligible items by originality, technical quality and candidate score, then
assign the highest score to the next empty channel slot. A rejection or revision
request from the owner always overrides this fallback.

## Initial weekly targets

- BuiltWhys EN: active, target 5
- BuiltWhys TR: paused until the operator explicitly activates it
- WildWhys EN: paused until the operator explicitly activates it
- WorldWhys EN: paused until the operator explicitly activates it

The factory may create more candidates than it publishes. Quality yield, not raw CPU
utilization, controls output.
