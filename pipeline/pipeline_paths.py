"""Where the pipeline notebooks read and write: 01_diarization, 02_chunk_transcribe, 03_denoise,
04_remove_non_speech, 05_remove_fillers and 06_finalize. Set RUN here once, for all of them; each notebook prints what it uses.

RUN = None      the main dataset: outputs/, dataset/, dataset_clean/, dataset_nofillers/, dataset_final/ and
                dataset_train/ in the project root.
RUN = "<name>"  a separate run in runs/<name>/, with the same folders inside. Nothing of the main dataset is read or
                changed, and the review pages (03 samples, 04 list, 05 review) show only this run's audio.
AUDIOS          the wavs of data/raw_audios/ that 01 and 02 take; None = all of them.
DIARIZATION     the diarization 02 cuts the speaker turns by and 06 takes as the reference: a system folder of 01
                ("nemotron", the only one built for 8 speakers) or "consensus". 06 checks every chunk against the others.
SAMPLE_RATE     48000: every wav keeps this rate from data/raw_audios/ to dataset_train/, nothing is resampled.
                01 and 02 stop when an input wav is not 48 kHz (check_sample_rate): upsampling a 24 kHz file leaves
                nothing above 12 kHz, so download the source again at 48 kHz instead (docs/data.md).

A notebook reads this file when its first cell runs, so after a change run that cell again (no restart needed).

A run numbers its podcasts from 001, like the main dataset, so its chunk names repeat the main dataset's
(001_0000_speaker_0.wav): rename them before merging a run into the main dataset.
"""
from pathlib import Path

RUN = "main48k"   # the full dataset at 48 kHz (2026-11-27); "test" is the 2-audio test run
AUDIOS = None     # every wav in data/raw_audios/

DIARIZATION = "nemotron"
SAMPLE_RATE = 48000

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
BASE = ROOT if RUN is None else ROOT / "runs" / RUN
AUDIO_DIR = ROOT / "data" / "raw_audios"        # input of 01 and 02, shared by every run
OUTPUTS = BASE / "outputs"                      # diarization/ (01), chunks/ (02), denoise/ (03), speech_check/ (04), fillers/ (05)
DATASET = BASE / "dataset"                      # 02 -> 03
DATASET_CLEAN = BASE / "dataset_clean"          # 03 -> 04 (in place) -> 05
DATASET_NOFILLERS = BASE / "dataset_nofillers"  # 05 step 4
DATASET_FINAL = BASE / "dataset_final"          # 05 step 5: sentence chunks
DATASET_TRAIN = BASE / "dataset_train"          # 06: the training set (filtered, numbers as words, one loudness, 24 kHz)


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


def check_sample_rate(wavs):
    """Stops when an input wav is not SAMPLE_RATE: the pipeline never resamples, so it would not be real 48 kHz."""
    import soundfile as sf
    bad = [f"{p.name} ({sf.info(str(p)).samplerate} Hz)" for p in wavs if sf.info(str(p)).samplerate != SAMPLE_RATE]
    if bad:
        raise ValueError(f"{len(bad)} of {len(wavs)} input wavs are not {SAMPLE_RATE} Hz, and the pipeline does not "
                         f"resample: download them again at {SAMPLE_RATE} Hz. " + "; ".join(bad))
    print(f"all {len(wavs)} input wavs are {SAMPLE_RATE} Hz")
