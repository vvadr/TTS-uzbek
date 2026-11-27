#!/usr/bin/env bash
# Run the pipeline notebooks headless, one after another, each with its own kernel, and save what every cell prints
# into the notebook (so it shows the run when opened). For the DGX Spark; start it inside tmux:
#
#   tmux new -s pipeline
#   scripts/run_pipeline.sh              # 01 to 06
#   scripts/run_pipeline.sh 03 04 05     # only these steps
#
# Logs: <run folder>/logs/<step>.log (the run folder is set by RUN in pipeline/pipeline_paths.py).
# It stops at the first step that fails.
set -euo pipefail
cd "$(dirname "$0")/.."

kernel() {   # NeMo needs Python 3.12 (.venv-nemo); the denoise models need numpy < 2 (.venv-denoise)
  case "$1" in
    01|06) echo .venv-nemo ;;
    *) echo .venv-denoise ;;
  esac
}

steps=("$@")
[ ${#steps[@]} -eq 0 ] && steps=(01 02 03 04 05 06)
base=$(.venv-denoise/bin/python -c "import sys; sys.path.insert(0, 'pipeline'); import pipeline_paths as P; print(P.BASE)")
mkdir -p "$base/logs"
for s in "${steps[@]}"; do
  nb=$(ls pipeline/"$s"_*.ipynb)
  k=$(kernel "$s")
  echo "[$(date '+%F %T')] $nb  ($k)  log: $base/logs/$s.log"
  if ! "$k/bin/python" scripts/run_notebook.py --save "$nb" > "$base/logs/$s.log" 2>&1; then
    echo "[$(date '+%F %T')] FAILED: $nb, see $base/logs/$s.log"
    exit 1
  fi
done
echo "[$(date '+%F %T')] done: ${steps[*]}"
