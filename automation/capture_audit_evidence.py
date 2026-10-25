from __future__ import annotations

import os
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


OUT = Path(__file__).resolve().parents[1] / "audit-evidence"
BASE = "https://control.builtwhys.space"


def main() -> None:
    session = os.environ["BUILTWHYS_AUDIT_SESSION"]
    OUT.mkdir(parents=True, exist_ok=True)
    options = Options()
    options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1100")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--force-device-scale-factor=1")
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(f"{BASE}/login")
        driver.add_cookie({
            "name": "builtwhys_session",
            "value": session,
            "domain": "control.builtwhys.space",
            "path": "/",
            "secure": True,
            "httpOnly": True,
        })
        driver.get(BASE)
        time.sleep(4)
        driver.save_screenshot(str(OUT / "05-control-center-dashboard.png"))

        driver.get(f"{BASE}/?video=36123445f3b8")
        time.sleep(5)
        driver.save_screenshot(str(OUT / "06-control-center-video-review.png"))
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
