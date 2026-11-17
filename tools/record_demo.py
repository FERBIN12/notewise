"""Record the real Notewise UI with Playwright's video recorder and log caption timings.
Usage: record_demo.py URL OUTDIR   -> OUTDIR/raw.webm + OUTDIR/captions.json ([start_s, end_s, text])
Every answer on screen is produced live by the local model during the recording (nothing scripted on the bot side)."""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
caps, t0 = [], None


def cap(text):
    now = time.monotonic() - t0
    if caps and caps[-1][1] is None:
        caps[-1][1] = now
    caps.append([now, None, text])


def send(pg, mode, text, topic=None, hold=5000):
    pg.click(f'.mode[data-mode="{mode}"]'); pg.wait_for_timeout(600)
    if topic:
        pg.fill("#topic", ""); pg.type("#topic", topic, delay=40)
    n = pg.locator(".msg.bot:not(.typing)").count()
    pg.type("#q", text, delay=28); pg.wait_for_timeout(400)
    pg.click("#send")
    pg.wait_for_function(f"document.querySelectorAll('.msg.bot:not(.typing)').length > {n}", timeout=600000)
    pg.wait_for_timeout(hold)


with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--mute-audio"])
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, record_video_dir=str(out),
                        record_video_size={"width": 1440, "height": 900})
    t0 = time.monotonic()
    pg = ctx.new_page()
    pg.goto(url); pg.wait_for_timeout(1500)
    cap("Notewise answers only from YOUR notes. Start by loading notes (here: 4 sample files).")
    pg.wait_for_timeout(2500)
    pg.click("#samples"); pg.wait_for_selector(".tab"); pg.wait_for_timeout(3500)

    cap("Ask mode: a real question, answered live by a local model (qwen2.5:1.5b on Ollama).")
    send(pg, "answer", "What causes integral windup and how do you fix it?", hold=2500)
    cap("Every answer cites file + line range. The cited lines are highlighted in the notes panel.")
    pg.wait_for_timeout(3500)
    pg.locator(".msg.bot .cite").last.click(); pg.wait_for_timeout(3500)

    cap("Not in your notes? It says so instead of guessing.")
    send(pg, "answer", "What is the capital of Australia?", hold=5500)

    cap("Tutor me: no answer, just a guiding question and where to look in your notes.")
    send(pg, "tutor", "Why does the Krebs cycle turn twice per glucose?", hold=7000)

    cap("Explain it back: this explanation has planted errors (wrong place, wrong ATP count).")
    send(pg, "check", "Glycolysis happens inside the mitochondria and needs oxygen, and it makes about 30 ATP.",
         topic="Glycolysis", hold=2500)
    cap("Each claim is checked on its own. Contradictions show the exact note sentence that disagrees.")
    pg.wait_for_timeout(5000)
    pg.locator("#log").evaluate("e => e.scrollTop = e.scrollHeight"); pg.wait_for_timeout(4000)

    cap("A correct explanation of the same topic, for comparison.")
    send(pg, "check", "Glycolysis happens in the cytoplasm, splits glucose into two pyruvate and does not need oxygen.",
         topic="Glycolysis", hold=7000)
    caps[-1][1] = time.monotonic() - t0
    video = pg.video
    ctx.close(); b.close()
    Path(video.path()).rename(out / "raw.webm")

json.dump(caps, open(out / "captions.json", "w"), indent=1)
print("ok", out / "raw.webm", f"{caps[-1][1]:.1f}s")
