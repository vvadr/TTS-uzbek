# The pipeline, step by step

Notebooks in `pipeline/`. Each one reads its folders from `pipeline_paths.py`, puts every setting in one config cell, prints counts and hours, and resumes where it stopped. To run them headless on the Spark: `scripts/run_pipeline.sh [steps]` (see `AGENTS.md`).

**Principle: 48 kHz from input to output.** The input wavs must be 48 kHz, and no step resamples the audio it keeps (`docs/data.md`).

**Principle: fix rather than drop.** Each step removes only what can't be repaired, and says why, with a review page or a `dropped/<reason>/` folder to listen to. On the test run, most of what disappears between raw audio and the training set is music and silence, not speech (`docs/results.md`).

---

## 00 Video to wav (optional)
`data/videos/*` → `data/raw_audios/*.wav` with ffmpeg. Skips files that exist.

## 01 Diarization: who speaks when
- **Systems**, each in `outputs/diarization/<audio>/<system>/`:

  | System | What it is |
  |---|---|
  | `nemotron` | Nemotron-3-Diarization, up to 8 speakers. **The reference.** |
  | `sortformer_v2`, `sortformer_v2_1` | Streaming Sortformer, up to 4 speakers |
  | `clustering` | NeMo ClusteringDiarizer, guided by Nemotron's speech regions and speaker count. TitaNet embeddings at three scales plus spectral clustering decide who is who. |
  | `consensus` | DOVER-Lap of all four, for comparison only |
- **Why Nemotron is the reference:** on the test series, the 4-speaker models merged actors, the unguided clustering called everything one speaker, and the consensus came out with 4 speakers. Details in `docs/history.md`.
- **Outputs:** each system writes `<audio>.rttm`, `stats.json` and `timeline.png`. Per audio, `agreement.json` holds the many-to-one label agreement between every two systems (1.0 = they split the speech the same way).
- **Settings:** `METHODS`, `GUIDE`, `MAX_SPEAKERS`, `DOVER_STD`, `FORCE`.
- **Time on the Spark:** about 15–60 s per system per 45 min of audio; clustering takes 20–90 s.

## 02 Chunk and transcribe
1. **Turns:** consecutive diarization segments of one speaker. A pause > 3 s ends a turn, and only 0.5 s of it is kept on each side. Two turns are cut apart at the quietest 10 ms of the pause between them.
2. **Short turns** (< 1 s) are transcribed first. Those with fewer than 3 words ("ha", "mm") are omitted; diarization blips under 0.1 s are too.
3. **Merge:** when an omitted turn interrupts a speaker (A, B: "ha", A), it is cut out and A's two parts become one chunk, joined with a 20 ms crossfade. **Split:** a turn over 29.5 s is cut at its longest pauses. (05 step 5 later re-cuts at sentence ends.)
4. **Transcribe** every chunk on its own with the ASR server (`uz`): 8201 first; a job that fails is sent again, then to 8199. A short turn that stays a chunk reuses its step-2 text.
5. **Dataset:**
   - omitted: empty transcripts, and Whisper loops (a word or phrase repeated more than 3 times in a row);
   - `bo 'ladi` becomes `bo'ladi`;
   - kept at 48 kHz, the rate of the input: never resampled.

Uses the diarization `DIARIZATION` names. Time: mostly the ASR server's queue.

## 03 Denoise
1. **Scan** every chunk:
   - AST "Music" probability of its most musical 10 s;
   - the steady background in the pauses, in dB below the speech. DeepFilterNet3 finds the pauses; hiss, hum and music beds count, a laugh doesn't.
2. **Find:** music ≥ 0.2 → `music`. Otherwise background ≥ −35 dB → `noisy`. A chunk with < 0.3 s of pause gets its speaker's median background.
3. **Samples:** `outputs/denoise/samples/index.html`, before/after of both models.
4. **Denoise** into `dataset_clean/`:
   - `USE = {"music": "mossformer2", "noisy": "dfn3"}`. Both models work at 48 kHz themselves:
     - DeepFilterNet3 for noisy chunks: the user's choice of 2026-11-25;
     - MossFormer2_SE_48K for music: since 2026-11-27, in place of the 16 kHz MossFormerGAN, which needed 48 → 16 → 48 kHz.
   - Clean chunks are hard links.
   - A chunk is left out when the model removed more energy than it kept (a lone "hm", or no speech at all).

Time: DFN3 about 1 s per minute of audio; MossFormer2_SE_48K about 0.08 s per second of audio on the Spark's GPU.

## 04 Remove non-speech
Silero VAD scores each 32 ms of every chunk.
- **Removed:** chunks with < 0.3 s of speech, or speech on < 20% of the chunk. Their wavs move to `no_speech/`; the full list is kept in `metadata.all.json`, and the step can be undone.
- **Only listed:** "text longer than speech" (> 25 characters per second of speech).

Time: a few minutes.

## 05 Remove fillers, then sentence chunks
1. **Analyse** every chunk:
   - MMS forced alignment (Uzbek Latin adapter, 20 ms);
   - written fillers: the sound between their neighbouring words;
   - unwritten sounds: stretches of sound, or of a vocal burst, that no word covers.

   Each sound gets what MMS hears in it by itself, pitch steadiness (pYIN), AST laugh/cough/breath probabilities and the Vocal Burst Locator v2 probability. Cached in `outputs/fillers/analysis.json`.
2. **Decide:** each sound is typed as `filler`, `burst`, `laugh`, `cough`, `breath`, `speech` (words the text lacks), `word_edge` or `other`.
   - **Cut:** `filler`, `burst`, `laugh`, `cough`, `speech`, `other`. **Kept:** breaths and word edges.
   - A cut inside a chunk becomes a short pause of the chunk's own room tone: 40% of the cut, 0.10–0.35 s.
   - Written fillers are removed from the text too.
   - **Dropped:** filler-only texts, texts that don't align, ≥ 0.5 s of untranscribed speech, and chunks < 1 s after cutting.
3. **Review:** `outputs/fillers/review/index.html`, and `dropped/<reason>/`.
4. **Build** `dataset_nofillers/`.
5. **Sentence chunks** `dataset_final/`:
   - **Join:** a speaker's consecutive chunks are joined (same speaker, contiguous in the original audio, same denoising).
   - **Cut:** only at a sentence end (`. ! ? …`) followed by a pause ≥ `SPLIT_PAUSE_SEC` (0.5 s).
   - **Long:** a piece over 30 s is cut at its sentence end with the longest pause; without one, it keeps its old cuts.
   - **Short:** a piece under 1 s joins its neighbour.
   - **Edges:** at most 0.2 s of silence at each end.
   - Word times come from MMS, cached in `words.json`. Review: `outputs/fillers/sentences/index.html`.

Time: about 0.08 s per second of audio for step 1, and 2–3 min per hour for the step-5 alignment.

## 06 Finalize: the training set
1. **Diarization check.** Every final chunk is followed back through all cuts to the original timeline. Every system other than the reference votes:
   - **agree:** it puts the chunk with the rest of that speaker's speech;
   - **mixed:** it hears another speaker alone for ≥ 0.5 s inside the chunk.

   The reference also gives the chunk's overlap: two people talking at once.
2. **Text:**
   - numbers and symbols become Uzbek words; every possible reading is scored by MMS forced alignment on the chunk's audio, and the best fit wins;
   - `align_prob` (mean letter probability) measures how well the text matches the audio.
3. **Speakers:**
   - a TitaNet embedding of every (denoised) chunk;
   - each label's voice is averaged over the chunks the systems confirm;
   - labels whose voices are ≥ 0.70 alike are merged into one speaker id, across podcasts too.
4. **Decide:**
   - **Dropped:**
     - unreadable characters;
     - `align_prob` < 0.40;
     - overlap ≥ 0.5 s;
     - mixed speakers (a majority of the systems);
     - uncertain speaker (see below).
   - **Doubted labels:** when a majority doubts a chunk's label, the voice decides:
     - still its own label → kept;
     - ≥ 0.05 closer to another speaker → **relabeled**;
     - too close to call → dropped.
   - Small speakers are kept (`MIN_SPEAKER_MIN = 0`).
   - Review: `outputs/train/review/index.html` and `outputs/train/dropped/<reason>/`.
5. **Build** `dataset_train/`: −23 LUFS (BS.1770, peak ≤ −1 dBFS), 48 kHz (not resampled), `metadata.json`, and the `train.txt` / `val.txt` manifests (2% validation per speaker).

Time: roughly 3 min per hour of audio for the alignment, plus about a minute for embeddings and the build.
