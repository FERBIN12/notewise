#!/bin/bash
# One GPU turn: both evals + live UI screenshots. Waits for the shared gpu.lock (never kills holders).
cd "$(dirname "$0")/.." || exit 1
exec 9>>"$HOME/.cache/ferbins-world/gpu.lock"
echo "waiting for gpu.lock $(date)"; flock 9; echo "got gpu.lock $(date)"
.venv/bin/python eval/run_eval.py qwen2.5:1.5b
.venv/bin/python eval/run_check_eval.py qwen2.5:1.5b
NOTEWISE_PORT=8765 .venv/bin/python -m notewise.server & SRV=$!
sleep 4
"$HOME/udemy-upload/venv/bin/python" tools/shoot.py http://127.0.0.1:8765 shots \
  "answer:What causes integral windup and how do you fix it?" \
  "answer:What is the capital of Australia?" \
  "tutor:Why does the Krebs cycle turn twice per glucose?" \
  "check:Glycolysis|Glycolysis happens inside the mitochondria and needs oxygen, and it makes about 30 ATP."
kill $SRV; curl -s -XPOST -m 5 http://127.0.0.1:11434/api/generate -d '{"model":"qwen2.5:1.5b","keep_alive":0}' >/dev/null
echo "done $(date)"; touch tools/.gpu_batch_done
