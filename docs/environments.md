# Environments, models and servers

## DGX Spark (`ssh intern@192.168.1.88`, project at `~/projects/tts`)
- aarch64, NVIDIA GB10, CUDA 13.1, 119 GB of memory that CPU and GPU share.
- **Shared.** Other people's jobs run on the same GPU, for example a 26 GB Gemma notebook kernel of the same user account and another user's TTS training. Check `nvidia-smi` before heavy runs. Shut down notebook kernels you no longer need: each idle kernel keeps its models in GPU memory.
- An external T7 SSD is mounted by another user, and `intern` can't write to it.
- `uv` is at `~/.local/bin/uv`. Long runs go inside `tmux`, so they survive a closed terminal.

### `.venv-denoise` (Python 3.11): notebooks 00, 02, 03, 04, 05
Made with:
```
uv venv .venv-denoise --python 3.11
uv pip install --python .venv-denoise/bin/python --extra-index-url https://download.pytorch.org/whl/cu130 \
  --index-strategy unsafe-best-match "torch==2.14.1+cu130" "torchaudio==2.11.0+cu130" "numpy<2" \
  deepfilternet clearvoice "transformers<5" ipykernel matplotlib tqdm silero-vad librosa
```
- **numpy < 2**, because DeepFilterNet and ClearerVoice pin it. Pin torch, torchaudio and numpy whenever you add a package, for example with `uv pip freeze > constraints.txt` and `-c constraints.txt`. The full package list from 2026-11-26 is in `backups/2026-11-26_venv-denoise/freeze.txt`.
- torch 2.5 doesn't support the GB10, so it's 2.14.1+cu130. torchaudio 2.11 no longer has `torchaudio.backend`; 03 stubs `torchaudio.backend.common` so that DeepFilterNet imports.
- **No pip inside the venv.** After `source .venv-denoise/bin/activate`, `pip` is conda base's. Use `uv pip install --python .venv-denoise/bin/python ...`.
- pyannote.audio 3.4 is installed but fails to import under torchaudio 2.11, so don't use it here.

### `.venv-nemo` (Python 3.12): notebooks 01 and 06
Made with:
```
uv venv .venv-nemo --python 3.12
uv pip install --python .venv-nemo/bin/python --extra-index-url https://download.pytorch.org/whl/cu130 \
  --index-strategy unsafe-best-match "torch==2.14.1+cu130" "torchaudio==2.11.0+cu130" \
  "nemo-toolkit[asr] @ git+https://github.com/NVIDIA/NeMo.git@f47ddde246380a250bd868b51b4a7f3a2f3770f3" \
  ipykernel matplotlib soundfile
uv pip install --python .venv-nemo/bin/python pyloudnorm dover-lap
```
- NeMo needs Python ≥ 3.12, so it can't go into `.venv-denoise` (a dry run proved that). The commit is the same as the Mac's `pyproject.toml`.
- This env also runs MMS (transformers 5.x), TitaNet, `torchaudio.functional.forced_align`, pyloudnorm and DOVER-Lap.

### VS Code
VS Code finds both venvs: Select Kernel → Python Environments. Each notebook's metadata names its kernel. When a script has rewritten a notebook (`run_notebook.py --save`), reload it with "File: Revert File" before you edit it, so you don't save the old copy over it.

## Mac
- The project `.venv` (`uv sync`): Python 3.12, NeMo at the same commit, torch 2.15 (MPS). It can run 01; the rest runs on the Spark.
- New YouTube audio: `scripts/download_48k.py`, with the separate `stt_data_collection` project's venv, cookies and PO token server (`make pot-up`, Docker). It writes 48 kHz mono wavs; copy them to the Spark's `data/raw_audios/`. That project's own downloader writes 24 kHz, which this pipeline refuses.

## Models
| Used in | Model | Where it comes from |
|---|---|---|
| 01 | `nvidia/Nemotron-3-Diarization`, `nvidia/diar_streaming_sortformer_4spk-v2`, `-v2.1` | Hugging Face, no login |
| 01 | `vad_multilingual_marblenet`, `titanet_large` (NeMo `ClusteringDiarizer`) | NVIDIA NGC, no login; config in `pipeline/configs/diar_infer_general.yaml` (from the NeMo repo at the same commit) |
| 02 | fine-tuned Whisper (CTranslate2) | the ASR servers, `http://192.168.1.71:8201` and `:8199` |
| 03 | AST `MIT/ast-finetuned-audioset-10-10-0.4593` (music detection), DeepFilterNet3, MossFormer2_SE_48K (ClearerVoice, 212 MB; 03 moves it to the GPU itself, because ClearVoice cannot read the GB10's free memory and picks the CPU) | HF / pip / `~/.cache/clearvoice` |
| 04 | Silero VAD | pip package |
| 05, 06 | `facebook/mms-1b-all` + `uzb-script_latin` adapter (forced alignment, 20 ms frames) | HF |
| 05 | AST (laugh / cough / breath), Vocal Burst Locator v2 `laion/vocalburst-locator` `model_v2.pt` | HF |
| 06 | TitaNet-large `nvidia/speakerverification_en_titanet_large` | HF |

Not available: pyannote `speaker-diarization-3.1` and `community-1` are gated behind a Hugging Face login, which the Spark doesn't have.

## ASR server
Two servers with the same API (FastAPI "Faster Whisper API" 1.6.0, 4 workers, `POST /jobs`, `GET /jobs/{id}`, `GET /health`), both reporting `model_path: /models/ft_model`:
- `http://192.168.1.71:8201`, the first choice (the user's instruction of 2026-11-27);
- `http://192.168.1.71:8199`, the backup.

02 sends every chunk with `language=uz` to the first server that answers `/health` with `ready`. A job that fails is sent again, `TRIES` (3) times per server, then to the next one; 02 prints how many chunks each server transcribed. When other people's jobs fill a queue, 02 waits. Details: `src/transcribe.md`.

**Known faults (2026-11-27):**
- Jobs can fail with `parallel_for failed: cudaErrorInvalidDevice: invalid device ordinal` while `/health` still says `ready`: 8199 failed every job from 12:32 to 14:20, and 8201 failed 3 of 8 jobs at 14:32.
- The two give almost the same text: on 12 test chunks, 7 were identical and 5 differed by a period or one word (8201 `Diqqat bering`, 8199 `Diqqat bering.`).
- `scripts/wait_for_asr.sh` waits until one of them works.
