# What changed on 2026-11-27, in short

Short notes on today's changes, with the code. Older changes, and why things were decided: `docs/history.md`.

## 1. Transcription uses two ASR servers (02)
**Problem.** 02 sent every chunk to one server, `192.168.1.71:8199`. From 12:32 to 14:20 that server failed every job with `cudaErrorInvalidDevice: invalid device ordinal`, while `/health` still said `ready`. The pipeline stopped at 02.

**Change.** 02 now has a list of servers. It uses `8201` first and keeps `8199` as a backup. A job that fails is sent again, 3 times per server, and then to the next server. At the end, 02 prints how many chunks each server did.

```python
# pipeline/02_chunk_transcribe.ipynb, config cell
API = ["http://192.168.1.71:8201", "http://192.168.1.71:8199"]  # the first ready one is used; the next if a job keeps failing
TRIES = 3             # a failed job is sent again up to this many times per server
```

```python
# pipeline/02_chunk_transcribe.ipynb, transcription cell
def transcribe(path):
    """Text of one wav. A failed job is sent again, TRIES times per server, in the order of servers."""
    errors = []
    for url in servers:                     # the servers of API that answered /health with "ready"
        for _ in range(TRIES):
            try:
                text = " ".join(extract_text(wait(url, submit(url, path))).split())
                with used_lock:
                    used[url] += 1
                return text
            except Exception as e:
                errors.append(f"{url}: {type(e).__name__}: {e}")
    raise RuntimeError(f"{len(errors)} tries failed, last: {errors[-1] if errors else 'no server ready'}")
```

`scripts/wait_for_asr.sh` waits until **either** server works (`APIS="url1 url2"` to change the list).

**Tested** on the Spark, on real chunks, in a scratch folder (deleted afterwards):
- 8201 did all 6 test chunks; an address with no server behind it was skipped.
- With 8201 made to fail on purpose, all 6 went to 8199.

**What the two servers give.** Both report the same model path (`/models/ft_model`) and the same API. On 12 real chunks, 7 texts were identical and 5 differed only by a period or one word:

| | 8201 | 8199 |
|---|---|---|
| `0044_speaker_2` | Diqqat bering | Diqqat bering. |
| `0300_speaker_3` | … roldan olaman. | … roldan olay. |
| `0173_speaker_6` | … menga xavotir qildi. | … menga xavotir |

8201 also failed 3 of 8 jobs at 14:32, which is why the retry is there.

**On the whole test run** (re-transcribed at 14:45 with this change):
- 8201 did all 491 jobs, with 0 failures and 0 sent to 8199. That gives 430 chunks, 1.37 h, the same as with 8199.
- Compared with the 8199 texts of the same chunks (446 audio spans), the words differ:

  | | words | differ |
  |---|---|---|
  | the podcast (clean, 1 speaker) | 4,958 | 2.4% |
  | the series (drama, music) | 3,184 | 8.9% |

  Most of the differences are word endings (`mening` / `meni`, `hubermanni` / `hubermanning`). So the two ports run different models, or the same model with different decoding. Which one is closer to the audio is not measured yet.
- One short turn came out with fewer than 3 words on 8201, so 02 left it out. That shifted the chunk numbers after it: compare runs by time, not by file name.
- The 8199 version of the test run (02 to 04) is kept in `backups/2026-11-27_test_asr8199/`.

## 2. Diarization: four systems instead of one (01)
**Change.** 01 runs four diarization systems, each into its own folder `outputs/diarization/<audio>/<system>/`. A fifth folder, `consensus`, combines them (DOVER-Lap), for comparison only.

```python
# pipeline/01_diarization.ipynb, config cell
METHODS = ["nemotron", "sortformer_v2", "sortformer_v2_1", "clustering"]
GUIDE = "nemotron"      # clustering takes its speech regions and speaker count from this system
```

- **The clustering is guided by Nemotron.** Left on its own, it heard the music in the series as speech and called everyone one speaker.

  ```python
  cfg.diarizer.oracle_vad = True                                 # speech regions from the guide
  cfg.diarizer.clustering.parameters.oracle_num_speakers = True  # and its number of speakers
  ```
- **02 still cuts by Nemotron** (`DIARIZATION = "nemotron"` in `pipeline_paths.py`). It is the only system made for 8 speakers. On the series, the vote of all systems came out with 4 speakers for 8+ actors.
- **`agreement.json`** says how much two systems agree, from 0 to 1. The podcast: 1.0 everywhere. The series: 0.42–0.84, so its speaker labels are uncertain for about half the speech.

## 3. Every final chunk is checked against the other systems (06)
**Change.** 06 follows every final chunk back to the original audio. Each of the three other systems then votes:
- **agree:** it puts the chunk with the rest of that speaker's speech;
- **mixed:** it hears another speaker alone for 0.5 s or more inside the chunk.

The chunk is **dropped** only when most systems say "mixed". When most systems **doubt the label**, the voice decides (TitaNet, on the denoised chunk):

```python
# pipeline/06_finalize.ipynb, decide cell (shortened)
elif d and d["mixed"] >= need:                 # need = a majority of the systems
    decision[f] = "mixed_speakers"             # dropped
elif d and d["votes"] - d["agree"] >= need:    # most systems doubt the label: the voice decides
    best = max(cands, key=lambda l: sim(f, l))
    if best == c["speaker"]:
        decision[f] = "keep"                   # the voice is still its own speaker's
    elif sim(f, best) >= sim_own[f] + RELABEL_MARGIN:
        label_of[f] = best                     # clearly another speaker: relabeled, kept
        decision[f] = "keep"
    else:
        decision[f] = "uncertain_speaker"      # too close to call: dropped
```

## 4. Less is dropped (06)
Before today, 06 dropped every chunk with a doubtful speaker and every speaker with less than 1 minute. Now:

```python
RELABEL = True          # a doubted chunk whose voice is clearly another speaker's gets that label (False: dropped)
RELABEL_MARGIN = 0.05   # ...at least this much more alike to that speaker than to its own label
MIN_SPEAKER_MIN = 0.0   # keep every speaker, also small ones (it was 1.0)
```

Every drop still has a reason and a folder to listen to: `outputs/train/dropped/<reason>/`, and the review page `outputs/train/review/index.html`.

## 5. Running the notebooks headless
- `scripts/run_pipeline.sh [steps]`:
  - runs the notebooks in order, each with its own venv (01 and 06 with `.venv-nemo`, the others with `.venv-denoise`);
  - writes a log per step in `runs/<RUN>/logs/`;
  - stops at the first error.
- `scripts/run_notebook.py --save` writes what each cell printed into the notebook, so you can open it afterwards and see the run.

```bash
cd ~/projects/tts && tmux new -s pipeline
scripts/run_pipeline.sh                 # 01 to 06
scripts/run_pipeline.sh 05 06           # only these
```

## 6. Docs
- `AGENTS.md`: the overview and the rules, for any agent. `CLAUDE.md` loads it.
- `docs/`:
  - `pipeline.md`: each step;
  - `data.md`: folders and formats;
  - `environments.md`: venvs, models, ASR servers;
  - `history.md`: decisions;
  - `results.md`: numbers per stage;
  - `changes.md`: this file.

## 7. 48 kHz from input to output
**Problem.**
- Every input was below 48 kHz: the downloader turns YouTube's 48 kHz Opus into 24 kHz.
- The pipeline then resampled three times:
  - 02 upsampled 24 → 48 kHz;
  - 03 sent music chunks 48 → 16 → 48 kHz through MossFormerGAN;
  - 06 downsampled 48 → 24 kHz.

**Change.** 48 kHz everywhere, and no step resamples the audio it keeps. Models that need 16 kHz still get a 16 kHz *copy*, and the stored audio is untouched.

```python
# pipeline/pipeline_paths.py
SAMPLE_RATE = 48000

def check_sample_rate(wavs):
    """Stops when an input wav is not SAMPLE_RATE: the pipeline never resamples, so it would not be real 48 kHz."""
    bad = [f"{p.name} ({sf.info(str(p)).samplerate} Hz)" for p in wavs if sf.info(str(p)).samplerate != SAMPLE_RATE]
    if bad:
        raise ValueError(f"{len(bad)} of {len(wavs)} input wavs are not {SAMPLE_RATE} Hz, ... download them again")
```

```python
# 01 and 02, first cell
wavs = P.audio_files()
P.check_sample_rate(wavs)   # 48 kHz from input to output: stops on a wav that is not

# 02: was `if sr != OUT_SR: x = AF.resample(...)`
OUT_SR = P.SAMPLE_RATE
assert sr == OUT_SR, f"{src}: {sr} Hz, the input must be {OUT_SR} Hz (nothing is resampled)"

# 06: was OUT_SR = 24000 and a resample
OUT_SR = P.SAMPLE_RATE
assert sr == OUT_SR, (c["file"], sr)                     # never resampled
```

```python
# 03: MossFormer2_SE_48K instead of MossFormerGAN_SE_16K (+ DFN3 above 7 kHz)
USE = {"music": "mossformer2", "noisy": "dfn3"}          # both models work at 48 kHz
mf2 = ClearVoice(task="speech_enhancement", model_names=["MossFormer2_SE_48K"]).models[0]
mf2.model.to(dev); mf2.device = dev                      # ClearVoice can't read the GB10's memory and picks the CPU

def mossformer2(x):
    with torch.no_grad():
        y = np.asarray(decode_one_audio(mf2.model, mf2.device, x[None, :], mf2.args), dtype=np.float32).reshape(-1)
    return np.pad(y, (0, max(0, len(x) - len(y))))[:len(x)]
```

- **00** now makes the audio mono (`-ac 1`) and prints each wav's rate. It never had `-ar`, so it keeps the video's own rate.
- **`scripts/download_48k.py`** (Mac, with the `stt_data_collection` venv) downloads YouTube format 251 (Opus, 48 kHz) and decodes it to a 48 kHz mono wav, with no `-ar`.
- **The test run's audios** were downloaded again this way:
  - 48 kHz, with content up to 20 kHz (the 24 kHz files stopped at 12 kHz);
  - the 24 kHz files are in `backups/2026-11-27_raw_audios_24k/`.

**Tested** on 6 music chunks of the series, cut from the 48 kHz audio:
- MossFormer2_SE_48K took 0.08 s per second of audio on the GPU; MossFormerGAN took about 0.5.
- It removed about as much as DeepFilterNet3 (5.6–14.6 dB against 5.7–13.1 dB).
- Every output was 48 kHz and kept the input's length.

## Files changed today
| File | What |
|---|---|
| `pipeline/01_diarization.ipynb` | 4 systems, guided clustering, consensus, `agreement.json` |
| `pipeline/02_chunk_transcribe.ipynb` | two ASR servers with retries; RTTM from `DIARIZATION` |
| `pipeline/06_finalize.ipynb` | diarization check, voice decides, relabeling, small speakers kept |
| `pipeline/pipeline_paths.py` | `DIARIZATION = "nemotron"` |
| `pipeline/configs/diar_infer_general.yaml` | the clustering config, from NeMo |
| `scripts/run_pipeline.sh`, `scripts/run_notebook.py`, `scripts/wait_for_asr.sh` | headless runs, waiting for the ASR servers |
| `pipeline/pipeline_paths.py`, `00`, `01`, `02`, `03`, `06`, `scripts/download_48k.py` | 48 kHz from input to output |
| `AGENTS.md`, `CLAUDE.md`, `docs/*.md`, `README.md`, `pipeline/README.md` | docs |

## Backups (on the Spark, `~/projects/tts/backups/`)
- `2026-11-27_before_diar_ensemble/`: the notebooks before today's changes, and the old test `dataset_train` (`dataset_train_v1/`: 517 chunks, 68.4 min).
- `2026-11-27_48khz/`: the notebooks and docs before the 48 kHz change; `2026-11-27_raw_audios_24k/`: the 24 kHz test audios; `2026-11-27_test_v2_24k/`: the test run made from them.
- `2026-11-27_asr_two_servers/`: 02, `wait_for_asr.sh` and the docs before the two-server change.
