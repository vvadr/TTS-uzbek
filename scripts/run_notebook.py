"""Run a notebook's code cells in order without Jupyter, e.g. on the DGX Spark inside tmux.

    python scripts/run_notebook.py pipeline/03_denoise.ipynb
    python scripts/run_notebook.py pipeline/03_denoise.ipynb --set 'USE={"music": "dfn3", "noisy": "dfn3"}'
    python scripts/run_notebook.py --save pipeline/06_finalize.ipynb

--set NAME=VALUE replaces the line `NAME = ...` of the cell that first assigns NAME (the config cell) before that cell
runs, so the cell's own checks see the new value. VALUE is Python, e.g. --set 'ONLY=["030"]'.
--save writes what every cell prints into the notebook as that cell's output, after each cell, so the notebook shows
the run when you open it (the code itself is not changed; reload the notebook in VS Code if it is open).
The working directory is the notebook's folder, as in Jupyter, and that folder is on sys.path, so the notebook can
import the modules next to it (pipeline_paths.py). Figures are saved, not shown (MPLBACKEND=Agg).
"""
import argparse
import io
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("notebook")
ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
ap.add_argument("--save", action="store_true", help="write the printed output into the notebook")
args = ap.parse_args()

nb = Path(args.notebook).resolve()
book = json.load(open(nb, encoding="utf-8"))
where = [k for k, c in enumerate(book["cells"]) if c["cell_type"] == "code"]   # notebook index of every code cell
cells = ["".join(book["cells"][k]["source"]) for k in where]
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


class Tee(io.TextIOBase):
    """Prints to the terminal and keeps a copy for the notebook."""

    def __init__(self, out):
        self.out, self.buf = out, io.StringIO()

    def write(self, s):
        self.out.write(s)
        self.out.flush()
        return self.buf.write(s)

    def flush(self):
        self.out.flush()


def save(k, text, n, error=None):
    cell = book["cells"][where[k]]
    cell["execution_count"] = n
    cell["outputs"] = []
    if text:
        cell["outputs"].append(dict(output_type="stream", name="stdout", text=text.splitlines(keepends=True)))
    if error:
        cell["outputs"].append(dict(output_type="error", ename=type(error).__name__, evalue=str(error),
                                    traceback=traceback.format_exception(error)))
    tmp = nb.with_name(nb.name + ".tmp")
    tmp.write_text(json.dumps(book, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, nb)


def stamp(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


stamp(f"{nb.name}: {len(cells)} code cells" + "".join(f"\n    --set {s}" for s in args.set))
if args.save:                         # this run's outputs replace the old ones
    for k in where:
        book["cells"][k]["outputs"], book["cells"][k]["execution_count"] = [], None
g = {"__name__": "__main__"}
t0 = time.time()
for i, src in enumerate(cells, 1):
    first = next((l for l in src.splitlines() if l.strip()), "")
    stamp(f"cell {i}/{len(cells)}: {first[:80]}")
    tee = Tee(sys.stdout)
    real, sys.stdout = sys.stdout, tee
    try:
        exec(compile(src, f"{nb.name} cell {i}", "exec"), g)
    except BaseException as e:
        sys.stdout = real
        if args.save:
            save(i - 1, tee.buf.getvalue(), i, e)
        raise
    finally:
        sys.stdout = real
    if args.save:
        save(i - 1, tee.buf.getvalue(), i)
stamp(f"all cells done in {(time.time() - t0) / 60:.1f} min")
