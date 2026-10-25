# YouTube API Services follow-up package

Reply to the existing YouTube API Services email thread within seven business days.

## Email body

Hello YouTube API Services Team,

Thank you for the follow-up. Please find attached a complete screencast demonstrating
the BuiltWhys Publisher API client's upload workflow from human review through the
YouTube Data API upload and the resulting video in YouTube Studio.

YouTube channel:
https://www.youtube.com/channel/UC_owbRSmCX1dtpXXN5VX3MQ

The workflow shown in the recording is:

1. The operator signs in to the private BuiltWhys Control Center.
2. The operator opens a rendered video, previews it, reviews its title, description,
   visibility and target platforms, and explicitly confirms the human review.
3. Only a human-approved video can be placed in the publishing queue.
4. The server-side publisher uses YouTube Data API v3 `videos.insert` with OAuth 2.0
   credentials belonging to the channel owner. It then stores the returned YouTube
   video ID and status.
5. The recording shows the resulting upload in YouTube Studio on the BuiltWhys channel.

The client is used only by the channel owner. It does not expose Google credentials,
does not scrape YouTube, and does not upload a video without explicit human approval.
The privacy policy, terms, and data-deletion pages are available from the Control
Center footer.

Please let me know if you need the source files or any additional demonstration.

Kind regards,
Tarik Cetinturk

## Screencast checklist

Record one continuous video with Windows Snipping Tool screen recording or Xbox Game
Bar. Do not display passwords, OAuth tokens, `.env.automation`, App Secret, or terminal
credentials.

1. Open `https://control.builtwhys.space` and sign in.
2. Open **Video Havuzu > Havuz / onaylananlar**.
3. Open one approved test video and show:
   - video preview;
   - title and description;
   - YouTube selected as a target platform;
   - YouTube visibility set to **Private** for the compliance demonstration;
   - the human-review state.
4. Click **Şimdi yayın kuyruğuna al** and confirm the explicit-consent dialog.
5. Show the Calendar entry becoming due and the platform status changing to published.
6. Open YouTube Studio in the same recording and show the new private video's title,
   upload time and channel identity.
7. Optionally return to Control Center and show the YouTube `yayında` badge.

Upload the recording to Google Drive with viewer access for anyone with the link, or
attach it directly if the email size allows. Reply to the existing thread; do not open
a separate quota request.
