"""Compose the demo: title card + captioned live recording + results card + end card. Usage: build_video.py VIDEODIR"""
import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
d = Path(sys.argv[1]); W, H, BAR = 1440, 1000, 100
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def card(name, title, lines):
    im = Image.new("RGB", (W, H), (250, 248, 242)); g = ImageDraw.Draw(im)
    g.text((110, 120), title, font=ImageFont.truetype(FB, 58), fill=(31, 58, 95)); y = 250
    for ln in lines:
        f = ImageFont.truetype(FB if ln.startswith("*") else F, 32); ln = ln.lstrip("*")
        g.text((110, y), ln, font=f, fill=(40, 40, 40)); y += 58 if ln else 30
    im.save(d / f"{name}.png")
card("c0", "Notewise", ["A study tutor that answers only from your own notes,", "shows the exact lines it used, and says",
     "\"that is not in your notes\" instead of guessing.", "", "Runs on a laptop: local model qwen2.5:1.5b via Ollama.",
     "Notes never leave your machine.", "", "Everything in this video is the real app, recorded live.",
     "Built by Ferbin Richard with Claude Code (an AI coding agent)."])
card("c1", "Measured, not claimed", ["*Grounded Q&A (28 answerable, 16 not in notes), qwen2.5:1.5b:",
     "25/28 cite the right passage, 15/16 correctly refused, median 0.71 s", "",
     "*Explain it back, held-out set (12 new items, run once, no tuning after):",
     "5/6 planted errors caught, 5/6 correct explanations not flagged", "",
     "Small eval sets: a sanity check, not a benchmark.", "A wrong claim can still slip through: the check helps you",
     "find mistakes, it does not prove an explanation right.", "Times on a laptop RTX 4050."])
card("c2", "Try it", ["github.com/FERBIN12/notewise  (MIT license)", "", "ollama pull qwen2.5:1.5b",
     "python -m venv .venv && .venv/bin/pip install -r requirements.txt", ".venv/bin/python -m notewise.server", "",
     "Credits: Ollama, Qwen2.5 (Apache-2.0), rank_bm25, FastAPI.", "Built with Claude Code (AI coding agent) directed by Ferbin.",
     "Captions only, no voice."])
def ts(s): return f"{int(s//3600)}:{int(s%3600//60):02d}:{s%60:05.2f}"
caps = json.load(open(d / "captions.json"))
ass = ["[Script Info]", "PlayResX: 1440", "PlayResY: 1000", "", "[V4+ Styles]",
       "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Alignment, MarginV, BorderStyle, Outline, Shadow",
       "Style: C,DejaVu Sans,34,&H00FFFFFF,&H00000000,&H00000000,0,2,30,1,0,0", "", "[Events]",
       "Format: Layer, Start, End, Style, Text"]
ass += [f"Dialogue: 0,{ts(a)},{ts(b)},C,{t}" for a, b, t in caps]
(d / "caps.ass").write_text("\n".join(ass) + "\n")
run = lambda *a: subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)
enc = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-crf", "20"]
for c, sec in (("c0", 7), ("c1", 12), ("c2", 10)):
    run("-loop", "1", "-t", str(sec), "-i", str(d / f"{c}.png"), "-vf", "fade=in:0:15", *enc, str(d / f"{c}.mp4"))
run("-i", str(d / "raw.webm"), "-vf", f"scale={W}:900,pad={W}:{H}:0:0:color=0x1f3a5f,ass={d/'caps.ass'}", *enc, str(d / "live.mp4"))
(d / "list.txt").write_text("".join(f"file '{n}.mp4'\n" for n in ("c0", "live", "c1", "c2")))
run("-f", "concat", "-safe", "0", "-i", str(d / "list.txt"), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
    "-shortest", *enc, "-c:a", "aac", str(d / "notewise_demo.mp4"))
print("ok", d / "notewise_demo.mp4")
