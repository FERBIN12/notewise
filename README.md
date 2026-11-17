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
6. **Explain it back** uses the same retrieval, and every "missed" or "wrong" item must cite a retrieved chunk or
   it is dropped.

## Evaluation (real runs, files in `eval/`)

EVAL_TABLE_PLACEHOLDER

Reproduce: `.venv/bin/python eval/run_eval.py` and `.venv/bin/python eval/run_check_eval.py` (Ollama running).
The note sets in `sample_notes/` (controls, estimation, biology, data structures) were written for this project.

## Limits (honest list)

- A 1.5B model is small: it can still phrase an answer loosely, and the word-overlap support check is a
  heuristic, not proof. The guards make it fail toward "not in your notes", not toward a made-up answer.
- Plain text and markdown notes only (no PDF or handwriting yet). Notes are held in memory and cleared on restart.
- Single user, local only. It is a study aid: check important facts against your course material.

## Tests

`.venv/bin/python -m pytest -q` runs the unit and API tests (they use a fake model, no Ollama needed).

## How it was built

Built with Claude Code (an AI coding agent) directed by Ferbin. The design, the guards and the evaluation numbers
were checked by running the app and the eval scripts; every number above comes from the result files in `eval/`.

## Credits and licenses

- [Ollama](https://github.com/ollama/ollama) (MIT) for local inference.
- [Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct) (Apache-2.0).
- [rank_bm25](https://github.com/dorianbrown/rank_bm25) (Apache-2.0), [FastAPI](https://fastapi.tiangolo.com) (MIT),
  [Uvicorn](https://www.uvicorn.org) (BSD-3-Clause), [HTTPX](https://www.python-httpx.org) (BSD-3-Clause).

Notewise is released under the MIT License (see `LICENSE`).
