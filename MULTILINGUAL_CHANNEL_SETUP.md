# BuiltWhys multilingual rollout

## Operating rule

English remains the source story. A localized job reuses the licensed visual pack,
but creates native-language narration, subtitles, title, description and hashtags.
Rendering is strictly sequential on the current 4-vCPU/8-GB server.

Every language version must pass the originality and production-quality gates and
must be watched and approved by the owner. Automatic scoring may prioritize the
review queue, but it never replaces human approval.

## Prepared profiles

| Language | YouTube | Instagram | Facebook | State |
|---|---|---|---|---|
| English | BuiltWhys | @builtwhys | BuiltWhys | Connected |
| Turkish | BuiltWhys Türkçe / BuiltWhys TR | @builtwhys.tr (subject to availability) | BuiltWhys Türkçe | Owner must create and authorize |

## Turkish OAuth variables

The application selects credentials by job language. Turkish credentials use:

- `GOOGLE_CLIENT_ID_TR`
- `GOOGLE_CLIENT_SECRET_TR`
- `GOOGLE_REFRESH_TOKEN_TR`
- `META_PAGE_ACCESS_TOKEN_TR`
- `META_PAGE_ID_TR`
- `META_IG_USER_ID_TR`

Never store social-media passwords in the project or Control Center. OAuth tokens
belong only in the server's protected `.env.automation` file.

## Expansion order

1. Prove a repeatable English format and collect retention data.
2. Create and review one Turkish pilot from the best English story.
3. Connect the Turkish profiles and publish at a conservative cadence.
4. Add another language only after the first two channels have enough performance
   data to justify it. Each YouTube channel qualifies for monetization separately.
