# Uzbek TTS dataset

Builds a text-to-speech training set in Uzbek (Latin script) from YouTube podcasts and videos: diarization → chunks → transcription → denoising → filler removal → sentence chunks → checks → `dataset_train/` (48 kHz from input to output, one loudness, `train.txt` / `val.txt`).

- **Start here:** `AGENTS.md`, for the overview, machines, environments and rules.
- **How to run:** `pipeline/README.md`. The notebooks are in `pipeline/`, numbered in run order; they run on the DGX Spark.
- **Docs:** `docs/pipeline.md` (each step), `docs/data.md` (folders and formats), `docs/environments.md` (venvs, models, the ASR server), `docs/history.md` (decisions), `docs/results.md` (what the runs produced), `docs/changes.md` (the latest changes, in short).

## Getting audio
- **New YouTube audio at 48 kHz:** `scripts/download_48k.py` (run it with the `stt_data_collection` venv; see its header), then copy the wavs to `data/raw_audios/` on the Spark. The pipeline needs 48 kHz input.
- Older audio was downloaded with the separate `stt_data_collection` project and moved to `data/raw_audios/` on the Spark.
- The old download notebooks (`01_download_ytdlp.ipynb`, `01_download_pytubefix.ipynb`) were removed in commit `10a61e5`; they are still in the git history.
- If you already have podcast folders in `data/podcasts/`, run `python scripts/move_podcast_audios.py` (add `--dry-run` to preview). It names each wav from the folder's YouTube id and the title in `data/podcasts.md`.

## Mac setup
```bash
uv sync      # Python 3.12, NeMo, torch; ffmpeg must be on PATH
```
The Spark needs two separate venvs; see `docs/environments.md`.
