"""Drive the local app and save three screenshots. Localhost only."""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
CHIPS = ["spinach", "yogurt", "rice", "garlic", "oil", "tomato", "lemon"]
STARS = ["spinach", "yogurt"]
ATTEMPTS = 3


def base_url():
    explicit = os.environ.get("STILL_GOOD_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    port = os.environ.get("PORT", "8765").strip() or "8765"
    return f"http://127.0.0.1:{port}"


def friend_name():
    return os.environ.get("FRIEND_NAME", "Sathguru").strip() or "Sathguru"


def abort_off_host(route, base):
    if route.request.url.startswith(base):
        route.continue_()
    else:
        route.abort()


def wait_for_settled_note(page):
    previous = page.locator("#model-line").inner_text()
    page.click("#cook")
    page.wait_for_function(
        """(previous) => {
          const status = document.querySelector('#note')?.dataset.noteStatus;
          const meta = document.querySelector('#model-line')?.textContent || '';
          const settled = status === 'gemma' || status === 'fallback';
          return settled && meta !== previous;
        }""",
        arg=previous,
        timeout=330000,
    )


def note_is_accepted(page):
    status = page.get_attribute("#note", "data-note-status")
    if status != "gemma":
        return False
    used = page.inner_text("#used-ingredients")
    if "Spinach" not in used or "Yogurt" not in used:
        return False
    steps = page.locator("#note-steps li")
    if steps.count() != 4:
        return False
    step_text = " ".join(steps.all_inner_texts()).lower()
    if "spinach" not in step_text and "palak" not in step_text:
        return False
    if not any(word in step_text for word in ("yogurt", "yoghurt", "curd", "dahi")):
        return False
    return True


def main():
    base = base_url()
    name = friend_name()
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.route("**/*", lambda route: abort_off_host(route, base))
        page.goto(base + "/", wait_until="domcontentloaded")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("[data-chip=spinach]", timeout=10000)

        page.fill("#friend-name", name)
        page.wait_for_function(
            """(friend) => document.querySelector('#for-name')?.textContent.includes(friend)""",
            arg=name,
        )
        page.get_by_text("Vegetarian", exact=True).click()
        page.get_by_text("Nuts", exact=True).click()
        page.get_by_text("15 min", exact=True).click()
        page.get_by_text("Follow steps", exact=True).click()
        page.screenshot(path=str(OUT / "01-friend-profile.png"), full_page=True)

        for chip in CHIPS:
            page.click(f"[data-chip={chip}]")
        for star in STARS:
            page.click(f"[data-star={star}]")
        page.screenshot(path=str(OUT / "02-fridge.png"), full_page=True)

        accepted = False
        for attempt in range(1, ATTEMPTS + 1):
            wait_for_settled_note(page)
            status = page.get_attribute("#note", "data-note-status")
            print(f"attempt {attempt}: {status}")
            if note_is_accepted(page):
                accepted = True
                break
            print(page.inner_text("#note"))

        if not accepted:
            browser.close()
            sys.exit("Gemma did not return an accepted note that uses the starred foods")

        page.screenshot(path=str(OUT / "03-sticky-note.png"), full_page=True)
        print(page.get_attribute("#note", "data-note-status"))
        print(page.inner_text("#note"))
        browser.close()


if __name__ == "__main__":
    main()
