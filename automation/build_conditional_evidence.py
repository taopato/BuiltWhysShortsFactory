from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "audit-evidence"
PAGE = (1600, 1100)
FONT_PATH = Path(r"C:\Windows\Fonts\arial.ttf")
BOLD_PATH = Path(r"C:\Windows\Fonts\arialbd.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(BOLD_PATH if bold else FONT_PATH), size)


def text_page() -> Image.Image:
    image = Image.new("RGB", PAGE, "white")
    draw = ImageDraw.Draw(image)
    draw.text((80, 65), "BuiltWhys Publisher - OAuth Flow Evidence", fill="#111827", font=font(46, True))
    blocks = [
        ("OAuth client", "BuiltWhys Publisher (owner-authorized, single-user client)"),
        ("Authorization flow", "Google OAuth 2.0 authorization code flow with refresh-token revalidation."),
        ("Requested scopes", "youtube.upload\nyoutube.readonly\nyt-analytics.readonly"),
        ("Purpose", "Upload owner-approved videos, read the owner's channel/video records, and display owner-authorized YouTube Analytics reports."),
        ("Revocation", "The owner can revoke access at https://security.google.com/settings/security/permissions"),
        ("Data deletion", "https://control.builtwhys.space/data-deletion - credentials and API-derived records are removed as soon as possible and within seven days."),
    ]
    y = 165
    for heading, body in blocks:
        draw.text((85, y), heading, fill="#1f2937", font=font(26, True))
        y += 42
        for paragraph in body.splitlines():
            for line in wrap(paragraph, width=96) or [""]:
                draw.text((105, y), line, fill="#374151", font=font(24))
                y += 34
        y += 22
    draw.text((85, 1010), "No access token, client secret, refresh token, password, or production credential is included.", fill="#991b1b", font=font(22, True))
    return image


def screenshot_page(filename: str, title: str, url: str) -> Image.Image:
    shot = Image.open(EVIDENCE / filename).convert("RGB")
    canvas = Image.new("RGB", PAGE, "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((55, 35), title, fill="#111827", font=font(34, True))
    draw.text((55, 82), f"URL: {url}", fill="#2563eb", font=font(21))
    shot.thumbnail((1490, 920), Image.Resampling.LANCZOS)
    x = (PAGE[0] - shot.width) // 2
    canvas.paste(shot, (x, 135))
    return canvas


def main() -> None:
    pages = [
        text_page(),
        screenshot_page("06-control-center-video-review.png", "Upload and mandatory human-review interface", "https://control.builtwhys.space/"),
        screenshot_page("05-control-center-dashboard.png", "Owner-only dashboard and publishing schedule", "https://control.builtwhys.space/"),
        screenshot_page("04-data-deletion.png", "OAuth revocation and data-deletion instructions", "https://control.builtwhys.space/data-deletion"),
    ]
    output = EVIDENCE / "conditional-evidence.pdf"
    pages[0].save(output, "PDF", resolution=120, save_all=True, append_images=pages[1:])
    print(output)


if __name__ == "__main__":
    main()
