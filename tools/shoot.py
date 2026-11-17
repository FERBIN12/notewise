"""Drive the real UI headless and screenshot it. Usage: shoot.py URL OUTDIR [question...]"""
import sys
from playwright.sync_api import sync_playwright
url, out, qs = sys.argv[1], sys.argv[2], sys.argv[3:]
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--mute-audio"])
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(url); pg.click("#samples"); pg.wait_for_selector(".tab")
    pg.screenshot(path=f"{out}/01_notes.png")
    for i, q in enumerate(qs, 2):
        mode, _, text = q.partition(":")
        pg.click(f'.mode[data-mode="{mode}"]')
        if mode == "check":
            topic, _, text = text.partition("|"); pg.fill("#topic", topic)
        n = pg.locator(".msg.bot").count()
        pg.fill("#q", text); pg.click("#send")
        pg.wait_for_function(f"document.querySelectorAll('.msg.bot:not(.typing)').length > {n}", timeout=600000)
        pg.wait_for_timeout(800)
        pg.screenshot(path=f"{out}/{i:02d}_{mode}.png")
    pg.set_viewport_size({"width": 400, "height": 860}); pg.wait_for_timeout(300)
    pg.screenshot(path=f"{out}/99_mobile.png", full_page=True)
    b.close()
