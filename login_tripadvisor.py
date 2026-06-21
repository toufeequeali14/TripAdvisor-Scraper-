"""
google-chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-debug

"""

import subprocess
import time
import platform


# def launch_chrome():
#     subprocess.Popen([
#         "google-chrome",
#         "--remote-debugging-port=9222",
#         "--user-data-dir=/tmp/chrome-debug",
#         "https://www.tripadvisor.com"
#     ])

#     # Give Chrome time to start
#     time.sleep(5)


def launch_chrome():
    system = platform.system()

    if system == "Linux":
        chrome_cmd = [
            "google-chrome",
            "--remote-debugging-port=9222",
            "--user-data-dir=/tmp/chrome-debug",
            "https://www.tripadvisor.com",
        ]

    elif system == "Windows":
        chrome_cmd = [
            "chrome",
            "--remote-debugging-port=9222",
            "--user-data-dir=%TEMP%\\chrome-debug",
            "https://www.tripadvisor.com",
        ]

    elif system == "Darwin":  # macOS
        chrome_cmd = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "--remote-debugging-port=9222",
            "--user-data-dir=/tmp/chrome-debug",
            "https://www.tripadvisor.com",
        ]

    else:
        raise RuntimeError(f"Unsupported OS: {system}")

    subprocess.Popen(chrome_cmd)

    # Give Chrome time to start
    time.sleep(5)


########

import asyncio
import json
from playwright.async_api import async_playwright


async def save_cookies_from_open_browser(
    output_file="cookies.json",
):
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(
            "http://127.0.0.1:9222"
        )

        contexts = browser.contexts

        if not contexts:
            print("No browser contexts found.")
            return

        context = contexts[0]

        cookies = await context.cookies()

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)

        print(f"Saved {len(cookies)} cookies to {output_file}")


# if __name__ == "__main__":
#     asyncio.run(save_cookies_from_open_browser())

if __name__ == "__main__":
    launch_chrome()

    input(
        "\nChrome opened.\n"
        "Login to TripAdvisor and press ENTER to save cookies..."
    )

    asyncio.run(save_cookies_from_open_browser())










#second way to login
# """
# TripAdvisor Login Helper — Undetected ChromeDriver
# ----------------------------------------------------
# 1. Opens TripAdvisor in an undetected Chrome browser
# 2. You log in manually
# 3. Press Enter in the terminal when done
# 4. Cookies saved to cookies.json (both full format and paste-ready dict)

# Install:
#     pip install undetected-chromedriver selenium
# """

# import json
# import logging
# import time
# from pathlib import Path

# import undetected_chromedriver as uc

# logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# log = logging.getLogger(__name__)

# COOKIES_FILE = "cookies.json"
# TARGET_URL   = "https://www.tripadvisor.com/members/auth/login/"


# def login_and_save_cookies():
#     log.info("Launching undetected Chrome ...")

#     options = uc.ChromeOptions()
#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-dev-shm-usage")
#     options.add_argument("--disable-popup-blocking")
#     options.add_argument("--start-maximized")
#     options.add_argument("--lang=en-US")

#     # Persistent profile — looks more like a real browser,
#     # avoids re-solving CAPTCHAs on every run
#     options.add_argument("--user-data-dir=./chrome_profile")

#     driver = uc.Chrome(
#         options=options,
#         headless=False,
#         use_subprocess=True,   # more stable on Linux
#         version_main=148,
#     )

#     # Extra JS patches on top of what undetected_chromedriver already does
#     driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
#         "source": """
#             Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
#             Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3, 4, 5] });
#             Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
#             window.chrome = { runtime: {} };
#         """
#     })

#     log.info(f"Navigating to {TARGET_URL} ...")
#     driver.get(TARGET_URL)
#     time.sleep(3)

#     print("\n" + "=" * 55)
#     print("  Browser is open. Please log in to TripAdvisor.")
#     print("  When you're fully logged in, come back here")
#     print("  and press Enter to save your cookies.")
#     print("=" * 55 + "\n")

#     input("  ▶  Press Enter after logging in ... ")

#     # Save full Selenium cookie objects
#     cookies = driver.get_cookies()
#     Path(COOKIES_FILE).write_text(
#         json.dumps(cookies, indent=2, ensure_ascii=False),
#         encoding="utf-8",
#     )
#     log.info(f"Saved {len(cookies)} cookies → {COOKIES_FILE}")

#     # Paste-ready dict for the COOKIES var in your scrapers
#     cookie_dict = {c["name"]: c["value"] for c in cookies}
#     print("\n--- Paste-ready dict (for COOKIES in scrapers) ---")
#     print(json.dumps(cookie_dict, indent=2))
#     print("--------------------------------------------------\n")

#     driver.quit()
#     log.info("Done.")


# if __name__ == "__main__":
#     login_and_save_cookies()

