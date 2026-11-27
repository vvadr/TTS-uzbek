# AGENTS.md: Uzbek TTS dataset project

Read this first. Details are in `docs/`. Keep it current: when something here stops being true, fix it here.

## What this project is
This repo builds a **text-to-speech training dataset in Uzbek (Latin script)** from YouTube podcasts and videos. Long recordings go in; short, clean, transcribed, single-speaker chunks come out.
- Language: Uzbek, Latin alphabet (`o'`, `g'` written with the ASCII apostrophe). Speakers code-switch into Russian and English words, written in Latin letters.
- Sources: about 30 podcasts (the main dataset, 38 h after cleaning) plus test runs on new audio (`runs/<name>/`).
- Goal: the training set `dataset_train/` with 48 kHz wavs (48 kHz from input to output, never resampled), one loudness, numbers written as words, speakers consistent across podcasts, and `train.txt` / `val.txt` manifests (`chunks/x.wav|text|speaker`).

## Machines
| Machine | Role |
|---|---|
| **Mac** (this checkout) | Editing, git, and small tests. The project `.venv` (Python 3.12, NeMo) can run diarization. The main dataset's raw audio and the 02 outputs live here. |
| **DGX Spark** `ssh intern@192.168.1.88`, `~/projects/tts` | Where the pipeline runs: aarch64, NVIDIA GB10 GPU, CUDA 13, 119 GB unified memory. **The GPU is shared** with other people's jobs (for example a 26 GB Gemma kernel). |
| **ASR servers** `http://192.168.1.71:8201` (first) and `:8199` (backup) | Fine-tuned Whisper (CTranslate2) behind a FastAPI job queue, the same API on both ports. 02 sends chunks to 8201, and a job that fails there goes to 8199. See `docs/environments.md`. |

## The pipeline (`pipeline/`, run in order)
| # | Notebook | Kernel (Spark) | Makes |
|---|---|---|---|
| 00 | `00_video_to_wav` | any | `data/raw_audios/*.wav` from `data/videos/` (only for video sources) |
| 01 | `01_diarization` | `.venv-nemo` | `outputs/diarization/<audio>/<system>/`: 4 diarization systems (Nemotron, 2 Sortformer versions, TitaNet clustering) plus a DOVER-Lap `consensus` for comparison |
| 02 | `02_chunk_transcribe` | `.venv-denoise` | `dataset/`: speaker turns, then chunks (≤ 29.5 s), transcribed by the ASR server, at 48 kHz |
| 03 | `03_denoise` | `.venv-denoise` | `dataset_clean/`: music chunks through MossFormer2_SE_48K, noisy ones through DeepFilterNet3 (both 48 kHz) |
| 04 | `04_remove_non_speech` | `.venv-denoise` | removes chunks without speech from `dataset_clean/` in place (Silero VAD) |
| 05 | `05_remove_fillers` | `.venv-denoise` | `dataset_nofillers/` (fillers, laughs, coughs cut out of audio and text), then `dataset_final/` (sentence chunks) |
| 06 | `06_finalize` | `.venv-nemo` | **`dataset_train/`**: diarization check against all systems, numbers as words, text/audio match, speakers, loudness, 48 kHz, manifests |

- **Paths:** every notebook takes its paths from `pipeline/pipeline_paths.py`. `RUN = None` is the old (24 kHz) main dataset in the project root; `RUN = "main48k"` is the full dataset at 48 kHz in `runs/main48k/` (33 audios, 2026-11-27); `RUN = "test"` is the 2-audio test run in `runs/test/`. `AUDIOS` picks the input wavs, and `DIARIZATION` picks the diarization 02 cuts by (`"nemotron"`); 06 checks every chunk against the other systems.
- **Run headless on the Spark**, inside tmux: `scripts/run_pipeline.sh [01 02 ...]`. It picks each notebook's kernel and writes the printed output into the notebooks. Logs go to `<run folder>/logs/`.
- **One notebook:** `<venv>/bin/python scripts/run_notebook.py [--save] [--set NAME=VALUE] pipeline/NN_*.ipynb`.
- **Steps resume.** Expensive results are cached, for example `analysis.json`, `words.json`, `text.json` and `speakers.npz`, so a rerun only does what is missing or stale.

## Environments (Spark)
- `.venv-denoise`: Python 3.11, torch 2.14.1+cu130, numpy 1.26 (DeepFilterNet and ClearerVoice need numpy < 2), transformers 4.57, silero-vad. Used for 00 and 02–05.
- `.venv-nemo`: Python 3.12 (NeMo needs ≥ 3.12), torch 2.14.1+cu130, NeMo at git `f47ddde24` (the same commit as the Mac), transformers 5.x, pyloudnorm, dover-lap. Used for 01 and 06.
- **Install with uv, never pip:** `~/.local/bin/uv pip install --python <venv>/bin/python ...`. Inside an activated venv, `pip` points at conda base. Pin torch, torchaudio and numpy so they are not upgraded.
- Models are cached in `~/.cache/huggingface` (shared with other people's projects; delete only this project's models) and `~/.cache/clearvoice`. pyannote models need a Hugging Face login, which the Spark doesn't have.
- Full install commands: `docs/environments.md`.

## Rules for agents
- **48 kHz from input to output.** The input wavs must be 48 kHz: 01 and 02 stop on any other rate (`P.check_sample_rate`). No step resamples the audio it keeps; models that need 16 kHz (diarization, VAD, MMS, TitaNet, AST) get a copy. Get YouTube audio with `scripts/download_48k.py` (Opus at 48 kHz). The `stt_data_collection` downloader writes 24 kHz on purpose, for its own corpus: don't use its wavs, and don't change its config.
- **Don't touch the main dataset by accident.** Test new audio with `RUN = "<name>"`. Chunk names repeat across runs (`001_0000_speaker_0.wav`), so a run pointed at the main folders can overwrite them. 03's step 4 deletes wavs that its metadata doesn't list.
- **Back up before overwriting** notebooks, datasets or venvs (`~/projects/tts/backups/<date>_<what>/` on the Spark). Do self-tests in temporary folders that you delete afterwards, never in the real outputs.
- **Before anything heavy, say so first.** A model run over real audio, GPU work, or anything longer than a couple of minutes: say what runs, on how much data, for how long, and why. By default the user writes and runs the heavy steps themselves; on 2026-11-27 they asked for the whole test run to be run for them.
- Use real chunks from the dataset for examples, not synthetic audio.
- The audio is real people's voices. Keep datasets private and never upload them anywhere public. Don't put the user's personal details into requests to outside services.
- Notebook style: plain, short comments; settings in one config cell; every step prints counts and hours; reviews are written as `index.html` pages with players.
- Files that are not in git: `data/`, `outputs/`, `dataset*/`, `runs/`, `.venv*` (see `.gitignore`). Commit only when asked.

## Where to read more
- `docs/pipeline.md`: every step, what it drops or fixes and why, settings, timings.
- `docs/data.md`: folder layout and the `metadata.json` / manifest formats.
- `docs/environments.md`: venvs, install commands, models, the ASR server.
- `docs/history.md`: decisions, what was tried and rejected, and why.
- `docs/results.md`: what each run produced (chunks and hours per stage).
- `docs/changes.md`: the changes of 2026-11-27 in short, with code.
- `pipeline/README.md`: the short how-to-run.
