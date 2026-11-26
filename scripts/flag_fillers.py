"""Flag the chunks whose transcript has a filler (hm, a-a, ee, mhm, ...) and copy their wavs into a review folder.

    python scripts/flag_fillers.py                       # dataset_clean -> outputs/fillers
    python scripts/flag_fillers.py --dataset dataset --out outputs/fillers_dataset

Writes <out>/filler_only/ (the transcript is nothing but fillers), <out>/has_filler/ (fillers among words) and
<out>/fillers.json. The dataset itself is not changed. Only fillers that are written in the text are found here;
fillers that are spoken but not written need the audio (see the notes in the conversation / a later notebook).
"""
import argparse
import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path

# Non-word sounds only. Real words that also work as fillers (mana, ya'ni, endi, demak, ha, u, a) are not counted.
FILLER = re.compile(r"(?<![\w'])(?:h+m+|x+m+|m{2,}|m+h+m+|a+(?:-a+)+|a{3,}|e+(?:-e+)*h*|u+h+m*|u+m+|u{3,}|a+ha+)(?![\w'])",
                    re.IGNORECASE)


def fillers(text):
    return [m.group(0).lower() for m in FILLER.finditer(text)]


def only_fillers(text):
    return not re.sub(r"[^\w']+", " ", FILLER.sub(" ", text)).strip()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="dataset_clean")
    ap.add_argument("--out", default="outputs/fillers")
    args = ap.parse_args()
    root = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists())
    ds, out = root / args.dataset, root / args.out
    chunks = json.load(open(ds / "metadata.json", encoding="utf-8"))["chunks"]

    rows = []
    for c in chunks:
        f = fillers(c["text"])
        if f:
            rows.append(dict(file=c["file"], category="filler_only" if only_fillers(c["text"]) else "has_filler",
                             fillers=f, text=c["text"], speaker=c["speaker"], duration=c["duration"],
                             denoised=c.get("denoised", "")))
    for d in ("filler_only", "has_filler"):
        shutil.rmtree(out / d, ignore_errors=True)
        (out / d).mkdir(parents=True)
    for r in rows:
        shutil.copy2(ds / r["file"], out / r["category"] / Path(r["file"]).name)
    tmp = out / "fillers.json.tmp"
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, out / "fillers.json")

    cat = Counter(r["category"] for r in rows)
    print(f"{args.dataset}: {len(chunks)} chunks; with a written filler: {len(rows)} "
          f"({sum(r['duration'] for r in rows) / 3600:.2f} h)")
    for k in ("filler_only", "has_filler"):
        print(f"  {k:12} {cat[k]:5d} chunks -> {out / k}")
    print("fillers:", Counter(f for r in rows for f in r["fillers"]).most_common())
