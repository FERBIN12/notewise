"""Grounding eval: answerable questions must cite the right chunk; unanswerable ones must say 'not in your notes'.
usage: python eval/run_eval.py [model]   (writes eval/results_<model>.json; numbers in the README come from these files)"""
import json, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from notewise.core import Notebook, LLM, ask
root = pathlib.Path(__file__).resolve().parents[1]
model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:1.5b"
nb = Notebook()
for f in sorted((root / "sample_notes").glob("*.md")): nb.add(f.read_text(), f.name)
llm, rows = LLM(model), []
for item in json.loads((root / "eval/questions.json").read_text()):
    t = time.time(); out = ask(nb, llm, item["q"]); dt = time.time() - t
    if item["answerable"]:
        ok = out["in_notes"] and item["expect"] in out["citations"]
    else:
        ok = not out["in_notes"]
    rows.append({**item, "ok": ok, "in_notes": out["in_notes"], "citations": out["citations"], "guard": out.get("guard"),
                 "answer": out.get("answer"), "seconds": round(dt, 2)})
    print(("PASS" if ok else "FAIL"), item["q"], "->", out["citations"], out.get("guard") or "", f"{dt:.1f}s")
a = [r for r in rows if r["answerable"]]; u = [r for r in rows if not r["answerable"]]
summary = {"model": model, "answerable_correct_citation": f"{sum(r['ok'] for r in a)}/{len(a)}",
           "unanswerable_abstained": f"{sum(r['ok'] for r in u)}/{len(u)}",
           "median_seconds": sorted(r["seconds"] for r in rows)[len(rows) // 2]}
print(json.dumps(summary))
(root / f"eval/results_{model.replace(':', '_')}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
