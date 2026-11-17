"""Notewise core: chunk notes, BM25 retrieval, grounded answers with checked citations, tutor + understanding check."""
from __future__ import annotations
import json, re
from dataclasses import dataclass, field
from rank_bm25 import BM25Plus   # BM25Okapi gives idf 0 on tiny note sets

TOKEN = re.compile(r"[a-z0-9]+")
STOP = set("the a an of to in and or is are was were be for on with as by at it this that from what how why which who"
           " do does did can could should would will i my me you your we our there their its into than then when where".split())

def tokens(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]

@dataclass
class Chunk:
    id: str
    source: str
    heading: str
    text: str
    lines: tuple[int, int]

def chunk_notes(text: str, source: str, max_words: int = 120) -> list[Chunk]:
    """Split on markdown headings and blank lines, pack paragraphs up to max_words, keep line ranges for citations."""
    chunks, heading, buf, start = [], "", [], None
    lines = text.splitlines()
    last = 0
    def flush(_end=None):
        nonlocal buf, start
        end = last
        body = " ".join(" ".join(buf).split())
        if body:
            chunks.append(Chunk(f"{source}#{len(chunks) + 1}", source, heading, body, (start, end)))
        buf, start = [], None
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            flush(i - 1); heading = s.lstrip("#").strip(); continue
        if not s:
            if buf and sum(len(b.split()) for b in buf) >= max_words // 2: flush(i - 1)
            continue
        if start is None: start = i
        buf.append(s); last = i
        if sum(len(b.split()) for b in buf) >= max_words: flush(i)
    flush(len(lines))
    return chunks

@dataclass
class Notebook:
    chunks: list[Chunk] = field(default_factory=list)
    _bm25: BM25Plus | None = None
    _toks: list[set[str]] = field(default_factory=list)

    def add(self, text: str, source: str):
        self.chunks += chunk_notes(text, source)
        docs = [tokens(c.heading + " " + c.text) for c in self.chunks]
        self._bm25, self._toks = BM25Plus(docs), [set(d) for d in docs]

    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]:
        if not self.chunks: return []
        q = tokens(query); qs = set(q)
        scores = self._bm25.get_scores(q)
        ranked = sorted(((c, float(s), len(qs & t)) for c, s, t in zip(self.chunks, scores, self._toks)), key=lambda x: -x[1])
        return [(c, s) for c, s, overlap in ranked if overlap > 0][:k]   # a chunk sharing no word with the question is not evidence

    def get(self, cid: str) -> Chunk | None:
        return next((c for c in self.chunks if c.id == cid), None)

def context_block(hits) -> str:
    return "\n\n".join(f"[{c.id}] ({c.heading})\n{c.text}" for c, _ in hits)

ASK_SYS = """You are Notewise, a study tutor. Answer ONLY from the student's notes given below.
Reply as JSON: {"in_notes": true|false, "answer": "...", "citations": [chunk ids]}.
Citations must be copied exactly from the chunk ids in square brackets, e.g. "controls.md#2".
If the notes do not contain the answer, set in_notes false, answer "That is not in your notes.", citations [].
Every fact in the answer must come from a cited chunk. Keep it under 120 words."""

TUTOR_SYS = """You are Notewise in tutor mode. Do NOT give the final answer. Using ONLY the student's notes below,
reply as JSON: {"in_notes": true|false, "question": "one guiding question that leads the student toward the answer",
"hint": "a small hint pointing to where in the notes to look", "citations": [chunk ids]}.
Citations must be copied exactly from the chunk ids in square brackets, e.g. "controls.md#2".
If the notes do not cover it, set in_notes false and say so in question."""

CHECK_SYS = """You are Notewise checking a student's understanding. Compare the student's explanation with the notes below.
Reply as JSON: {"covered": ["key point the student got right", ...], "missed": [{"point": "...", "citation": chunk id}, ...],
"wrong": [{"claim": "student claim that contradicts the notes", "citation": chunk id}, ...], "score": 0-100}.
Use only the notes. Be encouraging but exact."""

class LLM:
    """Ollama chat client (local model, notes never leave the machine)."""
    def __init__(self, model="qwen2.5:1.5b", host="http://127.0.0.1:11434"):
        self.model, self.host = model, host
    def json_chat(self, system: str, user: str) -> dict:
        import httpx
        r = httpx.post(f"{self.host}/api/chat", timeout=180, json={"model": self.model, "stream": False, "format": "json",
            "options": {"temperature": 0, "seed": 7}, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        r.raise_for_status()
        try: return json.loads(r.json()["message"]["content"])
        except json.JSONDecodeError: return {}

def _norm(cid) -> str:
    return cid.strip().strip("[]()").strip() if isinstance(cid, str) else ""

def _valid_citations(cites, hits) -> list[str]:
    allowed = {c.id for c, _ in hits}
    if isinstance(cites, str): cites = [cites]
    out = [_norm(c) for c in (cites or [])]
    return list(dict.fromkeys(c for c in out if c in allowed))

def supported(answer: str, cites: list[str], nb: "Notebook", min_frac: float = 0.3) -> list[str]:
    """Keep only citations whose chunk actually contains a good share of the answer's words (small models over-cite)."""
    a = set(tokens(answer))
    if not a: return []
    frac = {c: len(a & set(tokens(nb.get(c).text))) / len(a) for c in cites if nb.get(c)}
    return [c for c in cites if frac.get(c, 0) >= min_frac]

MIN_SCORE = 1.0   # below this BM25 score the notes do not really talk about the question

def ask(nb: Notebook, llm, question: str, mode: str = "answer") -> dict:
    hits = nb.search(question)
    if not hits or hits[0][1] < MIN_SCORE:
        return {"in_notes": False, "answer": "That is not in your notes.", "citations": [], "guard": "retrieval"}
    out = llm.json_chat(TUTOR_SYS if mode == "tutor" else ASK_SYS, f"NOTES:\n{context_block(hits)}\n\nCHUNK IDS: {', '.join(c.id for c, _ in hits)}\n\nQUESTION: {question}")
    out["citations"] = _valid_citations(out.get("citations"), hits)
    out["in_notes"] = bool(out.get("in_notes"))
    if mode != "tutor" and out["in_notes"]:
        ans = str(out.get("answer", ""))
        out["citations"] = supported(ans, out["citations"], nb)
        if not out["citations"]:   # model forgot or mangled ids: attribute by checking which retrieved chunk supports it
            out["citations"] = supported(ans, [c.id for c, _ in hits], nb, min_frac=0.4)[:2]
            if out["citations"]: out["attributed"] = "support-check"
    if out["in_notes"] and not out["citations"]:      # a claim with no valid source is not shown as grounded
        out = {"in_notes": False, "answer": "I could not ground an answer in your notes.", "citations": [], "guard": "citation"}
    out["sources"] = [{"id": c.id, "heading": c.heading, "lines": c.lines, "text": c.text} for c, _ in hits if c.id in out["citations"]]
    return out

def check_understanding(nb: Notebook, llm, topic: str, explanation: str) -> dict:
    hits = nb.search(topic + " " + explanation, k=5)
    if not hits:
        return {"covered": [], "missed": [], "wrong": [], "score": 0, "guard": "retrieval"}
    out = llm.json_chat(CHECK_SYS, f"NOTES:\n{context_block(hits)}\n\nCHUNK IDS: {', '.join(c.id for c, _ in hits)}\n\nTOPIC: {topic}\nSTUDENT EXPLANATION: {explanation}")
    allowed = {c.id for c, _ in hits}
    for key in ("missed", "wrong"):
        out[key] = [{**m, "citation": _norm(m.get("citation"))} for m in out.get(key, []) if isinstance(m, dict) and _norm(m.get("citation")) in allowed]
    out.setdefault("covered", []); out["score"] = int(out.get("score", 0) or 0)
    out["sources"] = {c.id: {"heading": c.heading, "lines": c.lines, "text": c.text} for c, _ in hits}
    return out
