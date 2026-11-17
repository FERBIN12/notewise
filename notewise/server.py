"""Notewise web server: paste or upload notes, ask grounded questions, tutor mode, explain-it-back check.

Run: python -m notewise.server   (then open http://127.0.0.1:8000)
Everything stays on this machine: notes are held in memory, the model runs in a local Ollama.
"""
from __future__ import annotations
import contextlib, fcntl, os, threading
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .core import LLM, Notebook, ask, check_understanding

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
SAMPLES = ROOT.parent / "sample_notes"
MAX_NOTE_CHARS = 400_000

app = FastAPI(title="Notewise")
_lock = threading.Lock()
state = {"nb": Notebook(), "files": {}}
llm = LLM(model=os.environ.get("NOTEWISE_MODEL", "qwen2.5:1.5b"), host=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"))


@contextlib.contextmanager
def gpu_turn():
    """Optional: wait for a shared GPU lock file (NOTEWISE_GPU_LOCK) so the model does not fight other GPU jobs."""
    path = os.environ.get("NOTEWISE_GPU_LOCK")
    if not path:
        yield; return
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try: yield
        finally: fcntl.flock(f, fcntl.LOCK_UN)


class NoteIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=MAX_NOTE_CHARS)

class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: str = "answer"

class CheckIn(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    explanation: str = Field(min_length=1, max_length=5000)


def _rebuild():
    nb = Notebook()
    for name, text in state["files"].items():
        nb.add(text, name)
    state["nb"] = nb


def _summary():
    nb = state["nb"]
    return {"files": [{"name": n, "chunks": sum(c.source == n for c in nb.chunks), "lines": t.count("\n") + 1, "text": t}
                      for n, t in state["files"].items()], "chunks": len(nb.chunks)}


@app.get("/api/notes")
def get_notes():
    return _summary()

@app.post("/api/notes")
def add_note(note: NoteIn):
    name = Path(note.name).name.replace("#", "_")   # '#' separates file and chunk number in citation ids
    with _lock:
        state["files"][name] = note.text
        _rebuild()
    return _summary()

@app.delete("/api/notes/{name}")
def del_note(name: str):
    with _lock:
        if state["files"].pop(name, None) is None:
            raise HTTPException(404, "no such note")
        _rebuild()
    return _summary()

@app.post("/api/samples")
def load_samples():
    with _lock:
        for p in sorted(SAMPLES.glob("*.md")):
            state["files"][p.name] = p.read_text()
        _rebuild()
    return _summary()

@app.post("/api/ask")
def api_ask(q: AskIn):
    if q.mode not in ("answer", "tutor"):
        raise HTTPException(400, "mode must be answer or tutor")
    if not state["nb"].chunks:
        raise HTTPException(400, "add some notes first")
    with gpu_turn():
        return ask(state["nb"], llm, q.question, q.mode)

@app.post("/api/check")
def api_check(c: CheckIn):
    if not state["nb"].chunks:
        raise HTTPException(400, "add some notes first")
    with gpu_turn():
        return check_understanding(state["nb"], llm, c.topic, c.explanation)

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")

app.mount("/static", StaticFiles(directory=STATIC), name="static")


def main():
    import uvicorn
    uvicorn.run(app, host=os.environ.get("NOTEWISE_HOST", "127.0.0.1"), port=int(os.environ.get("NOTEWISE_PORT", "8000")))

if __name__ == "__main__":
    main()
