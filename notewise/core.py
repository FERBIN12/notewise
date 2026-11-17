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
The guiding question must NOT repeat the student's question: ask about one smaller step that leads to the answer
(for example a cause, a quantity, or what happens just before). If the notes do not cover it, set in_notes false
and say so in question."""

CLAIM_SYS = """You are a strict fact checker for a student's study notes. You get NOTES and ONE student CLAIM.
Decide if the notes support the claim, contradict it, or do not mention it. A claim is contradicted if ANY part of it
disagrees with the notes (a different place, number, cause, name, or fix). Reply as JSON:
{"verdict": "supported" | "contradicted" | "not_in_notes", "citation": "chunk id", "evidence": "the sentence copied
exactly from the notes", "correction": "what the notes say instead (only if contradicted)"}."""

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
    if mode == "tutor" and out["in_notes"]:
        qt = set(tokens(question))
        def near(c): return len(qt & set(tokens(nb.get(c).heading + " " + nb.get(c).text)))
        # point at the ONE chunk that best matches the question (the model often cites an overview chunk)
        out["citations"] = [max([c.id for c, _ in hits], key=near)]
        gq = str(out.get("question", ""))
        echo = lambda g: not tokens(g) or len(set(tokens(g)) & qt) / max(len(qt), 1) >= 0.6   # restates the student's question
        if echo(gq):
            retry = llm.json_chat(TUTOR_SYS, f"NOTES:\n{context_block(hits)}\n\nCHUNK IDS: {', '.join(c.id for c, _ in hits)}\n\n"
                                  f"QUESTION: {question}\n\nDo not repeat this question. Ask about a smaller step instead.")
            rq = str(retry.get("question", ""))
            if not echo(rq):
                out["question"], out["hint"] = rq, retry.get("hint", out.get("hint", ""))
            else:
                h = nb.get(out["citations"][0]).heading
                out["question"] = f"Before answering, reread your notes on {h}: what happens there step by step?"
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

PAIR_SYS = """Compare two sentences. A is from the student's notes, B is the student's claim.
Answer as JSON {"disagree": true|false, "why": "..."}. disagree is true ONLY if B states a fact that A says is false
(for example a different place, number, direction, cause or method). If B just says less than A, or says the same
thing in other words, disagree is false."""

def _contained(claim: str, text: str) -> float:
    c = set(tokens(claim))
    return len(c & set(tokens(text))) / len(c) if c else 0.0

SENT = re.compile(r"(?<=[.!?])\s+|;\s+|,\s+(?:and|but)\s+")

PRONOUN = re.compile(r"^(it|they|this|these)\s+", re.I)

def split_claims(text: str) -> list[str]:
    """Deterministic split of a student explanation into short claims (sentences, '; ', ', and ', ', but ')."""
    return [c.strip(" .") for c in SENT.split(text.strip()) if len(tokens(c)) >= 2]

def check_understanding(nb: Notebook, llm, topic: str, explanation: str) -> dict:
    """Explain-it-back: every claim is checked on its own against retrieved notes (small models judge one claim
    far better than a whole paragraph), and every verdict must quote evidence that is really in the cited chunk."""
    topic_hits = nb.search(topic + " " + explanation, k=3)
    if not topic_hits:
        return {"covered": [], "missed": [], "wrong": [], "unverified": [], "score": 0, "guard": "retrieval", "sources": {}}
    covered, wrong, unverified, used = [], [], [], {}
    own = nb.search(topic, k=1)   # the chunk about the topic itself always comes first
    for claim in split_claims(explanation):
        # "it makes 30 ATP" -> "Glycolysis makes 30 ATP": a claim cut out of its paragraph keeps its subject
        full = PRONOUN.sub(topic + " ", claim, count=1)
        hits = list({c.id: (c, sc) for c, sc in own + (nb.search(topic + " " + full, k=3) or topic_hits)}.values())[:4]
        allowed = {c.id: c for c, _ in hits}
        out = llm.json_chat(CLAIM_SYS, f"NOTES:\n{context_block(hits)}\n\nCHUNK IDS: {', '.join(allowed)}\n\nCLAIM: {full}")
        verdict, cid, ev = str(out.get("verdict", "")).lower(), _norm(out.get("citation")), str(out.get("evidence", ""))
        chunk = allowed.get(cid)
        ev_ok = bool(chunk) and bool(tokens(ev)) and len(set(tokens(ev)) & set(tokens(chunk.text))) / len(set(tokens(ev))) >= 0.6
        if ev_ok:   # show the real note sentence, never the model's paraphrase of it
            sents = re.split(r"(?<=[.!?])\s+", chunk.text); evt = set(tokens(ev))
            quoted = [x for x in sents if tokens(x) and len(set(tokens(x)) & evt) / len(set(tokens(x))) >= 0.5]
            focus = set(tokens(full + " " + str(out.get("correction", ""))))   # used only to rank real note sentences
            ev = max(quoted or sents, key=lambda x: (len(set(tokens(x)) & focus), len(set(tokens(x)) & evt)))
        if verdict == "supported" and ev_ok:
            covered.append(claim); used[cid] = chunk
        elif verdict == "contradicted" and ev_ok and _contained(claim, chunk.text) < 0.8 \
                and llm.json_chat(PAIR_SYS, f"A: {ev}\nB: {full}").get("disagree") is True:
            wrong.append({"claim": claim, "citation": cid, "evidence": ev}); used[cid] = chunk
        else:
            unverified.append(claim)
    # missed: sentences of the best-matching note chunk that share almost no words with the explanation
    exp = set(tokens(explanation)); top = topic_hits[0][0]; missed = []
    for sent in re.split(r"(?<=[.!?])\s+", top.text):
        st = set(tokens(sent))
        if len(st) >= 3 and len(st & exp) / len(st) < 0.25:
            missed.append({"point": sent, "citation": top.id})
    used.setdefault(top.id, top)
    n = len(covered) + len(wrong) + len(unverified)
    score = round(100 * len(covered) / n) if n else 0
    return {"covered": covered, "missed": missed[:3], "wrong": wrong, "unverified": unverified, "score": score,
            "sources": {c.id: {"heading": c.heading, "lines": c.lines, "text": c.text} for c in used.values()}}
