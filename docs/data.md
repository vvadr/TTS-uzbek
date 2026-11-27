# Data: folders and file formats

## Sample rate: 48 kHz from input to output
- Every wav that is kept, from `data/raw_audios/` to `dataset_train/`, is 48 kHz mono 16-bit, and no step resamples it. Models that need 16 kHz (diarization, Silero, MMS, TitaNet, AST) get a temporary copy, and the stored audio stays as it is.
- **Input check:** 01 and 02 stop with a list of the wavs that are not 48 kHz (`pipeline_paths.check_sample_rate`). An upsampled 24 kHz file has nothing above 12 kHz, so resampling would not give real 48 kHz audio.
- **YouTube:**
  - Its audio stream is Opus at 48 kHz (format 251, about 105–140 kbps), with content up to 20 kHz; nothing above 20 kHz is there to begin with.
  - Get it with `scripts/download_48k.py`.
  - The `stt_data_collection` downloader turns the same stream into 24 kHz on purpose, for its own corpus, and deletes the original.
- **What is 48 kHz now (2026-11-27):** on the Spark, `data/raw_audios/` holds 33 wavs at 48 kHz (41.6 h):
  - the 30 podcasts of the main dataset (links in `data/podcasts.md`) and `OyQOvi9Qhxs`, downloaded again with `scripts/download_48k.py --opus-only`;
  - the 2 test audios.

  The Opus originals are kept in `data/source_opus/` (2 GB), so they never need downloading again.
- **Not available at 48 kHz:** `abuser.wav` (69 s, no link) and `signal-2026-11-20-224446.wav` (24 s, from Signal). The Mac's `data/raw_audios/` still has the old 24 kHz and 44.1 kHz files.

## Run folders
`pipeline/pipeline_paths.py` decides where everything goes:
- `RUN = None`: the main dataset, in the project root.
- `RUN = "<name>"`: a separate run in `runs/<name>/`, with the same layout inside.

The input audio always comes from `data/raw_audios/`, and `AUDIOS` picks which files.

```
data/source_opus/<audio>.webm       the YouTube downloads (Opus, 48 kHz): the originals of the raw wavs
data/raw_audios/<audio>.wav          input: 48 kHz mono, one file per podcast or episode (01 and 02 stop on another rate)
<run>/outputs/
  diarization/<audio>/<system>/      01: <audio>.rttm, stats.json, timeline.png; systems nemotron, sortformer_v2,
                                         sortformer_v2_1, clustering, and consensus
  diarization/<audio>/agreement.json 01: share of the speech two systems hear as the same speaker
  chunks/<audio>/                    02: turns.json, short/ + short_text.json, wavs/ + chunks.json, text.json
  denoise/                           03: scores.json, flagged.json, samples/index.html
  speech_check/                      04: <dataset>_scores.json
  fillers/                           05: analysis.json, report.json, review/index.html, dropped/<reason>/,
                                         words.json (step 5 alignment), sentences/index.html
  train/                             06: text.json, speakers.npz, report.json, review/index.html, dropped/<reason>/
<run>/logs/<step>.log                scripts/run_pipeline.sh
<run>/dataset/                       02: chunks/*.wav (48 kHz) + metadata.json
<run>/dataset_clean/                 03 + 04: chunks/, metadata.json, metadata.all.json (before 04), no_speech/,
                                         no_speech.json, denoise_log.json
<run>/dataset_nofillers/             05 step 4
<run>/dataset_final/                 05 step 5: sentence chunks
<run>/dataset_train/                 06: the training set
```

Chunks that didn't change between stages are **hard links**, so they take no extra disk space. That holds through 03, 05 and the `dropped/` folders. Deleting a folder deletes only its links.

## Chunk names
`chunks/<podcast number>_<chunk number>_<speaker label>.wav`, for example `001_0042_speaker_1.wav`. 05 step 5 adds `-<piece>` (`001_0042_speaker_1-3.wav`).
- The podcast number is the podcast's position in that run's sorted list, so **names repeat across runs**. Rename before merging a run into another.
- The speaker label is the diarization's label (`DIARIZATION`), unique only within one podcast: `001_speaker_1` and `002_speaker_1` are different people. 06 gives the final speaker ids (`spk000`, ...), merged across podcasts.

## `metadata.json`
Every dataset folder has one:
```json
{"sample_rate": 48000,
 "podcasts": {"001": "<audio name>", "002": "..."},
 "chunks": [{"file": "chunks/001_0042_speaker_1.wav", "speaker": "001_speaker_1", "text": "...",
             "duration": 7.43, "start": 812.31, "end": 819.9}]}
```
Each stage adds fields:

| Stage | Added |
|---|---|
| 02 `dataset/` | `start`, `end`: the span in the original audio. A chunk merged across an interruption is shorter than `end - start`. |
| 03 `dataset_clean/` | `denoised`: `"dfn3"` or `"mossformer2"` (before 2026-11-27: `"mossformergan"`), when the chunk was denoised. Top level: `denoise` settings. |
| 04 | top level: `speech_check` settings. Removed chunks are listed in `no_speech.json`. |
| 05 `dataset_nofillers/` | `fillers`: `{cuts: [[start, end, type]], text_before}` for edited chunks. Top level: `fillers` settings. |
| 05 `dataset_final/` | `sources`: `[[dataset_nofillers file, from s, to s], ...]`, what the chunk was made of. Top level: `sentence_chunks` settings. |
| 06 `dataset_train/` | `speaker` (final id), `speaker_label`, `speaker_label_before` (when relabeled), `split`, `diarization` ("agree/voted"), `text_original` (when numbers were written out), `align_prob`, `overlap_sec`, `gain_db`. Top level: `speakers` (`id → labels, minutes, chunks`), `settings`, `sample_rate` 24000. |

## Manifests (`dataset_train/`)
`train.txt` and `val.txt` hold one chunk per line, pipe-separated, in the LJSpeech/VITS style:
```
chunks/001_0000_speaker_0-1.wav|Neyrobiologiyaga, o'zi miyaga qiziqishim azaldan bo'lgan, bu narsa haqida gapirganman.|spk000
```
The text is Uzbek Latin with the ASCII apostrophe, punctuation kept, and numbers written as words. 2% of each speaker's chunks are validation, chosen from chunks of 1.5–15 s.

## RTTM
`SPEAKER <file id> 1 <start> <duration> <NA> <NA> <speaker> <NA> <NA>`. The file id is the audio name with spaces replaced by `_`. Readers count fields from the end, so names with spaces still parse.
