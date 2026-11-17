# Notewise

**A study tutor that only answers from your own notes, shows you the exact lines it used, and says
"that is not in your notes" instead of guessing.**

Students paste lecture notes into a chatbot and get confident answers that are partly from the notes and partly
made up, with no way to tell which part is which. Notewise is built the other way round:

- **Ask**: every answer cites the note passages it came from. Click a citation and the notes panel scrolls to those
  lines and highlights them.
- **Tutor me**: instead of the answer, you get one guiding question and a hint about where in your notes to look.
- **Explain it back**: write what you think a topic means. Notewise compares it with your notes and lists what you
  got, what you missed and which claims contradict your notes, each linked to the lines that show why.
- **Private by design**: the model runs locally through [Ollama](https://ollama.com) (default `qwen2.5:1.5b`), and notes are
  kept in memory on your machine. Nothing is sent to a cloud API.

## Screenshots (real app, local qwen2.5:1.5b)

![Grounded answer with the cited lines highlighted](https://github.com/FERBIN12/notewise/releases/download/media-v1/answer.png)

![Explain it back: two planted errors flagged, each with the note sentence that shows why](https://github.com/FERBIN12/notewise/releases/download/media-v1/check.png)

## Setup (3 commands)

Needs Python 3.10+ and Ollama.

```bash
ollama pull qwen2.5:1.5b
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m notewise.server          # open http://127.0.0.1:8000, click "Load sample notes"
```

Settings (environment variables): `NOTEWISE_MODEL` (any Ollama model), `OLLAMA_HOST`, `NOTEWISE_PORT`.

## How it works

1. **Chunking** (`notewise/core.py`): notes are split on markdown headings and paragraphs, and every chunk keeps
   its file name and line range, so a citation can point at real lines.
2. **Retrieval**: BM25 (`rank_bm25.BM25Plus`) over the chunks. A chunk that shares no word with the question is
   never treated as evidence.
3. **Guard 1, retrieval**: if no chunk scores above a threshold, Notewise answers "That is not in your notes"
   without calling the model at all.
4. **Generation**: the local model gets only the retrieved chunks and their ids and must reply in JSON
   (`in_notes`, `answer`, `citations`). Temperature 0, fixed seed.
5. **Guard 2, citations**: citation ids that were not in the retrieved set are dropped. A citation is kept only if
   its chunk really contains a good share of the answer's words (small models over-cite). If no citation survives,
   the answer is withheld and the student is told it could not be grounded.
6. **Explain it back** splits the student's explanation into short claims and checks each one on its own: the
   model must say supported / contradicted / not in notes and quote the note sentence it used. A verdict whose
   quote is not really in the cited chunk is ignored. "Contradicted" also needs a second, narrower check (do these
   two sentences disagree on a fact?) and is never given for a claim whose words are almost all in the notes.
   Claims nobody could verify are listed as "Could not check", and the score is the share of claims supported.

## Evaluation (real runs, files in `eval/`)

**Grounded Q&A** (`eval/questions.json`: 28 questions answerable from the notes, 16 that are not):

| Model | Answerable, right chunk cited | Not in notes, correctly refused | Median time |
|---|---|---|---|
| qwen2.5:1.5b (default) | 25/28 | 15/16 | 0.71 s |
| qwen2.5:3b (optional) | 26/28 | 16/16 | 0.88 s |

**Explain it back** (`eval/check_items.json`: 6 correct explanations, 6 with a planted factual error):

| Model | Planted errors caught | Correct explanations not flagged | Mean score, correct | Mean score, planted |
|---|---|---|---|---|
| qwen2.5:1.5b (default) | 4/6 | 5/6 | 64.0 | 0.0 |
| qwen2.5:3b (optional) | 4/6 | 6/6 | 94.5 | 0.0 |

**Explain it back, held-out set** (`eval/check_items_heldout.json`: 12 new items on other topics, written after the
tuning above and run once, with no changes made after seeing the results):

| Model | Planted errors caught | Correct explanations not flagged | Mean score, correct | Mean score, planted |
|---|---|---|---|---|
| qwen2.5:1.5b (default) | 5/6 | 5/6 | 41.7 | 0.0 |
| qwen2.5:3b (optional) | 4/6 | 5/6 | 83.3 | 16.7 |

On the held-out set the 1.5B model is cautious: it catches most errors but often cannot verify correct claims either
(they land in "Could not check", hence the low scores). The 3B model scores correct explanations higher, but once it
accepted a wrong claim (R large means trust the measurement) as "You got". So a wrong claim can slip through:
the check helps you find mistakes, it does not prove an explanation right.

Times are on a laptop RTX 4050 GPU. In the tuning set no claim from a planted explanation was marked "You got": the uncaught ones
landed in "Could not check", which is why planted explanations score 0 with both models. The first version of explain-it-back
judged the whole paragraph in one prompt and caught **0/6** planted errors (the small model just restated the notes),
which is why it now checks one claim at a time. The eval set is small and the claim checker was tuned while looking at these same 12 items, so these numbers are
likely optimistic: treat them as a sanity check, not a benchmark.

Reproduce: `.venv/bin/python eval/run_eval.py`, `.venv/bin/python eval/run_check_eval.py` and
`.venv/bin/python eval/run_check_eval.py qwen2.5:1.5b eval/check_items_heldout.json` (Ollama running).
The note sets in `sample_notes/` (controls, estimation, biology, data structures) were written for this project.

## Limits (honest list)

- A 1.5B model is small: it misses some planted errors (see the table) and can still phrase an answer loosely, and the word-overlap support check is a
  heuristic, not proof. The guards make it fail toward "not in your notes", not toward a made-up answer.
- Tutor mode with the 1.5B model sometimes hints too strongly (a guiding question can name part of the answer).
  If its question just repeats yours, Notewise retries once and then falls back to pointing you at the right section.
- Plain text and markdown notes only (no PDF or handwriting yet). Notes are held in memory and cleared on restart.
- Single user, local only. It is a study aid: check important facts against your course material.

## Tests

`.venv/bin/python -m pytest -q` runs the unit and API tests (they use a fake model, no Ollama needed).

## How it was built

Built with Claude Code (an AI coding agent) directed by Ferbin. The design, the guards and the evaluation numbers
were checked by running the app and the eval scripts; every number above comes from the result files in `eval/`.

## Credits and licenses

- [Ollama](https://github.com/ollama/ollama) (MIT) for local inference.
- [Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct) (Apache-2.0), the default model.
- Optional: [Qwen2.5-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct) is under the Qwen Research
  License (non-commercial). Notewise does not ship it; if you pull it yourself, run with `NOTEWISE_MODEL=qwen2.5:3b`.
- [rank_bm25](https://github.com/dorianbrown/rank_bm25) (Apache-2.0), [FastAPI](https://fastapi.tiangolo.com) (MIT),
  [Uvicorn](https://www.uvicorn.org) (BSD-3-Clause), [HTTPX](https://www.python-httpx.org) (BSD-3-Clause).

Notewise is released under the MIT License (see `LICENSE`).
