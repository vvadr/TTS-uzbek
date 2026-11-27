# Pipeline: raw audio -> training dataset

Run the notebooks in this order. `pipeline_paths.py` sets where they read and write:
- `RUN = "test"` puts everything in `runs/test/`; `RUN = None` is the main dataset in the project root.
- `AUDIOS` picks the wavs of `data/raw_audios/`.
- `DIARIZATION` is the diarization 02 cuts by (`"nemotron"`).

**48 kHz only:** the input wavs must be 48 kHz (01 and 02 stop otherwise), and no step resamples the audio. Get YouTube audio with `scripts/download_48k.py`.

Every notebook prints its folder first. Details per step: `docs/pipeline.md`.

| # | notebook | where (kernel) | makes, in the run folder |
|---|---|---|---|
| 00 | `00_video_to_wav` | anywhere; only if you start from videos | `data/raw_audios/*.wav` from `data/videos/` |
| 01 | `01_diarization` | Spark (**`.venv-nemo`**) | `outputs/diarization/<audio>/<system>/`: Nemotron (the reference), Sortformer v2 and v2.1, guided TitaNet clustering, a DOVER-Lap consensus; `agreement.json` |
| 02 | `02_chunk_transcribe` | Spark (`.venv-denoise`) | `dataset/`: chunks + text, 48 kHz (ASR servers 192.168.1.71:8201, backup :8199) |
| 03 | `03_denoise` | Spark (`.venv-denoise`) | `dataset_clean/`; before/after in `outputs/denoise/samples/index.html` |
| 04 | `04_remove_non_speech` | Spark (`.venv-denoise`) | takes the no-speech chunks out of `dataset_clean/` (into `no_speech/`) |
| 05 | `05_remove_fillers` | Spark (`.venv-denoise`) | `dataset_nofillers/` (fillers, laughs, coughs cut); then step 5: `dataset_final/`, sentence chunks. Review in `outputs/fillers/review/index.html` and `outputs/fillers/sentences/index.html` |
| 06 | `06_finalize` | Spark (**`.venv-nemo`**) | **`dataset_train/`, the result**: checked against every diarization system (mixed speakers dropped, doubted labels decided by voice), numbers as words, text/audio match, speakers merged across podcasts, one loudness, 48 kHz, `train.txt` / `val.txt`. Review in `outputs/train/review/index.html` and `outputs/train/dropped/` |

**Kernels:** 01 and 06 use `.venv-nemo`, because NeMo needs Python 3.12 or newer. 00 and 02–05 use `.venv-denoise` (Python 3.11), because the denoise models in 03 need numpy < 2. In VS Code: Select Kernel → Python Environments.

**Run everything headless** on the Spark, inside tmux so it survives a closed terminal. Each notebook gets its kernel, and what it prints is saved into it:

    cd ~/projects/tts && tmux new -s pipeline
    scripts/run_pipeline.sh              # 01 to 06; or e.g. scripts/run_pipeline.sh 05 06
    # logs: runs/<RUN>/logs/<step>.log

**One notebook:** `.venv-denoise/bin/python scripts/run_notebook.py --save pipeline/03_denoise.ipynb`.

**If the ASR servers are down,** `scripts/wait_for_asr.sh <a short wav> && scripts/run_pipeline.sh 02 03 04 05 06` waits until one of them works, then goes on.

The notebooks in `src/data_preprocessing/` are the older copies, with the outputs of the main run in them.
