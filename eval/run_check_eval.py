"""Explain-it-back eval: correct explanations must not be flagged wrong; explanations with a planted error must be caught.
usage: python eval/run_check_eval.py [model] [items.json]
(writes eval/check_results_<model>.json, or check_results_heldout_<model>.json for check_items_heldout.json)"""
import json, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from notewise.core import Notebook, LLM, check_understanding
root = pathlib.Path(__file__).resolve().parents[1]
model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:1.5b"
items = sys.argv[2] if len(sys.argv) > 2 else "eval/check_items.json"
tag = "heldout_" if "heldout" in items else ""
nb = Notebook()
for f in sorted((root / "sample_notes").glob("*.md")): nb.add(f.read_text(), f.name)
llm, rows = LLM(model), []
for item in json.loads((root / items).read_text()):
    t = time.time(); out = check_understanding(nb, llm, item["topic"], item["explanation"]); dt = time.time() - t
    flagged = bool(out["wrong"])
    ok = flagged if item["planted_error"] else not flagged
    rows.append({**item, "ok": ok, "score": out["score"], "wrong": out["wrong"], "missed": out["missed"], "covered": out["covered"], "seconds": round(dt, 2)})
    print("PASS" if ok else "FAIL", item["topic"], "planted" if item["planted_error"] else "correct", "score", out["score"], "wrong", len(out["wrong"]), f"{dt:.1f}s")
p = [r for r in rows if r["planted_error"]]; c = [r for r in rows if not r["planted_error"]]
mean = lambda xs: round(sum(xs) / len(xs), 1) if xs else 0
summary = {"model": model, "planted_errors_caught": f"{sum(r['ok'] for r in p)}/{len(p)}", "correct_not_flagged": f"{sum(r['ok'] for r in c)}/{len(c)}",
           "mean_score_correct": mean([r["score"] for r in c]), "mean_score_planted": mean([r["score"] for r in p])}
print(json.dumps(summary))
(root / f"eval/check_results_{tag}{model.replace(':', '_')}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
