"""Where the pipeline notebooks read and write: 04_diarization, 07_chunk_transcribe_dataset, 08_denoise,
09_remove_non_speech and 10_remove_fillers. Set RUN here once, for all of them; each notebook prints what it uses.

RUN = None      the main dataset: outputs/, dataset/, dataset_clean/ and dataset_nofillers/ in the project root.
RUN = "<name>"  a separate run in runs/<name>/, with the same folders inside. Nothing of the main dataset is read or
                changed, and the review pages (08 samples, 09 list, 10 review) show only this run's audio.
AUDIOS          the wavs of data/raw_audios/ that 04 and 07 take; None = all of them.

A notebook reads this file when its first cell runs, so after a change run that cell again (no restart needed).

A run numbers its podcasts from 001, like the main dataset, so its chunk names repeat the main dataset's
(001_0000_speaker_0.wav): rename them before merging a run into the main dataset.
"""
from pathlib import Path

RUN = "test"
AUDIOS = [
    "neyrobiologiya_va_qaysi_kunlik_WqD84GbTcBM.wav",
    "shaytanat_qism_milliy_serial_AsthRnnwvD4.wav",
]

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
BASE = ROOT if RUN is None else ROOT / "runs" / RUN
AUDIO_DIR = ROOT / "data" / "raw_audios"        # input of 04 and 07, shared by every run
OUTPUTS = BASE / "outputs"                      # diarization/ (04), chunks/ (07), denoise/ (08), speech_check/ (09), fillers/ (10)
DATASET = BASE / "dataset"                      # 07 -> 08
DATASET_CLEAN = BASE / "dataset_clean"          # 08 -> 09 (in place) -> 10
DATASET_NOFILLERS = BASE / "dataset_nofillers"  # 10


def audio_files():
    """The wavs of AUDIO_DIR that this run takes, sorted by name."""
    wavs = sorted(AUDIO_DIR.glob("*.wav"))
    if AUDIOS is None:
        return wavs
    missing = sorted(set(AUDIOS) - {p.name for p in wavs})
    assert not missing, f"AUDIOS in pipeline_paths.py names wavs that are not in {AUDIO_DIR}: {missing}"
    left_out = [p.name for p in wavs if p.name not in AUDIOS]
    if left_out:
        print(f"not in AUDIOS, left out: {left_out}")
    return [p for p in wavs if p.name in AUDIOS]


def describe():
    return f"{'main dataset' if RUN is None else f'run {RUN!r}'}: reading and writing in {BASE}"
