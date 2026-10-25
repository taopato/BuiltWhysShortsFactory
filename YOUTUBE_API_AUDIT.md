# BuiltWhys YouTube API Compliance Audit

This document is the truthful answer sheet and evidence checklist for the official YouTube API Services audit form.
It is not a quota-increase request and it does not claim guaranteed monetization.

## Project and owner

- API project number/name: use the Google Cloud project shown as `BuiltWhys Publisher`.
- API client name: `BuiltWhys Publisher`.
- Website: `https://control.builtwhys.space/about`
- Privacy policy: `https://control.builtwhys.space/privacy`
- Terms: `https://control.builtwhys.space/terms`
- Data deletion: `https://control.builtwhys.space/data-deletion`
- YouTube channel: `BuiltWhys` (`UC_owbRSmCX1dtpXXN5VX3MQ`).
- Users: one—the channel owner. The Control Center is not offered to third parties.

## Product description

BuiltWhys Publisher is a private, owner-operated production and publishing control panel for original short educational
videos explaining why engineered objects have particular design features. A local model drafts a script from research
seeds. The application records source links and asset licenses, builds a video from six distinct licensed Pexels clips
and at least two project-generated explanatory diagrams, and checks topic, script and stock-asset duplication. The owner
must watch the completed video and explicitly approve it before scheduling. The application then uploads only that
owner-approved video to the owner's BuiltWhys channel and retrieves owner-authorized analytics for the dashboard.

## API use

- YouTube Data API v3: `channels.list`, `videos.insert`, `videos.list`, and `thumbnails.set`.
- YouTube Analytics API: owner-authorized channel/video performance reports.
- OAuth scopes: `youtube.upload`, `youtube.readonly`, and `yt-analytics.readonly`.
- Upload frequency: normally four owner-approved Shorts per week; never bulk spam.
- Expected users: one.
- Expected YouTube uploads: no more than one per day under the current scheduler rule.
- No scraping, view automation, artificial engagement, comment automation or subscriber automation.
- No third-party YouTube content is downloaded or republished.
- Video visibility is explicitly selected per video. Public/unlisted API uploads remain locked in the application until
  YouTube confirms that the compliance audit has been approved.

## Data handling

- OAuth credentials and API-derived records are stored on a private Ubuntu server protected by HTTPS, firewall rules,
  restricted OS access and an authenticated Control Center.
- Authorized data is displayed only to the authorizing owner.
- Data is used only for uploads, duplicate prevention, performance reports and the owner's Drive archive.
- Data is not sold, used for advertising or disclosed to unrelated third parties.
- Authorization is revalidated through refresh-token use. The owner can revoke access through Google security settings.
- A deletion request removes stored OAuth credentials, API-derived channel records and related archives as soon as
  possible and within seven days.

## Evidence to attach

1. Homepage/About screenshot showing the product description, Privacy link and official Developed with YouTube mark.
2. Privacy Policy screenshots showing data accessed, purpose, storage/sharing, retention, Google Privacy Policy,
   YouTube Terms and Google security-settings revocation link.
3. Terms screenshot showing agreement to the YouTube Terms of Service.
4. Data-deletion screenshot showing the revocation and seven-day deletion process.
5. Google OAuth consent screenshots showing the three requested YouTube scopes.
6. Control Center video-detail screenshot showing:
   - originality report,
   - per-video YouTube visibility selector,
   - mandatory full-video human-review checkbox,
   - Approve/Revise/Reject controls.
7. Control Center calendar screenshot showing the limited weekly schedule.
8. Control Center analytics screenshot showing that reports are limited to the owner's channel.

Do not attach access tokens, client secrets, refresh tokens, passwords, `.env.automation`, terminal output containing
credentials, or database files.

## Form wording for the compliance explanation

> The application is a private control panel used only by the owner of the BuiltWhys YouTube channel. It uploads
> original educational Shorts after mandatory human review and retrieves owner-authorized channel analytics. Each
> candidate records research sources and commercial-use asset licenses, uses six distinct Pexels clips plus original
> explanatory diagrams, and is automatically checked for topic, script and media duplication. The owner must watch the
> final render, choose its visibility, and explicitly approve it before scheduling. The system limits publication to one
> video per day and normally schedules four per week. It does not scrape YouTube, download third-party YouTube content,
> automate engagement, or serve third-party users.

## Before submitting

- Keep live publishing disabled until the audit is approved.
- Confirm the OAuth consent screen is in production.
- Confirm the four public policy URLs return HTTPS 200.
- Take fresh screenshots after the current server deployment.
- Use only the official form at `https://support.google.com/youtube/contact/yt_api_form`.
