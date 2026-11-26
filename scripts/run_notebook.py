"""Run a notebook's code cells in order without Jupyter, e.g. on the DGX Spark inside tmux.

    python scripts/run_notebook.py pipeline/03_denoise.ipynb
    python scripts/run_notebook.py pipeline/03_denoise.ipynb --set 'USE={"music": "dfn3", "noisy": "dfn3"}'

--set NAME=VALUE replaces the line `NAME = ...` of the cell that first assigns NAME (the config cell) before that cell
runs, so the cell's own checks see the new value. VALUE is Python, e.g. --set 'ONLY=["030"]'.
The working directory is the notebook's folder, as in Jupyter, and that folder is on sys.path, so the notebook can
import the modules next to it (pipeline_paths.py). Figures are saved, not shown (MPLBACKEND=Agg).
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("notebook")
ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
args = ap.parse_args()

nb = Path(args.notebook).resolve()
cells = ["".join(c["source"]) for c in json.load(open(nb, encoding="utf-8"))["cells"] if c["cell_type"] == "code"]
for item in args.set:
    name, sep, value = item.partition("=")
    name = name.strip()
    assert sep and name.isidentifier(), f"--set needs NAME=VALUE, got {item!r}"
    line = re.compile(rf"^{re.escape(name)}\s*=.*$", re.MULTILINE)
    i = next((i for i, c in enumerate(cells) if line.search(c)), None)
    assert i is not None, f"no cell has a line `{name} = ...`"
    cells[i] = line.sub(lambda m: f"{name} = {value}", cells[i], count=1)

os.environ.setdefault("MPLBACKEND", "Agg")
os.chdir(nb.parent)
sys.path.insert(0, str(nb.parent))   # as in Jupyter: modules next to the notebook can be imported


def stamp(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


stamp(f"{nb.name}: {len(cells)} code cells" + "".join(f"\n    --set {s}" for s in args.set))
g = {"__name__": "__main__"}
t0 = time.time()
for i, src in enumerate(cells, 1):
    first = next((l for l in src.splitlines() if l.strip()), "")
    stamp(f"cell {i}/{len(cells)}: {first[:80]}")
    exec(compile(src, f"{nb.name} cell {i}", "exec"), g)
stamp(f"all cells done in {(time.time() - t0) / 60:.1f} min")
