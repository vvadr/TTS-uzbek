# Pipeline: raw audio -> training dataset

Run the notebooks one at a time, in this order. `pipeline_paths.py` sets where they read and write:
`RUN = "test"` puts everything in `runs/test/`, `RUN = None` is the main dataset in the project root.
`AUDIOS` picks the wavs of `data/raw_audios/`. Every notebook prints its folder first.

| # | notebook | where (kernel) | makes, in the run folder |
|---|---|---|---|
| 00 | `00_video_to_wav` | anywhere; only if you start from videos | `data/raw_audios/*.wav` from `data/videos/` |
| 01 | `01_diarization` | **Mac** (`.venv`: NeMo is only there) | `outputs/diarization/`: who speaks when |
| 02 | `02_chunk_transcribe` | Spark (`.venv-denoise`) | `dataset/`: chunks + text, 48 kHz (Whisper server 192.168.1.71:8199) |
| 03 | `03_denoise` | Spark (`.venv-denoise`) | `dataset_clean/`; before/after in `outputs/denoise/samples/index.html` |
| 04 | `04_remove_non_speech` | Spark (`.venv-denoise`) | takes the no-speech chunks out of `dataset_clean/` (into `no_speech/`) |
| 05 | `05_remove_fillers` | Spark (`.venv-denoise`) | `dataset_nofillers/`, the result; review in `outputs/fillers/review/index.html` |

01 runs on the Mac, so copy the audio there first and the diarization back afterwards (from the project root):

    scp 'intern@192.168.1.88:projects/tts/data/raw_audios/<name>.wav' data/raw_audios/
    rsync -a runs/test/outputs/diarization/ intern@192.168.1.88:projects/tts/runs/test/outputs/diarization/

To keep a step running on the Spark after the terminal closes, run it headless in tmux:

    cd ~/projects/tts && tmux new -s step02
    .venv-denoise/bin/python scripts/run_notebook.py pipeline/02_chunk_transcribe.ipynb

The notebooks in `src/data_preprocessing/` are the older copies, with the outputs of the main run in them.
